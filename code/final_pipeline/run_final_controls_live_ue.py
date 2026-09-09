from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd


BUDGETS = (64, 128, 256, 512)
METHODS = (
    "traditional_heuristic_ue",
    "surrogate_only",
    "random_ue",
    "proxy_topk_ue",
    "no_local_search",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class SharedLiveUE:
    def __init__(self, interface_path: Path, model_root: Path, cache_path: Path, namespace: str,
                 physical: pd.DataFrame, scenario_id: int, roads: list[int],
                 dependency_paths: list[Path] | None = None):
        self.api = load_module("final_live_interfaces", interface_path)
        self.interface = self.api.UEInterface(
            cache_path=cache_path,
            model_root=model_root,
            cache_namespace=namespace,
            dependency_paths=dependency_paths or [],
        )
        self.physical = physical.sort_values("physical_link_id").reset_index(drop=True)
        self.sid = int(scenario_id)
        self.roads = tuple(map(int, roads))
        self.road_to_bit = {road: bit for bit, road in enumerate(self.roads)}
        self.physical_events: list[dict] = []

    def restored_for(self, mask: int) -> tuple[int, ...]:
        return tuple(sorted(road for road, bit in self.road_to_bit.items() if mask & (1 << bit)))

    def evaluate(self, mask: int, method: str, reason: str) -> dict:
        restored = self.restored_for(mask)
        result = None
        last_error = None
        started = time.perf_counter()
        try:
            for max_iter in (1000, 3000, 10000):
                self.api.MAX_UE_ITERATIONS = max_iter
                try:
                    result = self.interface.run_ue(self.physical, restored, f"final_scenario_{self.sid}")
                    break
                except RuntimeError as exc:
                    if "UE failed to converge" not in str(exc):
                        raise
                    last_error = exc
        finally:
            self.api.MAX_UE_ITERATIONS = 1000
        if result is None:
            raise RuntimeError("UE failed after frozen iteration safeguards") from last_error
        row = {
            "scenario_id": self.sid,
            "method": method,
            "reason": reason,
            "subset_mask": int(mask),
            "restored_count": int(mask.bit_count()),
            "restored_links": "|".join(map(str, restored)),
            "state_hash": result.state_hash,
            "loss": float(result.loss),
            "tstt": float(result.tstt),
            "relative_gap": float(result.relative_gap),
            "iterations": int(result.iterations),
            "physical_cache_hit": bool(result.cache_hit),
            "request_wall_seconds": time.perf_counter() - started,
        }
        self.physical_events.append(row)
        return row

    def close(self) -> None:
        self.interface.cache.close()


def make_live_search(reference, backend: SharedLiveUE, candidates: pd.DataFrame, method: str, local_enabled: bool):
    class LiveSearch(reference.OracleSearch):
        def __init__(self):
            self.sid = backend.sid
            self.roads = backend.roads
            self.road_to_bit = backend.road_to_bit
            self.cost: dict[int, float] = {}
            self.candidates = candidates.copy()
            if "seq_tuple" not in self.candidates:
                self.candidates["seq_tuple"] = self.candidates["sequence"].map(reference.seq_tuple)
            self.method = method
            self.local_enabled = local_enabled
            self.queried: set[int] = set()
            self.query_rows: list[dict] = []
            self.results: dict[tuple[int, ...], dict] = {}
            self.local_attempted: set[tuple[int, ...]] = set()
            self.seed_attempted: set[tuple[int, ...]] = set()
            self.seed_queue: list[dict] = []

        def query(self, mask: int, reason: str) -> float:
            if mask not in self.queried:
                live = backend.evaluate(mask, self.method, reason)
                self.queried.add(mask)
                self.cost[mask] = float(live["loss"])
                self.query_rows.append({
                    **live,
                    "method_query_index": len(self.queried),
                    "information_budget_unit": "method-specific unique restored subset",
                })
            return self.cost[mask]

    return LiveSearch()


def masks_for_sequence(sequence: tuple[int, ...], roads: list[int]) -> list[int]:
    road_to_bit = {road: bit for bit, road in enumerate(roads)}
    masks = [0]
    current = 0
    for road in sequence[:9]:
        current |= 1 << road_to_bit[road]
        masks.append(current)
    return masks


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all five formal controls through live UE before exact-reference construction.")
    parser.add_argument("--scenario", type=int, required=True)
    parser.add_argument("--candidate-pool", required=True)
    parser.add_argument("--screened-candidates", required=True)
    parser.add_argument("--scenario-physical", required=True)
    parser.add_argument("--scenario-metadata", required=True)
    parser.add_argument("--interface", required=True)
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--shared-cache", required=True)
    parser.add_argument("--cache-namespace", required=True)
    parser.add_argument("--python-dependency", action="append", default=[])
    parser.add_argument("--reference-logic", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--random-seed-base", type=int, default=2026080704)
    args = parser.parse_args()

    sid = int(args.scenario)
    output = Path(args.output_dir) / f"scenario_{sid}"
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    pool_path = Path(args.candidate_pool)
    screened_path = Path(args.screened_candidates)
    physical_path = Path(args.scenario_physical)
    metadata_path = Path(args.scenario_metadata)
    pool = pd.read_csv(pool_path)
    pool = pool[pool["scenario_id"].astype(int) == sid].copy()
    screened = pd.read_csv(screened_path)
    screened = screened[screened["scenario_id"].astype(int) == sid].copy()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    meta = next(row for row in metadata["scenarios"] if int(row["scenario_id"]) == sid)
    roads = list(map(int, meta["selected_recoverable_roads"]))
    physical_all = pd.read_csv(physical_path)
    physical = physical_all[physical_all["scenario_id"].astype(int) == sid].copy()
    if len(roads) != 10 or len(set(roads)) != 10 or len(physical) != 38:
        raise ValueError("Invalid frozen scenario or road selection")
    reference = load_module("final_control_reference_logic", Path(args.reference_logic))
    pool["seq_tuple"] = pool["sequence"].map(reference.seq_tuple)
    screened["seq_tuple"] = screened["sequence"].map(reference.seq_tuple)
    backend = SharedLiveUE(Path(args.interface), Path(args.model_root), Path(args.shared_cache),
                           args.cache_namespace, physical, sid, roads,
                           [Path(value) for value in args.python_dependency])
    results = []
    query_frames = []
    method_freezes = {}
    try:
        for method in METHODS:
            method_started = time.perf_counter()
            if method == "surrogate_only":
                selected = pool.sort_values(["proxy_rank", "candidate_id"]).iloc[0]
                sequence = reference.seq_tuple(selected["sequence"])
                frozen_sequence_id = reference.seq_id(sequence)
                validation_rows = [backend.evaluate(mask, method, f"frozen_proxy_rank_1_validation:R{stage}")
                                   for stage, mask in enumerate(masks_for_sequence(sequence, roads))]
                objective = float(np.mean([row["loss"] for row in validation_rows]))
                snapshots = [{
                    "ue_budget": budget,
                    "unique_ue_calls": 0,
                    "validation_state_queries": len(validation_rows),
                    "complete_sequence_count": 1,
                    "best_sequence": selected["sequence"],
                    "best_sequence_id": frozen_sequence_id,
                    "best_ue_objective": objective,
                    "best_completion_budget": 0,
                    "best_origin": "proxy_rank_1_frozen_before_ue_validation",
                } for budget in BUDGETS]
                method_queries = pd.DataFrame([{**row, "method_query_index": index + 1,
                                                "information_budget_unit": "validation-only; no UE feedback"}
                                               for index, row in enumerate(validation_rows)])
            else:
                local_enabled = method == "no_local_search" and False
                search = make_live_search(reference, backend, screened, method, local_enabled)
                if method == "traditional_heuristic_ue":
                    queue = screened[(screened["screening_tier"] == "primary_shortlist") &
                                     (screened["channel"] == "heuristic")].sort_values("channel_rank")
                    snapshots = search.run_simple(reference.queue_from(queue), use_local=False)
                elif method == "random_ue":
                    queue = pool[pool["primary_source"] == "random"].sample(
                        frac=1.0, random_state=args.random_seed_base + sid)
                    snapshots = search.run_simple(reference.queue_from(queue), use_local=False)
                elif method == "proxy_topk_ue":
                    snapshots = search.run_simple(reference.queue_from(pool.sort_values(["proxy_rank", "candidate_id"])), use_local=False)
                elif method == "no_local_search":
                    snapshots = search.run_full()
                else:
                    raise AssertionError(method)
                method_queries = pd.DataFrame(search.query_rows)
            method_rows = pd.DataFrame([{"scenario_id": sid, "method": method, **row} for row in snapshots])
            method_result_path = output / f"{method}_results_pre_reference.csv"
            method_query_path = output / f"{method}_query_ledger.csv.gz"
            method_rows.to_csv(method_result_path, index=False, encoding="utf-8-sig")
            method_queries.to_csv(method_query_path, index=False, compression={"method": "gzip", "compresslevel": 9, "mtime": 0})
            freeze = {
                "schema_version": "final-live-control-method-freeze-v1.0",
                "scenario_id": sid,
                "method": method,
                "results_sha256": sha256(method_result_path),
                "query_ledger_sha256": sha256(method_query_path),
                "candidate_pool_sha256": sha256(pool_path),
                "screened_candidates_sha256": sha256(screened_path),
                "scenario_physical_sha256": sha256(physical_path),
                "scenario_metadata_sha256": sha256(metadata_path),
                "exact_reference_read": False,
                "method_output_frozen_before_exact_reference": True,
                "wall_seconds": time.perf_counter() - method_started,
            }
            freeze_path = output / f"{method}_freeze.json"
            freeze_path.write_text(json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8")
            method_freezes[method] = {"path": freeze_path.name, "sha256": sha256(freeze_path)}
            results.append(method_rows)
            query_frames.append(method_queries)
            print(json.dumps({"event": "live_control_frozen", "scenario_id": sid, "method": method,
                              "method_queries": len(method_queries)}), flush=True)
    finally:
        backend.close()

    aggregate_path = output / "formal_control_results_pre_reference.csv"
    physical_path_out = output / "physical_ue_request_audit.csv.gz"
    pd.concat(results, ignore_index=True).to_csv(aggregate_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(backend.physical_events).to_csv(
        physical_path_out, index=False, compression={"method": "gzip", "compresslevel": 9, "mtime": 0})
    aggregate_freeze = {
        "schema_version": "final-live-controls-aggregate-freeze-v1.0",
        "scenario_id": sid,
        "methods": method_freezes,
        "all_five_controls_frozen": set(method_freezes) == set(METHODS),
        "aggregate_results_sha256": sha256(aggregate_path),
        "physical_ue_request_audit_sha256": sha256(physical_path_out),
        "complete_subset_cost_table_read": False,
        "exact_dp_solution_read": False,
        "next_authorized_action": "exact reference may run only after full-method freeze is also verified",
    }
    aggregate_freeze_path = output / "controls_output_freeze.json"
    aggregate_freeze_path.write_text(json.dumps(aggregate_freeze, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "pass", "output": str(output), "controls": len(method_freezes)}, indent=2))


if __name__ == "__main__":
    main()
