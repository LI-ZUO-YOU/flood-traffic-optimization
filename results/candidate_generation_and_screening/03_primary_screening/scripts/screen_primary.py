from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_SEED_BASE = 2026080703
CHANNEL_QUOTAS = {
    "proxy_top": 15,
    "ensemble_disagreement": 10,
    "sequence_diversity": 15,
    "heuristic": 10,
    "random": 10,
}
CHANNEL_PRIORITY = list(CHANNEL_QUOTAS)
DISAGREEMENT_PROXY_FRACTION = 0.30
DIVERSITY_PROXY_FRACTION = 0.50


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_sequences(frame: pd.DataFrame) -> list[tuple[int, ...]]:
    return [tuple(map(int, value.split("|"))) for value in frame["sequence"]]


def orientation_matrix(sequences: list[tuple[int, ...]], roads: list[int]) -> np.ndarray:
    road_to_index = {road: index for index, road in enumerate(roads)}
    positions = np.empty((len(sequences), len(roads)), dtype=np.int8)
    for row_index, sequence in enumerate(sequences):
        for position, road in enumerate(sequence):
            positions[row_index, road_to_index[road]] = position
    columns = []
    for i in range(len(roads)):
        for j in range(i + 1, len(roads)):
            columns.append(positions[:, i] < positions[:, j])
    return np.column_stack(columns)


def kendall_distance(orientation: np.ndarray, reference: np.ndarray) -> np.ndarray:
    return np.count_nonzero(orientation != reference, axis=1) / orientation.shape[1]


def heuristic_references(audit: pd.DataFrame, roads: list[int]) -> list[tuple[str, tuple[int, ...]]]:
    selected = audit.loc[audit["physical_link_id"].isin(roads)].copy()
    rules = [
        ("combined_desc", ["combined_score", "physical_flow", "physical_link_id"], [False, False, True]),
        ("flow_desc", ["physical_flow", "betweenness", "physical_link_id"], [False, False, True]),
        ("betweenness_desc", ["betweenness", "physical_flow", "physical_link_id"], [False, False, True]),
        ("depth_desc", ["depth_m", "physical_flow", "physical_link_id"], [False, False, True]),
        ("depth_asc", ["depth_m", "physical_flow", "physical_link_id"], [True, False, True]),
    ]
    references = []
    for name, columns, ascending in rules:
        sequence = tuple(selected.sort_values(columns, ascending=ascending)["physical_link_id"].astype(int))
        references.append((name, sequence))
        references.append((name + "_reverse", tuple(reversed(sequence))))
    return references


def select_scenario(frame: pd.DataFrame, roads: list[int], audit: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    frame = frame.sort_values(["proxy_rank", "candidate_id"]).reset_index(drop=True).copy()
    sequences = parse_sequences(frame)
    orientations = orientation_matrix(sequences, roads)
    id_to_index = {candidate_id: index for index, candidate_id in enumerate(frame["candidate_id"])}
    selected_ids: set[str] = set()
    rows = []

    def choose(index: int, channel: str, channel_rank: int, score: float, reason: str) -> None:
        candidate_id = str(frame.iloc[index]["candidate_id"])
        if candidate_id in selected_ids:
            raise AssertionError("Duplicate candidate selected across channels")
        selected_ids.add(candidate_id)
        row = frame.iloc[index].to_dict()
        row.update({
            "channel": channel,
            "channel_rank": channel_rank,
            "screen_order": len(rows) + 1,
            "channel_selection_score": score,
            "selection_reason": reason,
            "proxy_top30pct_eligible": int(row["proxy_rank"]) <= int(DISAGREEMENT_PROXY_FRACTION * len(frame)),
            "diversity_top50pct_eligible": int(row["proxy_rank"]) <= int(DIVERSITY_PROXY_FRACTION * len(frame)),
        })
        rows.append(row)

    # Channel 1: exploit the surrogate conservatively; quota reduced from 30 to 15 after Day 3 validation.
    proxy_indices = frame.sort_values(["proxy_rank", "candidate_id"]).index
    for index in proxy_indices:
        if len([row for row in rows if row["channel"] == "proxy_top"]) >= CHANNEL_QUOTAS["proxy_top"]:
            break
        if str(frame.iloc[index]["candidate_id"]) not in selected_ids:
            rank = 1 + len([row for row in rows if row["channel"] == "proxy_top"])
            choose(int(index), "proxy_top", rank, float(frame.iloc[index]["proxy_rank"]), "lowest ensemble-mean proxy objective")

    # Channel 2: disagreement is exploratory only inside the proxy-quality top 30%.
    eligible = frame.loc[frame["proxy_rank"] <= int(DISAGREEMENT_PROXY_FRACTION * len(frame))]
    eligible = eligible.sort_values(["ensemble_disagreement", "proxy_objective_mean", "candidate_id"], ascending=[False, True, True])
    for index in eligible.index:
        if len([row for row in rows if row["channel"] == "ensemble_disagreement"]) >= CHANNEL_QUOTAS["ensemble_disagreement"]:
            break
        if str(frame.iloc[index]["candidate_id"]) not in selected_ids:
            rank = 1 + len([row for row in rows if row["channel"] == "ensemble_disagreement"])
            choose(int(index), "ensemble_disagreement", rank, float(frame.iloc[index]["ensemble_disagreement"]), "highest member disagreement within proxy top 30%")

    # Channel 3: max-min Kendall diversity, constrained to the proxy top 50%.
    diversity_mask = frame["proxy_rank"].to_numpy() <= int(DIVERSITY_PROXY_FRACTION * len(frame))
    available = diversity_mask.copy()
    for candidate_id in selected_ids:
        available[id_to_index[candidate_id]] = False
    selected_indices = [id_to_index[candidate_id] for candidate_id in selected_ids]
    min_distance = np.ones(len(frame), dtype=float)
    for index in selected_indices:
        min_distance = np.minimum(min_distance, kendall_distance(orientations, orientations[index]))
    for channel_rank in range(1, CHANNEL_QUOTAS["sequence_diversity"] + 1):
        valid = np.flatnonzero(available)
        if len(valid) == 0:
            raise RuntimeError("Diversity candidate set exhausted")
        best_distance = min_distance[valid].max()
        tied = valid[np.isclose(min_distance[valid], best_distance)]
        tied_frame = frame.iloc[tied]
        index = int(tied[np.lexsort((tied_frame["candidate_id"].to_numpy(), tied_frame["proxy_objective_mean"].to_numpy()))[0]])
        choose(index, "sequence_diversity", channel_rank, float(min_distance[index]), "max-min Kendall distance within proxy top 50%")
        available[index] = False
        min_distance = np.minimum(min_distance, kendall_distance(orientations, orientations[index]))

    # Channel 4: one pool candidate nearest to each frozen traditional ranking rule.
    references = heuristic_references(audit, roads)
    for channel_rank, (rule_name, reference_sequence) in enumerate(references, start=1):
        if channel_rank > CHANNEL_QUOTAS["heuristic"]:
            break
        reference_orientation = orientation_matrix([reference_sequence], roads)[0]
        distance = kendall_distance(orientations, reference_orientation)
        valid = np.array([str(candidate_id) not in selected_ids for candidate_id in frame["candidate_id"]])
        best_distance = distance[valid].min()
        tied = np.flatnonzero(valid & np.isclose(distance, best_distance))
        tied_frame = frame.iloc[tied]
        index = int(tied[np.lexsort((tied_frame["candidate_id"].to_numpy(), tied_frame["proxy_objective_mean"].to_numpy()))[0]])
        choose(index, "heuristic", channel_rank, float(distance[index]), f"nearest pool sequence to frozen rule {rule_name}")

    # Channel 5: fixed-seed uniform draw from the independently generated random source.
    random_indices = frame.index[frame["primary_source"] == "random"].to_numpy()
    random_indices = rng.permutation(random_indices)
    channel_rank = 0
    for index in random_indices:
        if channel_rank >= CHANNEL_QUOTAS["random"]:
            break
        if str(frame.iloc[int(index)]["candidate_id"]) in selected_ids:
            continue
        channel_rank += 1
        choose(int(index), "random", channel_rank, float(channel_rank), "fixed-seed uniform draw from random-source pool")

    selected = pd.DataFrame(rows)
    if len(selected) != sum(CHANNEL_QUOTAS.values()):
        raise AssertionError(f"Expected 60 selected candidates; got {len(selected)}")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Select the frozen 60-candidate primary shortlist for arbitrary scenarios.")
    parser.add_argument("--input-candidate-pool", required=True)
    parser.add_argument("--candidate-freeze", required=True)
    parser.add_argument("--scenario-metadata", required=True)
    parser.add_argument("--candidate-road-audit", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scenario-count", required=True, type=int)
    parser.add_argument("--seed-base", type=int, default=DEFAULT_SEED_BASE)
    args = parser.parse_args()

    pool_path = Path(args.input_candidate_pool)
    freeze_path = Path(args.candidate_freeze)
    metadata_path = Path(args.scenario_metadata)
    audit_path = Path(args.candidate_road_audit)
    output = Path(args.output_dir)
    staging = output.with_name(f".{output.name}_staging")
    if output.exists() or staging.exists():
        raise FileExistsError("Primary-screening output or staging already exists")
    staging.mkdir(parents=True)
    (staging / "scripts").mkdir()
    shutil.copy2(Path(__file__), staging / "scripts" / Path(__file__).name)
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if sha256(pool_path) != freeze["candidate_pool_sha256"]:
        raise RuntimeError("Day 3 candidate pool differs from its pre-quality freeze hash")
    pool = pd.read_csv(pool_path)
    development = json.loads(metadata_path.read_text(encoding="utf-8"))
    roads_by_scenario = {
        int(row["scenario_id"]): list(map(int, row["selected_recoverable_roads"]))
        for row in development["scenarios"]
    }
    if len(roads_by_scenario) != args.scenario_count:
        raise ValueError(f"Expected {args.scenario_count} scenarios; found {len(roads_by_scenario)}")
    audit = pd.read_csv(audit_path)
    selected_frames = []
    for scenario_id, frame in pool.groupby("scenario_id", sort=True):
        scenario_id = int(scenario_id)
        selected = select_scenario(
            frame,
            roads_by_scenario[scenario_id],
            audit.loc[audit["scenario_id"] == scenario_id],
            np.random.default_rng(args.seed_base + scenario_id),
        )
        selected_frames.append(selected)
        print(json.dumps({"event": "scenario_screened", "scenario_id": scenario_id, "channel_counts": selected["channel"].value_counts().sort_index().to_dict()}, ensure_ascii=False), flush=True)
    screened = pd.concat(selected_frames, ignore_index=True).sort_values(["scenario_id", "screen_order"])
    output_columns = [
        "scenario_id", "candidate_id", "sequence", "channel", "channel_rank", "screen_order",
        "primary_source", "source_detail", "proxy_rank", "proxy_objective_mean", "ensemble_disagreement",
        "channel_selection_score", "proxy_top30pct_eligible", "diversity_top50pct_eligible", "selection_reason",
    ] + [f"road_{index:02d}" for index in range(1, 11)]
    screened[output_columns].to_csv(staging / "screened_candidates.csv", index=False, encoding="utf-8-sig")

    summary = screened.groupby(["scenario_id", "channel"], as_index=False).agg(
        selected_count=("candidate_id", "count"),
        minimum_proxy_rank=("proxy_rank", "min"),
        median_proxy_rank=("proxy_rank", "median"),
        maximum_proxy_rank=("proxy_rank", "max"),
        minimum_proxy_objective=("proxy_objective_mean", "min"),
        median_proxy_objective=("proxy_objective_mean", "median"),
        maximum_disagreement=("ensemble_disagreement", "max"),
    )
    summary.to_csv(staging / "candidate_channel_summary.csv", index=False, encoding="utf-8-sig")

    config = {
        "schema_version": "week3-day4-v1.0",
        "random_seed_base": args.seed_base,
        "total_candidates_per_scenario": 60,
        "channel_priority": CHANNEL_PRIORITY,
        "channel_quotas": CHANNEL_QUOTAS,
        "duplicate_policy": "earlier-priority channel keeps candidate; later channel fills from next eligible candidate",
        "ensemble_disagreement_rule": {
            "unconditional_top_disagreement_forbidden": True,
            "eligible_proxy_fraction": DISAGREEMENT_PROXY_FRACTION,
            "selection": "highest disagreement, then lower proxy objective and candidate_id",
        },
        "sequence_diversity_rule": {
            "distance": "normalized Kendall discordant-pair count over 45 road pairs",
            "selection": "greedy max-min relative to candidates already selected",
            "eligible_proxy_fraction": DIVERSITY_PROXY_FRACTION,
        },
        "heuristic_rule": "nearest candidate by Kendall distance to ten frozen flow/betweenness/depth ranking rules",
        "random_rule": "fixed-seed uniform sampling from candidates whose primary_source is random",
        "information_boundary": {
            "posthoc_candidate_quality_not_read": True,
            "exact_dp_solution_not_read": True,
            "subset_ue_costs_not_read": True,
            "exact_reference_cache_not_read": True,
            "frozen_scenario_inputs_only": True,
        },
        "source_sha256": {
            "candidate_pool": sha256(pool_path),
            "candidate_generation_freeze": sha256(freeze_path),
            "scenario_metadata": sha256(metadata_path),
            "candidate_road_selection_audit": sha256(audit_path),
        },
    }
    write_json(staging / "screening_config.json", config)
    scenario_checks = {}
    for scenario_id, frame in screened.groupby("scenario_id"):
        counts = frame["channel"].value_counts().to_dict()
        disagreement = frame.loc[frame["channel"] == "ensemble_disagreement"]
        scenario_checks[str(int(scenario_id))] = {
            "selected_count_60": len(frame) == 60,
            "candidate_ids_unique_60": frame["candidate_id"].nunique() == 60,
            "channel_counts": counts,
            "channel_quotas_exact": counts == CHANNEL_QUOTAS,
            "all_disagreement_candidates_proxy_top30pct": bool(disagreement["proxy_top30pct_eligible"].all()),
            "all_sequences_from_frozen_pool": bool(frame["candidate_id"].isin(pool.loc[pool["scenario_id"] == scenario_id, "candidate_id"]).all()),
        }
    global_checks = {
        "scenario_count_matches_cli": len(scenario_checks) == args.scenario_count,
        "total_screened_candidates_exact": len(screened) == 60 * args.scenario_count,
        "global_candidate_ids_unique": screened["candidate_id"].nunique() == 60 * args.scenario_count,
        "all_scenario_checks_pass": all(
            value["selected_count_60"] and value["candidate_ids_unique_60"] and value["channel_quotas_exact"]
            and value["all_disagreement_candidates_proxy_top30pct"] and value["all_sequences_from_frozen_pool"]
            for value in scenario_checks.values()
        ),
        "unconditional_high_disagreement_not_used": True,
        "exact_reference_not_read": True,
        "frozen_scenario_inputs_only": True,
    }
    report = {
        "status": "pass" if all(global_checks.values()) else "fail",
        "global_checks": global_checks,
        "scenario_checks": scenario_checks,
        "day5_permitted_after_workbook_verification": all(global_checks.values()),
    }
    write_json(staging / "screening_verification_report.json", report)
    (staging / "结果说明.txt").write_text(
        "正式多通道候选筛选。\n"
        f"每个冻结情景从30000条候选中筛选60条，共{60 * args.scenario_count}条。\n"
        "通道配额：代理Top 15、质量约束成员分歧10、Kendall多样性15、传统启发式10、随机10。\n"
        "成员分歧仅在代理目标前30%内使用；筛选未读取任何真实UE质量或精确参考。\n",
        encoding="utf-8",
    )
    if report["status"] != "pass":
        raise RuntimeError("Day 4 screening gate failed")
    staging.replace(output)
    print(json.dumps({"output": str(output), "status": report["status"], "rows": len(screened)}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
