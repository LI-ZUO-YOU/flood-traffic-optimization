from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd


TARGET_GAP = 5e-4


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def load_interface(path: Path):
    spec = importlib.util.spec_from_file_location("final_exact_interfaces", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_method_freezes(paths: list[Path], scenario_ids: list[int]) -> list[dict]:
    records = []
    full_seen = set()
    controls_seen = set()
    for path in paths:
        record = json.loads(path.read_text(encoding="utf-8"))
        sid = int(record["scenario_id"])
        if sid not in scenario_ids:
            raise ValueError(f"Freeze {path} refers to unexpected scenario {sid}")
        if record.get("method") == "full_method" and record.get("method_output_frozen_before_exact_reference"):
            full_seen.add(sid)
        if record.get("all_five_controls_frozen") is True:
            controls_seen.add(sid)
        for relative, expected in record.get("files", {}).items():
            artifact = path.parent / relative
            if not artifact.is_file() or sha256(artifact) != expected:
                raise RuntimeError(f"Frozen method artifact mismatch: {artifact}")
        records.append({"path": str(path), "sha256": sha256(path), "scenario_id": sid})
    missing_full = sorted(set(scenario_ids) - full_seen)
    missing_controls = sorted(set(scenario_ids) - controls_seen)
    if missing_full or missing_controls:
        raise RuntimeError(f"Exact reference blocked: missing full={missing_full}, controls={missing_controls}")
    return records


def exact_dp(frame: pd.DataFrame, roads: list[int]) -> tuple[dict, pd.DataFrame]:
    costs = {int(row.subset_mask): float(row.loss) for row in frame.itertuples(index=False)}
    if set(costs) != set(range(1024)):
        raise ValueError("Exact reference requires all 1024 subsets")
    full = 1023
    dp = {0: costs[0]}
    predecessor = {}
    for size in range(1, 11):
        for mask in range(1, 1024):
            if mask.bit_count() != size:
                continue
            prior, road, index = min(
                (dp[mask ^ (1 << index)], int(road), index)
                for index, road in enumerate(roads) if mask & (1 << index)
            )
            dp[mask] = prior + (0.0 if mask == full else costs[mask])
            predecessor[mask] = (road, index, mask ^ (1 << index))
    reverse, cursor = [], full
    while cursor:
        road, _, cursor = predecessor[cursor]
        reverse.append(road)
    sequence = list(reversed(reverse))
    rows, mask, cumulative = [], 0, 0.0
    for stage in range(11):
        row = frame[frame["subset_mask"].astype(int) == mask].iloc[0]
        weight = 0.1 if stage < 10 else 0.0
        cumulative += weight * float(row["loss"])
        rows.append({"stage": stage, "subset_mask": mask,
                     "restored_links_before_interval": ";".join(map(str, sequence[:stage])),
                     "tstt": row["tstt"], "loss": row["loss"], "stage_weight": weight,
                     "weighted_loss": weight * float(row["loss"]), "cumulative_objective": cumulative})
        if stage < 10:
            mask |= 1 << roads.index(sequence[stage])
    solution = {
        "candidate_roads": roads,
        "optimal_sequence": sequence,
        "exact_objective": dp[full] / 10.0,
        "dp_sum_loss_R0_to_R9": dp[full],
        "terminal_state_loss_R10_zero_weight": costs[full],
        "conditional_optimum": True,
    }
    return solution, pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Complete the 1024-state exact reference only after all method outputs are frozen.")
    parser.add_argument("--scenario-physical", required=True)
    parser.add_argument("--scenario-metadata", required=True)
    parser.add_argument("--method-output-freeze", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--interface", required=True)
    cache_group = parser.add_mutually_exclusive_group(required=True)
    cache_group.add_argument("--cache-path")
    cache_group.add_argument("--cache-dir")
    parser.add_argument("--cache-namespace", required=True)
    parser.add_argument("--python-dependency", action="append", default=[])
    args = parser.parse_args()

    physical_path = Path(args.scenario_physical)
    metadata_path = Path(args.scenario_metadata)
    output = Path(args.output_dir)
    if output.exists():
        raise FileExistsError(output)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    scenario_ids = list(map(int, metadata.get("selected_scenario_ids", [row["scenario_id"] for row in metadata["scenarios"]])))
    roads_by_sid = {int(row["scenario_id"]): list(map(int, row["selected_recoverable_roads"])) for row in metadata["scenarios"]}
    freeze_records = validate_method_freezes([Path(value) for value in args.method_output_freeze], scenario_ids)
    physical_all = pd.read_csv(physical_path)
    api = load_interface(Path(args.interface))
    rows = []
    started = time.perf_counter()
    for sid in scenario_ids:
        cache_path = Path(args.cache_path) if args.cache_path else Path(args.cache_dir) / f"scenario_{sid}.sqlite"
        namespace = f"{args.cache_namespace}_s{sid}" if args.cache_dir else args.cache_namespace
        ue = api.UEInterface(
            cache_path=cache_path,
            model_root=Path(args.model_root),
            cache_namespace=namespace,
            dependency_paths=[Path(value) for value in args.python_dependency],
        )
        try:
            scenario = physical_all[physical_all["scenario_id"].astype(int) == sid].copy()
            roads = roads_by_sid[sid]
            if len(scenario) != 38 or len(roads) != 10:
                raise ValueError(f"Scenario {sid}: invalid physical table or recoverable-road set")
            for mask in range(1024):
                restored = [road for index, road in enumerate(roads) if mask & (1 << index)]
                result = None
                last_error = None
                try:
                    for max_iter in (1000, 3000, 10000):
                        api.MAX_UE_ITERATIONS = max_iter
                        try:
                            result = ue.run_ue(scenario, restored, f"final_scenario_{sid}")
                            break
                        except RuntimeError as exc:
                            if "UE failed to converge" not in str(exc):
                                raise
                            last_error = exc
                finally:
                    api.MAX_UE_ITERATIONS = 1000
                if result is None:
                    raise RuntimeError(f"Scenario {sid}, subset {mask}: UE failed") from last_error
                rows.append({
                    "scenario_id": sid,
                    "subset_mask": mask,
                    "restored_count": len(restored),
                    "restored_links": ";".join(map(str, restored)),
                    "state_hash": result.state_hash,
                    "tstt": result.tstt,
                    "normalized_tstt": result.normalized_tstt,
                    "loss": result.loss,
                    "relative_gap": result.relative_gap,
                    "iterations": result.iterations,
                    "converged": result.converged,
                    "preexisting_physical_cache_hit": result.cache_hit,
                    "elapsed_seconds": result.elapsed_seconds,
                })
            print(json.dumps({"event": "exact_scenario_complete", "scenario_id": sid,
                              "states": 1024, "elapsed_seconds": round(time.perf_counter() - started, 2)}), flush=True)
        finally:
            ue.cache.close()

    output.mkdir(parents=True)
    costs = pd.DataFrame(rows).sort_values(["scenario_id", "subset_mask"])
    cost_path = output / "subset_ue_costs.csv"
    costs.to_csv(cost_path, index=False, encoding="utf-8-sig")
    solutions, paths, checks = {}, [], {}
    for sid in scenario_ids:
        frame = costs[costs["scenario_id"].astype(int) == sid]
        solution, path = exact_dp(frame, roads_by_sid[sid])
        solution["scenario_id"] = sid
        solutions[str(sid)] = solution
        path.insert(0, "scenario_id", sid)
        paths.append(path)
        checks[str(sid)] = {
            "rows_1024": len(frame) == 1024,
            "all_converged": bool(frame["converged"].all()),
            "max_relative_gap": float(frame["relative_gap"].max()),
            "exact_objective_finite": math.isfinite(solution["exact_objective"]),
        }
    solution_path = output / "exact_dp_solution.json"
    path_path = output / "exact_dp_path.csv"
    write_json(solution_path, {"schema_version": "final-exact-reference-v1.0",
                               "objective": "mean loss R0..R9; R10 zero weight", "scenarios": solutions})
    pd.concat(paths, ignore_index=True).to_csv(path_path, index=False, encoding="utf-8-sig")
    report = {
        "schema_version": "final-exact-reference-verification-v1.0",
        "status": "pass" if all(value["rows_1024"] and value["all_converged"] and
                                 value["max_relative_gap"] <= TARGET_GAP + 1e-12 and
                                 value["exact_objective_finite"] for value in checks.values()) else "fail",
        "method_freezes_verified_before_exact_reference": freeze_records,
        "state_count": len(costs),
        "scenario_checks": checks,
        "all_converged": bool(costs["converged"].all()),
        "max_relative_gap": float(costs["relative_gap"].max()),
        "preexisting_cache_hits": int(costs["preexisting_physical_cache_hit"].sum()),
        "wall_seconds": time.perf_counter() - started,
    }
    verification_path = output / "verification_report.json"
    write_json(verification_path, report)
    freeze = {
        "schema_version": "final-exact-reference-freeze-v1.0",
        "method_outputs_were_frozen_first": True,
        "scenario_physical_sha256": sha256(physical_path),
        "scenario_metadata_sha256": sha256(metadata_path),
        "subset_ue_costs_sha256": sha256(cost_path),
        "exact_dp_solution_sha256": sha256(solution_path),
        "exact_dp_path_sha256": sha256(path_path),
        "verification_report_sha256": sha256(verification_path),
    }
    write_json(output / "exact_reference_freeze.json", freeze)
    if report["status"] != "pass":
        raise RuntimeError("Exact-reference verification failed")
    print(json.dumps({"status": "pass", "output": str(output), "states": len(costs)}, indent=2))


if __name__ == "__main__":
    main()
