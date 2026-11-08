from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd


BUDGET_LEVELS = (64, 128, 256, 512)
QUANTILE_PRIORITY = {q: i for i, q in enumerate((1, 5, 10, 3, 8, 2, 7, 4, 6, 9))}


def sequence_id(sequence: tuple[int, ...]) -> str:
    return hashlib.sha256("|".join(map(str, sequence)).encode("ascii")).hexdigest()


def parse_sequence(value: str) -> tuple[int, ...]:
    return tuple(int(v) for v in str(value).split("|"))


def load_interface(path: Path):
    spec = importlib.util.spec_from_file_location("week3_interfaces_day5", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load formal interface: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class BudgetedSearch:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.sid = int(args.scenario)
        self.out = Path(args.output_dir) / f"scenario_{self.sid}"
        self.out.mkdir(parents=True, exist_ok=True)
        self.api = load_interface(Path(args.interface))
        self.cache_path = Path(args.cache_path) if args.cache_path else self.out / f"ue_cache_live_s{self.sid}.sqlite"
        self.cache_namespace = args.cache_namespace or f"final_live_ue_s{self.sid}"
        self.ue = self.api.UEInterface(
            cache_path=self.cache_path,
            model_root=args.model_root,
            cache_namespace=self.cache_namespace,
            dependency_paths=[Path(value) for value in args.python_dependency],
        )

        all_scenarios = pd.read_csv(args.scenario_physical)
        self.physical = all_scenarios[all_scenarios["scenario_id"].astype(int) == self.sid].copy()
        self.physical = self.physical.sort_values("physical_link_id").reset_index(drop=True)
        if len(self.physical) != 38:
            raise ValueError(f"Scenario {self.sid}: expected 38 physical links, found {len(self.physical)}")

        development = json.loads(Path(args.scenario_metadata).read_text(encoding="utf-8"))
        scenario_meta = next(row for row in development["scenarios"] if int(row["scenario_id"]) == self.sid)
        self.roads = tuple(int(v) for v in scenario_meta["selected_recoverable_roads"])
        self.road_to_bit = {road: i for i, road in enumerate(self.roads)}

        screened = pd.read_csv(args.screened_candidates)
        self.screened = screened[screened["scenario_id"].astype(int) == self.sid].copy()
        self.screened["seq_tuple"] = self.screened["sequence"].map(parse_sequence)
        if self.screened["candidate_id"].duplicated().any():
            raise ValueError(f"Scenario {self.sid}: duplicate candidate_id")
        for seq in self.screened["seq_tuple"]:
            if len(seq) != 10 or set(seq) != set(self.roads):
                raise ValueError(f"Scenario {self.sid}: invalid candidate sequence {seq}")

        self.reserve = self.screened[self.screened["screening_tier"] == "structural_reserve"].copy()
        self.primary = self.screened[self.screened["screening_tier"] == "primary_shortlist"].copy()
        self.calls = 0
        self.requests = 0
        self.cache_hits = 0
        self.physical_cache_hits = 0
        self.state_by_hash: dict[str, dict] = {}
        self.state_rows: list[dict] = []
        self.result_rows: list[dict] = []
        self.local_rows: list[dict] = []
        self.result_by_sequence: dict[tuple[int, ...], dict] = {}
        self.seed_attempted: set[tuple[int, ...]] = set()
        self.local_attempted: set[tuple[int, ...]] = set()
        self._seed_queue: list[dict] = []
        self.started = time.perf_counter()

    def mask_for(self, restored: tuple[int, ...] | list[int]) -> int:
        mask = 0
        for road in restored:
            mask |= 1 << self.road_to_bit[int(road)]
        return mask

    def restored_for(self, mask: int) -> tuple[int, ...]:
        return tuple(sorted(road for road, bit in self.road_to_bit.items() if mask & (1 << bit)))

    def state_hash(self, mask: int) -> str:
        restored_mask = self.api.restored_mask_from_links(self.restored_for(mask))
        return self.api.get_state_hash(
            self.physical["depth_m"].to_numpy(float),
            self.physical["is_closed"].to_numpy(np.uint8),
            restored_mask,
        )

    def evaluate_mask(self, mask: int, phase: str, reason: str, sequence: tuple[int, ...] | None = None) -> dict:
        key = self.state_hash(mask)
        self.requests += 1
        cached = self.state_by_hash.get(key)
        if cached is not None:
            self.cache_hits += 1
            self.state_rows.append({
                "scenario_id": self.sid, "request_index": self.requests, "ue_calls_after": self.calls,
                "budget_level_reached": max((b for b in BUDGET_LEVELS if b <= self.calls), default=0),
                "phase": phase, "reason": reason, "state_hash": key, "subset_mask": mask,
                "restored_count": int(mask.bit_count()), "restored_links": "|".join(map(str, self.restored_for(mask))),
                "cache_hit": True, "loss": cached["loss"], "tstt": cached["tstt"],
                "relative_gap": cached["relative_gap"], "iterations": cached["iterations"],
                "elapsed_seconds": 0.0, "sequence_id": sequence_id(sequence) if sequence else "",
            })
            return cached
        if self.calls >= self.args.max_budget:
            raise RuntimeError("UE budget exhausted before a cache miss")
        restored = self.restored_for(mask)
        result = None
        last_error = None
        try:
            for max_iter in (1000, 3000, 10000):
                self.api.MAX_UE_ITERATIONS = max_iter
                try:
                    result = self.ue.run_ue(self.physical, restored, f"scenario_{self.sid}")
                    break
                except RuntimeError as exc:
                    if "UE failed to converge" not in str(exc):
                        raise
                    last_error = exc
        finally:
            self.api.MAX_UE_ITERATIONS = 1000
        if result is None:
            raise RuntimeError("UE failed after frozen 1000/3000/10000 iteration safeguard") from last_error
        physical_cache_hit = bool(result.cache_hit)
        if physical_cache_hit and not self.args.allow_prewarmed_cache:
            raise RuntimeError("Formal run requires a fresh cache; pre-existing physical state found")
        if physical_cache_hit:
            self.physical_cache_hits += 1
        self.calls += 1
        row = asdict(result)
        self.state_by_hash[key] = row
        self.state_rows.append({
            "scenario_id": self.sid, "request_index": self.requests, "ue_calls_after": self.calls,
            "budget_level_reached": max((b for b in BUDGET_LEVELS if b <= self.calls), default=0),
            "phase": phase, "reason": reason, "state_hash": key, "subset_mask": mask,
            "restored_count": int(mask.bit_count()), "restored_links": "|".join(map(str, restored)),
            "cache_hit": False, "physical_cache_hit": physical_cache_hit,
            "loss": result.loss, "tstt": result.tstt,
            "relative_gap": result.relative_gap, "iterations": result.iterations,
            "elapsed_seconds": result.elapsed_seconds, "sequence_id": sequence_id(sequence) if sequence else "",
        })
        return row

    def masks_for_sequence(self, sequence: tuple[int, ...]) -> list[int]:
        masks = [0]
        current = 0
        for road in sequence[:9]:
            current |= 1 << self.road_to_bit[road]
            masks.append(current)
        return masks

    def missing_count(self, sequence: tuple[int, ...]) -> int:
        return sum(self.state_hash(mask) not in self.state_by_hash for mask in self.masks_for_sequence(sequence))

    def metadata_for(self, sequence: tuple[int, ...]) -> dict:
        rows = self.screened[self.screened["seq_tuple"] == sequence]
        if rows.empty:
            return {
                "candidate_id": sequence_id(sequence), "screening_tier": "local_search",
                "channel": "local_search", "primary_source": "local_search", "proxy_rank": math.nan,
                "proxy_objective_mean": math.nan, "prefix_2": "|".join(map(str, sequence[:2])),
                "prefix_3": "|".join(map(str, sequence[:3])),
            }
        row = rows.iloc[0]
        return {key: row.get(key, "") for key in (
            "candidate_id", "screening_tier", "channel", "primary_source", "proxy_rank",
            "proxy_objective_mean", "prefix_2", "prefix_3",
        )}

    def evaluate_sequence(self, sequence: tuple[int, ...], phase: str, reason: str,
                          parent: tuple[int, ...] | None = None, move: str = "") -> dict | None:
        if sequence in self.result_by_sequence:
            return self.result_by_sequence[sequence]
        missing = self.missing_count(sequence)
        if missing > self.args.max_budget - self.calls:
            return None
        before = self.calls
        stage_losses = []
        for stage, mask in enumerate(self.masks_for_sequence(sequence)):
            state = self.evaluate_mask(mask, phase, f"{reason}:R{stage}", sequence)
            stage_losses.append(float(state["loss"]))
        objective = float(np.mean(stage_losses))
        meta = self.metadata_for(sequence)
        result = {
            "scenario_id": self.sid, "sequence_id": sequence_id(sequence), "candidate_id": meta["candidate_id"],
            "sequence": "|".join(map(str, sequence)), "evaluation_phase": phase, "evaluation_reason": reason,
            "screening_tier": meta["screening_tier"], "channel": meta["channel"],
            "primary_source": meta["primary_source"], "proxy_rank": meta["proxy_rank"],
            "proxy_objective_mean": meta["proxy_objective_mean"], "prefix_2": meta["prefix_2"],
            "prefix_3": meta["prefix_3"], "ue_objective": objective,
            "new_ue_calls": self.calls - before, "completion_budget": self.calls,
            "all_states_converged": True, "max_relative_gap": max(
                float(self.state_by_hash[self.state_hash(mask)]["relative_gap"])
                for mask in self.masks_for_sequence(sequence)
            ),
            "parent_sequence_id": sequence_id(parent) if parent else "", "move": move,
        }
        self.result_rows.append(result)
        self.result_by_sequence[sequence] = result
        return result

    def evaluate_prefix2(self) -> list[str]:
        p2_table = self.reserve[["prefix_2", "prefix_2_cluster_rank"]].drop_duplicates().copy()
        p2_table["prefix_2_cluster_rank"] = pd.to_numeric(p2_table["prefix_2_cluster_rank"])
        p2_table = p2_table.sort_values(["prefix_2_cluster_rank", "prefix_2"])
        prefixes = p2_table["prefix_2"].astype(str).tolist()
        self.evaluate_mask(0, "A_prefix2", "common_R0")
        for prefix in prefixes:
            roads = parse_sequence(prefix)
            self.evaluate_mask(self.mask_for(roads[:1]), "A_prefix2", f"prefix2:{prefix}:R1")
            self.evaluate_mask(self.mask_for(roads), "A_prefix2", f"prefix2:{prefix}:R2")
        return prefixes

    def prefix2_scores(self, prefixes: list[str]) -> list[str]:
        scores = []
        for prefix in prefixes:
            roads = parse_sequence(prefix)
            score = self.state_by_hash[self.state_hash(self.mask_for(roads[:1]))]["loss"]
            score += self.state_by_hash[self.state_hash(self.mask_for(roads))]["loss"]
            scores.append((float(score), prefix))
        return [prefix for _, prefix in sorted(scores)]

    def evaluate_prefix3_for(self, prefixes: list[str], phase: str) -> None:
        for p2 in prefixes:
            groups = sorted(self.reserve[self.reserve["prefix_2"].astype(str) == p2]["prefix_3"].dropna().astype(str).unique())
            for p3 in groups:
                self.evaluate_mask(self.mask_for(parse_sequence(p3)), phase, f"prefix3:{p3}:R3")

    def build_seed_queue(self) -> None:
        p3_scores = []
        for p3 in self.reserve["prefix_3"].dropna().astype(str).unique():
            roads = parse_sequence(p3)
            key = self.state_hash(self.mask_for(roads))
            if key not in self.state_by_hash:
                continue
            score = sum(float(self.state_by_hash[self.state_hash(self.mask_for(roads[:k]))]["loss"]) for k in (1, 2, 3))
            p3_scores.append((score, p3))
        p3_rank = {p3: i for i, (_, p3) in enumerate(sorted(p3_scores), start=1)}

        rows = []
        sources = sorted(self.reserve["primary_source"].dropna().astype(str).unique())
        source_rank = {source: i for i, source in enumerate(sources)}
        for _, row in self.reserve.iterrows():
            p3 = str(row["prefix_3"])
            if p3 not in p3_rank:
                continue
            q = int(row["source_quantile_index"]) if pd.notna(row["source_quantile_index"]) else 99
            rotated_source = (source_rank.get(str(row["primary_source"]), 99) - p3_rank[p3]) % max(1, len(sources))
            rows.append({
                "sequence": row["seq_tuple"], "reason": "structural_reserve_stratified",
                "sort": (p3_rank[p3], QUANTILE_PRIORITY.get(q, 99), rotated_source, int(row["proxy_rank"])),
            })

        for _, row in self.primary.iterrows():
            p3 = str(row["prefix_3"])
            if p3 in p3_rank:
                channel_order = {"proxy_top": 0, "ensemble_disagreement": 1, "sequence_diversity": 2,
                                 "heuristic": 3, "random": 4}.get(str(row["channel"]), 9)
                rows.append({
                    "sequence": row["seq_tuple"], "reason": "primary_shortlist_channel",
                    "sort": (p3_rank[p3], channel_order, 50, int(row["proxy_rank"])),
                })
        rows.sort(key=lambda x: x["sort"])
        seen = set()
        self._seed_queue = []
        for row in rows:
            if row["sequence"] not in seen:
                seen.add(row["sequence"])
                self._seed_queue.append(row)

    def next_seed_that_fits(self, remaining: int) -> dict | None:
        for row in self._seed_queue:
            seq = row["sequence"]
            if seq in self.seed_attempted or seq in self.result_by_sequence:
                continue
            missing = self.missing_count(seq)
            if missing <= remaining:
                self.seed_attempted.add(seq)
                return row
        return None

    @staticmethod
    def move_neighbors(sequence: tuple[int, ...]):
        n = len(sequence)
        for i in range(n - 1):
            seq = list(sequence); seq[i], seq[i + 1] = seq[i + 1], seq[i]
            yield tuple(seq), "adjacent_swap", i, i + 1
        for i in range(5):
            for j in range(i + 2, n):
                seq = list(sequence); seq[i], seq[j] = seq[j], seq[i]
                yield tuple(seq), "arbitrary_swap", i, j
        for i in range(5):
            for j in range(n):
                if i == j:
                    continue
                seq = list(sequence); value = seq.pop(i); seq.insert(j, value)
                yield tuple(seq), "insertion", i, j

    def local_search(self, target_calls: int) -> None:
        rounds_without_improvement = 0
        round_no = 0
        while self.calls < target_calls and rounds_without_improvement < 2 and self.result_by_sequence:
            round_no += 1
            parents = sorted(self.result_by_sequence.items(), key=lambda kv: kv[1]["ue_objective"])[:5]
            best_before = parents[0][1]["ue_objective"]
            candidates = []
            for parent_seq, parent_row in parents:
                for seq, move, i, j in self.move_neighbors(parent_seq):
                    if seq in self.local_attempted or seq in self.result_by_sequence:
                        continue
                    candidates.append((self.missing_count(seq), move != "adjacent_swap", i, j,
                                       parent_row["ue_objective"], parent_seq, seq, move))
            candidates.sort(key=lambda x: x[:5])
            evaluated = 0
            for missing, _, i, j, parent_obj, parent_seq, seq, move in candidates:
                if self.calls >= target_calls:
                    break
                if missing > target_calls - self.calls:
                    continue
                self.local_attempted.add(seq)
                row = self.evaluate_sequence(seq, "D_local_search", f"round_{round_no}", parent_seq, f"{move}:{i}->{j}")
                if row is None:
                    continue
                evaluated += 1
                improvement = float(parent_obj - row["ue_objective"])
                self.local_rows.append({
                    "scenario_id": self.sid, "round": round_no, "parent_sequence_id": sequence_id(parent_seq),
                    "child_sequence_id": row["sequence_id"], "move": move, "position_from": i + 1,
                    "position_to": j + 1, "parent_ue_objective": parent_obj,
                    "child_ue_objective": row["ue_objective"], "absolute_improvement": improvement,
                    "relative_improvement": improvement / parent_obj if parent_obj else 0.0,
                    "accepted_as_global_best": row["ue_objective"] < min(r["ue_objective"] for s, r in self.result_by_sequence.items() if s != seq),
                    "new_ue_calls": row["new_ue_calls"], "completion_budget": row["completion_budget"],
                })
            best_after = min(row["ue_objective"] for row in self.result_by_sequence.values())
            relative = (best_before - best_after) / best_before if best_before else 0.0
            if evaluated == 0 or relative < 0.001:
                rounds_without_improvement += 1
            else:
                rounds_without_improvement = 0

    def run_interval(self, target: int, seed_share: float) -> None:
        seed_cutoff = self.calls + int((target - self.calls) * seed_share)
        while self.calls < seed_cutoff:
            seed = self.next_seed_that_fits(seed_cutoff - self.calls)
            if seed is None:
                break
            self.evaluate_sequence(seed["sequence"], "C_true_ue_reranking", seed["reason"])
        self.local_search(target)
        while self.calls < target:
            seed = self.next_seed_that_fits(target - self.calls)
            if seed is not None:
                self.evaluate_sequence(seed["sequence"], "C_true_ue_reranking", seed["reason"])
                self.local_search(target)
                continue
            if not self.fill_one_state(target):
                raise RuntimeError(f"Scenario {self.sid}: unable to spend the exact budget {target}")

    def fill_one_state(self, target: int) -> bool:
        if self.calls >= target:
            return False
        ordered = self.screened.sort_values(["screening_tier", "proxy_rank"], kind="stable")
        for seq in ordered["seq_tuple"]:
            current = 0
            for stage, road in enumerate(seq[:9], start=1):
                current |= 1 << self.road_to_bit[road]
                if self.state_hash(current) not in self.state_by_hash:
                    self.evaluate_mask(current, "budget_fill", f"structured_unseen_prefix:R{stage}", seq)
                    return True
        return False

    def snapshots(self) -> list[dict]:
        rows = []
        for budget in BUDGET_LEVELS:
            eligible = [row for row in self.result_rows if int(row["completion_budget"]) <= budget]
            if not eligible:
                rows.append({"scenario_id": self.sid, "ue_budget": budget, "complete_sequence_count": 0})
                continue
            best = min(eligible, key=lambda row: row["ue_objective"])
            rows.append({
                "scenario_id": self.sid, "ue_budget": budget, "complete_sequence_count": len(eligible),
                "best_sequence_id": best["sequence_id"], "best_sequence": best["sequence"],
                "best_ue_objective": best["ue_objective"], "best_screening_tier": best["screening_tier"],
                "best_primary_source": best["primary_source"], "best_evaluation_phase": best["evaluation_phase"],
                "best_completion_budget": best["completion_budget"],
            })
        return rows

    def run(self) -> None:
        prefixes = self.evaluate_prefix2()
        ranked = self.prefix2_scores(prefixes)
        self.evaluate_prefix3_for(ranked[:4], "B_prefix3_initial")
        self.build_seed_queue()
        self.run_interval(64, 0.55)

        self.evaluate_prefix3_for(ranked[4:], "B_prefix3_remaining")
        self.build_seed_queue()
        self.run_interval(128, 0.50)
        self.run_interval(256, 0.50)
        self.run_interval(512, 0.50)

        cache_rows = self.ue.cache.count()
        cache_ok = cache_rows >= self.args.max_budget if self.args.allow_prewarmed_cache else cache_rows == self.args.max_budget
        if self.calls != self.args.max_budget or not cache_ok:
            raise RuntimeError(f"Scenario {self.sid}: cache/budget mismatch {self.calls}/{cache_rows}")
        elapsed = time.perf_counter() - self.started
        pd.DataFrame(self.state_rows).to_csv(self.out / "ue_state_audit_log.csv.gz", index=False, compression="gzip")
        pd.DataFrame(self.result_rows).sort_values(["completion_budget", "ue_objective"]).to_csv(
            self.out / "ue_reranking_results.csv", index=False)
        pd.DataFrame(self.local_rows).to_csv(self.out / "local_search_history.csv", index=False)
        pd.DataFrame(self.snapshots()).to_csv(self.out / "budget_snapshots_pre_reference.csv", index=False)
        report = {
            "schema_version": "week3-day5-scenario-v1.0", "scenario_id": self.sid,
            "budget_unit": "unique recovery-state UE cache miss", "budget_levels": list(BUDGET_LEVELS),
            "maximum_budget": self.args.max_budget, "unique_ue_calls": self.calls,
            "cache_rows": self.ue.cache.count(), "state_requests": self.requests,
            "cache_hits": self.cache_hits, "request_cache_hit_rate": self.cache_hits / self.requests,
            "physical_cache_hits": self.physical_cache_hits,
            "prewarmed_cache_smoke_mode": bool(self.args.allow_prewarmed_cache),
            "fully_evaluated_sequences": len(self.result_rows),
            "local_search_evaluations": len(self.local_rows), "all_ue_converged": True,
            "max_relative_gap": max(float(row["relative_gap"]) for row in self.state_rows),
            "wall_seconds": elapsed, "exact_reference_access_during_search": False,
            "cache_namespace": self.cache_namespace,
            "cache_path": str(self.cache_path),
        }
        (self.out / "budget_usage_pre_reference.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self.ue.cache.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--screened-candidates", required=True)
    parser.add_argument("--scenario-physical", required=True)
    parser.add_argument("--scenario-metadata", required=True)
    parser.add_argument("--interface", required=True)
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--cache-path")
    parser.add_argument("--cache-namespace")
    parser.add_argument("--python-dependency", action="append", default=[])
    parser.add_argument("--allow-prewarmed-cache", action="store_true")
    parser.add_argument("--max-budget", type=int, default=512, choices=[512])
    args = parser.parse_args()
    BudgetedSearch(args).run()


if __name__ == "__main__":
    main()
