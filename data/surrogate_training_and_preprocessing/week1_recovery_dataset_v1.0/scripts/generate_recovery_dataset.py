from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

PACKAGE_ROOT = Path(__file__).resolve().parent
if not (PACKAGE_ROOT / "models").exists() and (PACKAGE_ROOT.parent / "models").exists():
    PACKAGE_ROOT = PACKAGE_ROOT.parent
sys.path.insert(0, str(PACKAGE_ROOT))


BASELINE_TSTT = 7480225.3449211195
DEFAULT_COUNTS = {
    "train": 1500,
    "calibration": 300,
    "test_id": 300,
    "test_severe": 300,
}
SPLIT_SEEDS = {
    "train": 202608031,
    "calibration": 202608032,
    "test_id": 202608033,
    "test_severe": 202608034,
}

_WORKER_LINKS: pd.DataFrame | None = None
_WORKER_OD: pd.DataFrame | None = None
_WORKER_SCENARIOS: dict[int, pd.DataFrame] | None = None
_WORKER_GAP: float = 5e-4
_WORKER_MAX_ITER: int = 1000


def _worker_init(links_path: str, od_path: str, scenarios_path: str, target_gap: float, max_iter: int) -> None:
    global _WORKER_LINKS, _WORKER_OD, _WORKER_SCENARIOS, _WORKER_GAP, _WORKER_MAX_ITER
    from models import build_flooded_solver  # noqa: F401

    _WORKER_LINKS = pd.read_csv(links_path)
    _WORKER_OD = pd.read_csv(od_path)
    all_scenarios = pd.read_csv(scenarios_path)
    _WORKER_SCENARIOS = {
        int(scenario_id): frame.copy()
        for scenario_id, frame in all_scenarios.groupby("scenario_id", sort=False)
    }
    _WORKER_GAP = float(target_gap)
    _WORKER_MAX_ITER = int(max_iter)


def _solve_task(task: dict) -> dict:
    from models import build_flooded_solver

    assert _WORKER_LINKS is not None and _WORKER_OD is not None and _WORKER_SCENARIOS is not None
    scenario_id = int(task["scenario_id"])
    restored = set(int(value) for value in task["restored_physical_links"])
    scenario = _WORKER_SCENARIOS[scenario_id].copy()
    restore_rows = scenario.physical_link_id.isin(restored)
    scenario.loc[restore_rows, "depth_m"] = 0.0
    scenario.loc[restore_rows, "is_wet"] = 0
    scenario.loc[restore_rows, "is_closed"] = 0
    scenario.loc[restore_rows, "speed_ratio"] = 1.0
    scenario.loc[restore_rows, "free_flow_time_multiplier"] = 1.0
    scenario.loc[restore_rows, "capacity_factor"] = 1.0

    solver = build_flooded_solver(_WORKER_LINKS, _WORKER_OD, scenario)
    started = time.perf_counter()
    result = solver.solve(method="fw", relative_gap=_WORKER_GAP, max_iter=_WORKER_MAX_ITER)
    retry = False
    if not result.converged:
        retry = True
        result = solver.solve(method="fw", relative_gap=_WORKER_GAP, max_iter=max(3000, _WORKER_MAX_ITER))
    elapsed = time.perf_counter() - started
    return {
        "state_id": task["state_id"],
        "tstt": result.tstt,
        "normalized_tstt": result.tstt / BASELINE_TSTT,
        "excess_tstt_ratio": result.tstt / BASELINE_TSTT - 1.0,
        "log_tstt_ratio": math.log(result.tstt / BASELINE_TSTT),
        "sptt": result.sptt,
        "relative_gap": result.relative_gap,
        "iterations": result.iterations,
        "converged": bool(result.converged),
        "retry_used": retry,
        "elapsed_seconds": elapsed,
    }


def distribute_quotas(summary: pd.DataFrame, split_name: str, desired: int) -> dict[int, int]:
    part = summary.loc[summary.split == split_name, ["scenario_id", "severity", "closed_physical_links"]].copy()
    part["capacity"] = np.power(2, part.closed_physical_links.astype(int))
    capacity_total = int(part.capacity.sum())
    if desired > capacity_total:
        raise ValueError(f"{split_name}: desired {desired} unique states exceeds capacity {capacity_total}")

    quotas = {int(row.scenario_id): 0 for row in part.itertuples(index=False)}
    if split_name in {"train", "calibration", "test_id"}:
        mild = part.loc[part.severity == "mild"]
        for row in mild.itertuples(index=False):
            quotas[int(row.scenario_id)] = int(row.capacity)
        remaining = desired - sum(quotas.values())
        eligible = part.loc[part.severity == "moderate"].copy()
    else:
        remaining = desired
        eligible = part.copy()

    if remaining < 0:
        raise ValueError(f"{split_name}: desired count is smaller than the complete mild-state set")

    # Round-robin proportional allocation keeps every scenario represented while
    # respecting its finite number of unique recovery masks.
    scenario_ids = eligible.scenario_id.astype(int).tolist()
    capacities = dict(zip(eligible.scenario_id.astype(int), eligible.capacity.astype(int)))
    while remaining > 0:
        progressed = False
        for scenario_id in scenario_ids:
            if quotas[scenario_id] < capacities[scenario_id]:
                quotas[scenario_id] += 1
                remaining -= 1
                progressed = True
                if remaining == 0:
                    break
        if not progressed:
            raise RuntimeError(f"{split_name}: quota allocation stalled")
    return quotas


def canonical_mask(restored: Iterable[int]) -> tuple[int, ...]:
    return tuple(sorted(int(value) for value in restored))


def generate_masks(closed_ids: list[int], quota: int, seed: int) -> list[dict]:
    closed_ids = sorted(int(value) for value in closed_ids)
    capacity = 2 ** len(closed_ids)
    if quota == 0:
        return []
    if quota > capacity:
        raise ValueError("quota exceeds unique subset count")
    rng = np.random.default_rng(seed)
    records: dict[tuple[int, ...], dict] = {}

    def add(mask: Iterable[int], trajectory_id: int, stage: int, order: list[int]) -> None:
        key = canonical_mask(mask)
        if key not in records:
            records[key] = {
                "restored_physical_links": list(key),
                "source_trajectory_id": trajectory_id,
                "source_stage": stage,
                "source_restoration_order": order.copy(),
            }

    add([], 0, 0, closed_ids)
    if quota > 1:
        add(closed_ids, 0, len(closed_ids), closed_ids)
    trajectory_id = 1
    attempts = 0
    max_attempts = max(1000, quota * 100)
    while len(records) < quota and attempts < max_attempts:
        order = rng.permutation(closed_ids).astype(int).tolist()
        for stage in range(len(order) + 1):
            add(order[:stage], trajectory_id, stage, order)
            if len(records) >= quota:
                break
        trajectory_id += 1
        attempts += 1

    if len(records) < quota:
        # Deterministic exhaustive fallback, mainly used when quotas approach 2^n.
        for bits in range(capacity):
            mask = [closed_ids[index] for index in range(len(closed_ids)) if bits & (1 << index)]
            order = mask + [value for value in closed_ids if value not in mask]
            add(mask, trajectory_id, len(mask), order)
            trajectory_id += 1
            if len(records) >= quota:
                break
    if len(records) != quota:
        raise RuntimeError(f"generated {len(records)} masks; expected {quota}")
    return list(records.values())


def state_hash(depths: np.ndarray, restored_mask: np.ndarray) -> str:
    payload = np.concatenate([np.round(depths.astype(float), 9), restored_mask.astype(float)])
    return hashlib.sha256(payload.tobytes()).hexdigest()


def build_manifest(root: Path, counts: dict[str, int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    model_root = root / "SiouxFalls_UE_flood_models"
    connected = model_root / "data_connected"
    physical_path = root / "SiouxFalls_flood_benchmark" / "processed" / "physical_links.csv"
    physical = pd.read_csv(physical_path).sort_values("physical_link_id")
    link_ids = physical.physical_link_id.astype(int).tolist()
    summary = pd.read_csv(connected / "scenario_summary.csv")
    scenarios = pd.read_csv(connected / "flood_scenarios_physical_links.csv")
    grouped = {int(sid): frame.sort_values("physical_link_id").copy() for sid, frame in scenarios.groupby("scenario_id")}

    metadata_rows: list[dict] = []
    feature_rows: list[dict] = []
    for split_name, desired in counts.items():
        quotas = distribute_quotas(summary, split_name, desired)
        split_counter = 0
        for scenario_id in summary.loc[summary.split == split_name, "scenario_id"].astype(int):
            scenario = grouped[int(scenario_id)]
            closed_ids = scenario.loc[scenario.is_closed == 1, "physical_link_id"].astype(int).tolist()
            masks = generate_masks(closed_ids, quotas[int(scenario_id)], SPLIT_SEEDS[split_name] + int(scenario_id))
            depths = scenario.depth_m.to_numpy(dtype=float)
            initial_closed = scenario.is_closed.to_numpy(dtype=int)
            for local_index, item in enumerate(masks, start=1):
                split_counter += 1
                restored_ids = item["restored_physical_links"]
                restored_mask = np.array([1 if link_id in restored_ids else 0 for link_id in link_ids], dtype=int)
                remaining_ids = [value for value in closed_ids if value not in restored_ids]
                state_id = f"{split_name}-{scenario_id:03d}-{local_index:04d}"
                metadata_rows.append({
                    "state_id": state_id,
                    "scenario_id": int(scenario_id),
                    "split": split_name,
                    "severity": str(scenario.severity.iloc[0]),
                    "source_trajectory_id": int(item["source_trajectory_id"]),
                    "source_stage": int(item["source_stage"]),
                    "initial_closed_count": len(closed_ids),
                    "restored_count": len(restored_ids),
                    "remaining_closed_count": len(remaining_ids),
                    "recovery_fraction": len(restored_ids) / len(closed_ids) if closed_ids else 1.0,
                    "initial_closed_physical_links": ";".join(map(str, closed_ids)),
                    "restored_physical_links": restored_ids,
                    "remaining_closed_physical_links": ";".join(map(str, remaining_ids)),
                    "source_restoration_order": ";".join(map(str, item["source_restoration_order"])),
                    "state_hash": state_hash(depths, restored_mask),
                })
                feature = {"state_id": state_id}
                for link_id, depth, closed, restored in zip(link_ids, depths, initial_closed, restored_mask):
                    feature[f"d_depth_m_pl{link_id:03d}"] = float(depth)
                    feature[f"d_closed_pl{link_id:03d}"] = int(closed)
                    feature[f"r_restored_pl{link_id:03d}"] = int(restored)
                feature_rows.append(feature)
        if split_counter != desired:
            raise RuntimeError(f"{split_name}: built {split_counter}; expected {desired}")
    return pd.DataFrame(metadata_rows), pd.DataFrame(feature_rows)


def checkpoint_write(rows: list[dict], path: Path) -> None:
    frame = pd.DataFrame(rows).sort_values("state_id")
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def solve_manifest(
    manifest: pd.DataFrame,
    root: Path,
    out: Path,
    *,
    target_gap: float,
    max_iter: int,
    workers: int,
) -> pd.DataFrame:
    model_root = root / "SiouxFalls_UE_flood_models"
    processed = root / "SiouxFalls_flood_benchmark" / "processed"
    checkpoint = out / "recovery_state_results_checkpoint.csv"
    completed_rows: list[dict] = []
    completed_ids: set[str] = set()
    if checkpoint.exists():
        existing = pd.read_csv(checkpoint)
        completed_rows = existing.to_dict("records")
        completed_ids = set(existing.state_id.astype(str))

    tasks = []
    for row in manifest.itertuples(index=False):
        if row.state_id in completed_ids:
            continue
        tasks.append({
            "state_id": row.state_id,
            "scenario_id": int(row.scenario_id),
            "restored_physical_links": list(row.restored_physical_links),
        })

    if tasks:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_worker_init,
            initargs=(
                str(processed / "directed_links.csv"),
                str(processed / "od_long.csv"),
                str(model_root / "data_connected" / "flood_scenarios_directed_arcs.csv"),
                target_gap,
                max_iter,
            ),
        ) as executor:
            for index, result in enumerate(executor.map(_solve_task, tasks, chunksize=4), start=1):
                completed_rows.append(result)
                if index % 50 == 0:
                    checkpoint_write(completed_rows, checkpoint)
                    print(f"completed {len(completed_rows)}/{len(manifest)} states", flush=True)
        checkpoint_write(completed_rows, checkpoint)
    return pd.DataFrame(completed_rows).sort_values("state_id")


def make_quality_report(
    manifest: pd.DataFrame,
    features: pd.DataFrame,
    results: pd.DataFrame,
    counts: dict[str, int],
    out: Path,
) -> pd.DataFrame:
    merged = manifest.merge(results, on="state_id", validate="one_to_one")
    checks: list[dict] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    actual_counts = merged.groupby("split").size().to_dict()
    add("exact_split_counts", actual_counts == counts, json.dumps({key: int(value) for key, value in actual_counts.items()}, ensure_ascii=False))
    scenario_sets = {name: set(merged.loc[merged.split == name, "scenario_id"].astype(int)) for name in counts}
    intersections = sum(len(scenario_sets[a] & scenario_sets[b]) for i, a in enumerate(counts) for b in list(counts)[i + 1 :])
    add("scenario_level_no_leakage", intersections == 0, f"cross_split_scenario_intersections={intersections}")
    add("unique_state_hashes", manifest.state_hash.nunique() == len(manifest), f"unique={manifest.state_hash.nunique()}, rows={len(manifest)}")
    add("unique_state_ids", manifest.state_id.nunique() == len(manifest), f"unique={manifest.state_id.nunique()}, rows={len(manifest)}")
    add("all_results_present", len(results) == len(manifest) and results.state_id.nunique() == len(manifest), f"results={len(results)}, manifest={len(manifest)}")
    add("all_ue_converged", bool(results.converged.astype(bool).all()), f"converged={int(results.converged.astype(bool).sum())}/{len(results)}")
    add("gap_within_target", bool((results.relative_gap <= 5e-4 + 1e-12).all()), f"max_gap={results.relative_gap.max():.8g}")
    restored_columns = [column for column in features if column.startswith("r_restored_")]
    closed_columns = [column for column in features if column.startswith("d_closed_")]
    restored_values = features[restored_columns].to_numpy(dtype=int)
    closed_values = features[closed_columns].to_numpy(dtype=int)
    add("restored_subset_of_initial_closed", bool((restored_values <= closed_values).all()), "every restored flag belongs to an initially closed road")
    add("finite_labels", bool(np.isfinite(results[["tstt", "normalized_tstt", "log_tstt_ratio"]].to_numpy()).all()), "TSTT-derived labels are finite")

    pd.DataFrame(checks).to_csv(out / "recovery_dataset_quality_checks.csv", index=False, encoding="utf-8-sig")
    return pd.DataFrame(checks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate leak-free flood recovery-state UE samples")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--train", type=int, default=DEFAULT_COUNTS["train"])
    parser.add_argument("--calibration", type=int, default=DEFAULT_COUNTS["calibration"])
    parser.add_argument("--test-id", type=int, default=DEFAULT_COUNTS["test_id"])
    parser.add_argument("--test-severe", type=int, default=DEFAULT_COUNTS["test_severe"])
    parser.add_argument("--target-gap", type=float, default=5e-4)
    parser.add_argument("--max-iter", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--manifest-only", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    counts = {
        "train": args.train,
        "calibration": args.calibration,
        "test_id": args.test_id,
        "test_severe": args.test_severe,
    }

    manifest, features = build_manifest(args.root, counts)
    serializable_manifest = manifest.copy()
    serializable_manifest["restored_physical_links"] = serializable_manifest.restored_physical_links.map(lambda values: json.dumps(values, ensure_ascii=False))
    for column in ["initial_closed_physical_links", "remaining_closed_physical_links", "source_restoration_order"]:
        serializable_manifest[column] = serializable_manifest[column].map(
            lambda value: json.dumps([int(item) for item in str(value).split(";") if item], ensure_ascii=False)
        )
    serializable_manifest.to_csv(args.out / "recovery_state_manifest.csv", index=False, encoding="utf-8-sig")
    features.to_csv(args.out / "recovery_state_features.csv", index=False, encoding="utf-8-sig")

    if args.manifest_only:
        print(serializable_manifest.groupby(["split", "severity"]).size().to_string())
        return

    results = solve_manifest(
        manifest,
        args.root,
        args.out,
        target_gap=args.target_gap,
        max_iter=args.max_iter,
        workers=args.workers,
    )
    merged = serializable_manifest.merge(features, on="state_id", validate="one_to_one").merge(results, on="state_id", validate="one_to_one")
    column_order = [
        "state_id", "scenario_id", "split", "severity", "source_trajectory_id", "source_stage",
        "initial_closed_count", "restored_count", "remaining_closed_count", "recovery_fraction",
        "initial_closed_physical_links", "restored_physical_links", "remaining_closed_physical_links",
        "source_restoration_order", "state_hash", "tstt", "normalized_tstt", "excess_tstt_ratio",
        "log_tstt_ratio", "sptt", "relative_gap", "iterations", "converged", "retry_used", "elapsed_seconds",
    ]
    feature_columns = [column for column in merged if column not in column_order]
    merged = merged[column_order + feature_columns]
    merged.to_csv(args.out / "recovery_states_all.csv", index=False, encoding="utf-8-sig")
    for split_name in counts:
        split_frame = merged.loc[merged.split == split_name].copy()
        split_frame.to_csv(args.out / f"recovery_states_{split_name}.csv", index=False, encoding="utf-8-sig")

    quality = make_quality_report(manifest, features, results, counts, args.out)
    summary = merged.groupby(["split", "severity"], as_index=False).agg(
        state_count=("state_id", "size"),
        scenario_count=("scenario_id", "nunique"),
        mean_initial_closed=("initial_closed_count", "mean"),
        mean_remaining_closed=("remaining_closed_count", "mean"),
        mean_tstt=("tstt", "mean"),
        min_tstt=("tstt", "min"),
        max_tstt=("tstt", "max"),
        max_relative_gap=("relative_gap", "max"),
        mean_elapsed_seconds=("elapsed_seconds", "mean"),
    )
    summary.to_csv(args.out / "recovery_dataset_summary.csv", index=False, encoding="utf-8-sig")
    config = {
        "random_seeds": SPLIT_SEEDS,
        "requested_counts": counts,
        "ue_method": "Frank-Wolfe",
        "ue_target_relative_gap": args.target_gap,
        "ue_max_iterations": args.max_iter,
        "ue_retry_max_iterations": max(3000, args.max_iter),
        "baseline_tstt": BASELINE_TSTT,
        "restoration_semantics": "Restored initially-closed physical links return to dry baseline free-flow time and capacity; non-closed wet links retain the scenario background disruption.",
        "split_rule": "All states from one scenario_id remain in exactly one split.",
        "feature_definition": "x=[d,r], where d contains 38 physical-link flood depths and closure flags, and r contains 38 restoration flags.",
    }
    (args.out / "recovery_dataset_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nSummary:\n", summary.to_string(index=False))
    print("\nQuality checks:\n", quality.to_string(index=False))


if __name__ == "__main__":
    main()
