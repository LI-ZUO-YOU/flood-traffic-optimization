from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


BUDGETS = (64, 128, 256, 512)
SEED = 2026080506
QUANTILE_PRIORITY = {q: i for i, q in enumerate((1, 5, 10, 3, 8, 2, 7, 4, 6, 9))}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def seq_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(v) for v in str(value).split("|"))


def seq_id(sequence: tuple[int, ...]) -> str:
    return hashlib.sha256("|".join(map(str, sequence)).encode("ascii")).hexdigest()


class OracleSearch:
    def __init__(self, sid: int, roads: list[int], cost_frame: pd.DataFrame, candidates: pd.DataFrame,
                 method: str, local_enabled: bool):
        self.sid = sid
        self.roads = tuple(map(int, roads))
        self.road_to_bit = {road: i for i, road in enumerate(self.roads)}
        self.cost = {int(row.subset_mask): float(row.loss) for row in cost_frame.itertuples(index=False)}
        if set(self.cost) != set(range(1024)):
            raise ValueError(f"Scenario {sid}: incomplete oracle")
        self.candidates = candidates.copy()
        if "seq_tuple" not in self.candidates:
            self.candidates["seq_tuple"] = self.candidates["sequence"].map(seq_tuple)
        self.method = method
        self.local_enabled = local_enabled
        self.queried: set[int] = set()
        self.query_rows: list[dict] = []
        self.results: dict[tuple[int, ...], dict] = {}
        self.local_attempted: set[tuple[int, ...]] = set()
        self.seed_attempted: set[tuple[int, ...]] = set()
        self.seed_queue: list[dict] = []

    @property
    def calls(self) -> int:
        return len(self.queried)

    def mask_for(self, restored) -> int:
        mask = 0
        for road in restored:
            mask |= 1 << self.road_to_bit[int(road)]
        return mask

    def masks_for_sequence(self, sequence: tuple[int, ...]) -> list[int]:
        masks, current = [0], 0
        for road in sequence[:9]:
            current |= 1 << self.road_to_bit[road]
            masks.append(current)
        return masks

    def missing_count(self, sequence: tuple[int, ...]) -> int:
        return sum(mask not in self.queried for mask in self.masks_for_sequence(sequence))

    def query(self, mask: int, reason: str) -> float:
        hit = mask in self.queried
        if not hit:
            self.queried.add(mask)
            self.query_rows.append({"scenario_id": self.sid, "method": self.method, "query_index": self.calls,
                                    "subset_mask": mask, "restored_count": mask.bit_count(),
                                    "reason": reason, "loss": self.cost[mask]})
        return self.cost[mask]

    def metadata(self, sequence: tuple[int, ...]) -> dict:
        rows = self.candidates[self.candidates["seq_tuple"] == sequence]
        if rows.empty:
            return {"screening_tier": "local_search", "channel": "local_search", "primary_source": "local_search",
                    "proxy_rank": np.nan}
        row = rows.iloc[0]
        return {key: row.get(key, "") for key in ("screening_tier", "channel", "primary_source", "proxy_rank")}

    def evaluate_sequence(self, sequence: tuple[int, ...], reason: str, cap: int,
                          parent: tuple[int, ...] | None = None, move: str = "") -> dict | None:
        if sequence in self.results:
            return self.results[sequence]
        missing = self.missing_count(sequence)
        if self.calls + missing > cap:
            return None
        before = self.calls
        objective = float(np.mean([self.query(mask, f"{reason}:R{stage}") for stage, mask in enumerate(self.masks_for_sequence(sequence))]))
        meta = self.metadata(sequence)
        row = {"sequence": "|".join(map(str, sequence)), "sequence_id": seq_id(sequence),
               "ue_objective": objective, "completion_budget": self.calls, "new_ue_calls": self.calls - before,
               "screening_tier": meta["screening_tier"], "channel": meta["channel"],
               "primary_source": meta["primary_source"], "proxy_rank": meta["proxy_rank"],
               "evaluation_reason": reason, "parent_sequence_id": seq_id(parent) if parent else "", "move": move}
        self.results[sequence] = row
        return row

    @staticmethod
    def neighbors(sequence: tuple[int, ...]):
        for i in range(9):
            child = list(sequence); child[i], child[i + 1] = child[i + 1], child[i]
            yield tuple(child), "adjacent_swap", i, i + 1
        for i in range(5):
            for j in range(i + 2, 10):
                child = list(sequence); child[i], child[j] = child[j], child[i]
                yield tuple(child), "arbitrary_swap", i, j
        for i in range(5):
            for j in range(10):
                if i == j:
                    continue
                child = list(sequence); value = child.pop(i); child.insert(j, value)
                yield tuple(child), "insertion", i, j

    def local_search(self, cap: int) -> None:
        if not self.local_enabled or not self.results:
            return
        stale = 0
        while self.calls < cap and stale < 2:
            parents = sorted(self.results.items(), key=lambda item: item[1]["ue_objective"])[:5]
            best_before = parents[0][1]["ue_objective"]
            choices = []
            for parent_seq, parent in parents:
                for child, move, i, j in self.neighbors(parent_seq):
                    if child in self.local_attempted or child in self.results:
                        continue
                    choices.append((self.missing_count(child), move != "adjacent_swap", i, j,
                                    parent["ue_objective"], parent_seq, child, move))
            choices.sort(key=lambda item: item[:5])
            evaluated = 0
            for missing, _, i, j, _, parent, child, move in choices:
                if self.calls >= cap:
                    break
                if self.calls + missing > cap:
                    continue
                self.local_attempted.add(child)
                if self.evaluate_sequence(child, "local_search", cap, parent, f"{move}:{i}->{j}") is not None:
                    evaluated += 1
            best_after = min(row["ue_objective"] for row in self.results.values())
            improvement = (best_before - best_after) / best_before if best_before else 0.0
            stale = stale + 1 if evaluated == 0 or improvement < 0.001 else 0

    def best_snapshot(self, budget: int) -> dict:
        eligible = [row for row in self.results.values() if row["completion_budget"] <= budget]
        if not eligible:
            return {"ue_budget": budget, "complete_sequence_count": 0}
        best = min(eligible, key=lambda row: row["ue_objective"])
        return {"ue_budget": budget, "unique_ue_calls": min(self.calls, budget),
                "complete_sequence_count": len(eligible), "best_sequence": best["sequence"],
                "best_sequence_id": best["sequence_id"], "best_ue_objective": best["ue_objective"],
                "best_completion_budget": best["completion_budget"], "best_origin": best["evaluation_reason"],
                "best_screening_tier": best["screening_tier"], "best_channel": best["channel"],
                "best_primary_source": best["primary_source"]}

    def run_simple(self, queue: list[tuple[int, ...]], use_local: bool) -> list[dict]:
        attempted = set()
        snapshots = []
        for budget in BUDGETS:
            seed_cap = self.calls + int((budget - self.calls) * (0.50 if use_local else 1.0))
            progress = True
            while self.calls < seed_cap and progress:
                progress = False
                for sequence in queue:
                    if sequence in attempted or sequence in self.results:
                        continue
                    if self.calls + self.missing_count(sequence) <= seed_cap:
                        attempted.add(sequence)
                        self.evaluate_sequence(sequence, "candidate_ue_reranking", seed_cap)
                        progress = True
                        break
            if use_local:
                self.local_search(budget)
                while self.calls < budget:
                    added = False
                    for sequence in queue:
                        if sequence in attempted or sequence in self.results:
                            continue
                        if self.calls + self.missing_count(sequence) <= budget:
                            attempted.add(sequence)
                            self.evaluate_sequence(sequence, "candidate_ue_reranking", budget)
                            self.local_search(budget)
                            added = True
                            break
                    if not added:
                        break
            snapshots.append(self.best_snapshot(budget))
        return snapshots

    def prefix2_order(self) -> list[str]:
        reserve = self.candidates[self.candidates["screening_tier"] == "structural_reserve"]
        table = reserve[["prefix_2", "prefix_2_cluster_rank"]].drop_duplicates().copy()
        table["prefix_2_cluster_rank"] = pd.to_numeric(table["prefix_2_cluster_rank"], errors="coerce")
        return table.sort_values(["prefix_2_cluster_rank", "prefix_2"])["prefix_2"].dropna().astype(str).unique().tolist()

    def evaluate_prefix2(self, cap: int) -> list[str]:
        prefixes = self.prefix2_order()
        self.query(0, "prefix2_common_R0")
        for prefix in prefixes:
            roads = seq_tuple(prefix)
            for stage in (1, 2):
                mask = self.mask_for(roads[:stage])
                if mask not in self.queried and self.calls >= cap:
                    return prefixes
                self.query(mask, f"prefix2:{prefix}:R{stage}")
        return prefixes

    def rank_prefix2(self, prefixes: list[str]) -> list[str]:
        scored = []
        for prefix in prefixes:
            roads = seq_tuple(prefix)
            masks = [self.mask_for(roads[:1]), self.mask_for(roads)]
            if all(mask in self.queried for mask in masks):
                scored.append((sum(self.cost[mask] for mask in masks), prefix))
        return [prefix for _, prefix in sorted(scored)]

    def evaluate_prefix3(self, prefixes: list[str], cap: int) -> None:
        reserve = self.candidates[self.candidates["screening_tier"] == "structural_reserve"]
        for p2 in prefixes:
            groups = sorted(reserve[reserve["prefix_2"].astype(str) == p2]["prefix_3"].dropna().astype(str).unique())
            for p3 in groups:
                mask = self.mask_for(seq_tuple(p3))
                if mask not in self.queried and self.calls >= cap:
                    return
                self.query(mask, f"prefix3:{p3}:R3")

    def build_seed_queue(self) -> None:
        reserve = self.candidates[self.candidates["screening_tier"] == "structural_reserve"].copy()
        scores = []
        for p3 in reserve["prefix_3"].dropna().astype(str).unique():
            roads = seq_tuple(p3)
            masks = [self.mask_for(roads[:k]) for k in (1, 2, 3)]
            if all(mask in self.queried for mask in masks):
                scores.append((sum(self.cost[mask] for mask in masks), p3))
        ranks = {p3: i for i, (_, p3) in enumerate(sorted(scores), start=1)}
        sources = sorted(reserve["primary_source"].dropna().astype(str).unique())
        source_rank = {source: i for i, source in enumerate(sources)}
        rows = []
        for _, row in reserve.iterrows():
            p3 = str(row["prefix_3"])
            if p3 not in ranks:
                continue
            q = int(row["source_quantile_index"]) if pd.notna(row["source_quantile_index"]) else 99
            rotated = (source_rank.get(str(row["primary_source"]), 99) - ranks[p3]) % max(1, len(sources))
            rows.append({"sequence": row["seq_tuple"], "sort": (ranks[p3], QUANTILE_PRIORITY.get(q, 99), rotated,
                                                                   int(row["proxy_rank"]))})
        primary = self.candidates[self.candidates["screening_tier"] == "primary_shortlist"]
        for _, row in primary.iterrows():
            p3 = str(row.get("prefix_3", ""))
            if p3 in ranks:
                rows.append({"sequence": row["seq_tuple"], "sort": (ranks[p3], int(row.get("channel_rank", 99)), 50,
                                                                        int(row["proxy_rank"]))})
        rows.sort(key=lambda item: item["sort"])
        seen = set(); self.seed_queue = []
        for row in rows:
            if row["sequence"] not in seen:
                seen.add(row["sequence"]); self.seed_queue.append(row)

    def next_seed(self, remaining: int):
        for row in self.seed_queue:
            sequence = row["sequence"]
            if sequence in self.seed_attempted or sequence in self.results:
                continue
            if self.missing_count(sequence) <= remaining:
                self.seed_attempted.add(sequence)
                return sequence
        return None

    def fill_state(self, cap: int) -> bool:
        if self.calls >= cap:
            return False
        ordered = self.candidates.sort_values(["screening_tier", "proxy_rank"], kind="stable")
        for sequence in ordered["seq_tuple"]:
            current = 0
            for stage, road in enumerate(sequence[:9], start=1):
                current |= 1 << self.road_to_bit[road]
                if current not in self.queried:
                    self.query(current, f"structured_fill:R{stage}")
                    return True
        return False

    def full_interval(self, cap: int, seed_share: float) -> None:
        seed_cap = self.calls + int((cap - self.calls) * seed_share)
        while self.calls < seed_cap:
            sequence = self.next_seed(seed_cap - self.calls)
            if sequence is None:
                break
            self.evaluate_sequence(sequence, "stratified_candidate", seed_cap)
        self.local_search(cap)
        while self.calls < cap:
            sequence = self.next_seed(cap - self.calls)
            if sequence is not None:
                self.evaluate_sequence(sequence, "stratified_candidate", cap)
                self.local_search(cap)
            elif not self.fill_state(cap):
                break

    def run_full(self) -> list[dict]:
        prefixes = self.evaluate_prefix2(64)
        ranked = self.rank_prefix2(prefixes)
        self.evaluate_prefix3(ranked[:4], 64)
        self.build_seed_queue(); self.full_interval(64, 0.55)
        snapshots = [self.best_snapshot(64)]
        self.evaluate_prefix3(ranked[4:], 128)
        self.build_seed_queue(); self.full_interval(128, 0.50); snapshots.append(self.best_snapshot(128))
        self.full_interval(256, 0.50); snapshots.append(self.best_snapshot(256))
        self.full_interval(512, 0.50); snapshots.append(self.best_snapshot(512))
        return snapshots


def queue_from(frame: pd.DataFrame) -> list[tuple[int, ...]]:
    return [seq_tuple(value) for value in frame["sequence"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day6-root", required=True)
    parser.add_argument("--mode", choices=["development", "pressure"], required=True)
    parser.add_argument("--development-root", type=Path, help="Root containing the archived development inputs")
    args = parser.parse_args()
    root = Path(args.day6_root)
    if args.mode == "development":
        if args.development_root is None:
            parser.error("--development-root is required in development mode")
        delivery = args.development_root.resolve()
        pool_path = delivery / "第三周工作/day3_candidate_pool_v1.1/candidate_pool.csv.gz"
        screened_path = delivery / "第三周工作/day4_multichannel_screening_v1.1/screened_candidates.csv"
        cost_path = delivery / "第三周工作/day2_exact_dp_baseline_v1.1/subset_ue_costs.csv"
        meta_path = delivery / "第三周工作/day1_problem_freeze_v1.1/development_scenarios.json"
        scenario_ids = (246, 247, 249)
        methods = ("traditional_heuristic_ue", "surrogate_only", "random_ue", "proxy_topk_ue",
                   "no_structural_reserve", "no_disagreement_channel", "no_diversity_channel",
                   "no_local_search", "full_method")
    else:
        pool_path = root / "pressure_candidates/candidate_pool.csv.gz"
        screened_path = root / "pressure_candidates/screened_candidates.csv"
        cost_path = root / "pressure_exact_reference/subset_ue_costs.csv"
        meta_path = root / "pressure_candidates/pressure_scenarios.json"
        scenario_ids = (146, 148, 149, 157)
        methods = ("random_ue", "proxy_topk_ue", "full_method")
    out = root / f"{args.mode}_experiments"
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    pool = pd.read_csv(pool_path)
    screened = pd.read_csv(screened_path)
    costs = pd.read_csv(cost_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    roads_by_sid = {int(row["scenario_id"]): list(map(int, row["selected_recoverable_roads"])) for row in meta["scenarios"]}
    rows, queries = [], []
    for sid in scenario_ids:
        scenario_pool = pool[pool["scenario_id"].astype(int) == sid].copy()
        scenario_screened = screened[screened["scenario_id"].astype(int) == sid].copy()
        scenario_cost = costs[costs["scenario_id"].astype(int) == sid].copy()
        for method in methods:
            if method == "full_method" and args.mode == "development":
                day5 = pd.read_csv(delivery / "第三周工作/day5_budgeted_ue_reranking_local_search/budget_snapshots_pre_reference.csv")
                for _, snap in day5[day5["scenario_id"].astype(int) == sid].iterrows():
                    rows.append({"dataset": args.mode, "scenario_id": sid, "method": method,
                                 "ue_budget": int(snap["ue_budget"]), "unique_ue_calls": int(snap["ue_budget"]),
                                 "complete_sequence_count": int(snap["complete_sequence_count"]),
                                 "best_sequence": snap["best_sequence"], "best_sequence_id": snap["best_sequence_id"],
                                 "best_ue_objective": float(snap["best_ue_objective"]),
                                 "best_completion_budget": int(snap["best_completion_budget"]),
                                 "best_origin": snap["best_evaluation_phase"]})
                continue
            if method == "surrogate_only":
                selected = scenario_pool.sort_values(["proxy_rank", "candidate_id"]).iloc[0]
                sequence = seq_tuple(selected["sequence"])
                road_to_bit = {road: i for i, road in enumerate(roads_by_sid[sid])}
                masks, current = [0], 0
                for road in sequence[:9]:
                    current |= 1 << road_to_bit[road]; masks.append(current)
                lookup = {int(row.subset_mask): float(row.loss) for row in scenario_cost.itertuples(index=False)}
                objective = float(np.mean([lookup[mask] for mask in masks]))
                for budget in BUDGETS:
                    rows.append({"dataset": args.mode, "scenario_id": sid, "method": method, "ue_budget": budget,
                                 "unique_ue_calls": 0, "complete_sequence_count": 1, "best_sequence": selected["sequence"],
                                 "best_sequence_id": seq_id(sequence), "best_ue_objective": objective,
                                 "best_completion_budget": 0, "best_origin": "proxy_rank_1_no_ue_feedback"})
                continue

            local = method in {"no_structural_reserve", "no_disagreement_channel", "no_diversity_channel", "full_method"}
            candidates = scenario_screened.copy()
            if method == "no_structural_reserve":
                candidates = candidates[candidates["screening_tier"] == "primary_shortlist"]
            elif method == "no_disagreement_channel":
                candidates = candidates[~((candidates["screening_tier"] == "primary_shortlist") &
                                          (candidates["channel"] == "ensemble_disagreement"))]
            elif method == "no_diversity_channel":
                candidates = candidates[(candidates["channel"] != "sequence_diversity") &
                                        (candidates["primary_source"] != "sequence_diversity")]
            search = OracleSearch(sid, roads_by_sid[sid], scenario_cost, candidates, method, local)
            if method == "traditional_heuristic_ue":
                queue_frame = scenario_screened[(scenario_screened["screening_tier"] == "primary_shortlist") &
                                                (scenario_screened["channel"] == "heuristic")].sort_values("channel_rank")
                snapshots = search.run_simple(queue_from(queue_frame), use_local=False)
            elif method == "random_ue":
                queue_frame = scenario_pool[scenario_pool["primary_source"] == "random"].sample(
                    frac=1.0, random_state=SEED + sid)
                snapshots = search.run_simple(queue_from(queue_frame), use_local=False)
            elif method == "proxy_topk_ue":
                snapshots = search.run_simple(queue_from(scenario_pool.sort_values(["proxy_rank", "candidate_id"])), use_local=False)
            elif method == "no_structural_reserve":
                queue_frame = candidates.sort_values(["channel_rank", "channel", "proxy_rank"], kind="mergesort")
                snapshots = search.run_simple(queue_from(queue_frame), use_local=True)
            else:
                snapshots = search.run_full()
            for snap in snapshots:
                rows.append({"dataset": args.mode, "scenario_id": sid, "method": method, **snap})
            queries.extend(search.query_rows)
            print(json.dumps({"event": "method_complete", "dataset": args.mode, "scenario_id": sid,
                              "method": method, "calls": search.calls, "complete_sequences": len(search.results)}), flush=True)

    result = pd.DataFrame(rows).sort_values(["scenario_id", "method", "ue_budget"])
    result.to_csv(out / "budgeted_method_results_pre_reference.csv", index=False)
    pd.DataFrame(queries).to_csv(out / "unique_state_query_audit.csv.gz", index=False, compression="gzip")
    freeze = {"schema_version": f"week3-day6-{args.mode}-experiment-freeze-v1.0",
              "results_sha256": sha256(out / "budgeted_method_results_pre_reference.csv"),
              "query_audit_sha256": sha256(out / "unique_state_query_audit.csv.gz"),
              "candidate_pool_sha256": sha256(pool_path), "screened_candidates_sha256": sha256(screened_path),
              "subset_cost_backend_sha256": sha256(cost_path), "exact_dp_solution_read_during_methods": False,
              "posthoc_exact_solution_scoring_permitted": True}
    (out / "experiment_freeze_record.json").write_text(json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
