from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


PREFIX2_CLUSTER_COUNT = 10
SOURCE_QUANTILES_PER_PREFIX3 = 10
PRIMARY_CHANNEL_QUOTAS = {
    "proxy_top": 15,
    "ensemble_disagreement": 10,
    "sequence_diversity": 15,
    "heuristic": 10,
    "random": 10,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def structural_reserve(frame: pd.DataFrame, primary_ids: set[str]) -> pd.DataFrame:
    frame = frame.copy()
    split = frame["sequence"].str.split("|")
    frame["prefix_2"] = split.map(lambda values: "|".join(values[:2]))
    frame["prefix_3"] = split.map(lambda values: "|".join(values[:3]))
    prefix2_order = (
        frame.groupby("prefix_2")["proxy_rank"].min()
        .sort_values(kind="mergesort")
        .head(PREFIX2_CLUSTER_COUNT)
    )
    prefix2_rank = {prefix: rank for rank, prefix in enumerate(prefix2_order.index, start=1)}
    selected_rows = []
    for prefix_2 in prefix2_order.index:
        cluster = frame.loc[frame["prefix_2"] == prefix_2]
        for prefix_3, prefix_frame in cluster.groupby("prefix_3", sort=True):
            for source, source_frame in prefix_frame.groupby("primary_source", sort=True):
                source_frame = source_frame.sort_values(["proxy_rank", "candidate_id"], kind="mergesort").reset_index(drop=True)
                count = min(SOURCE_QUANTILES_PER_PREFIX3, len(source_frame))
                positions = np.unique(np.round(np.linspace(0, len(source_frame) - 1, count)).astype(int))
                for quantile_index, position in enumerate(positions, start=1):
                    row = source_frame.iloc[int(position)].copy()
                    row["prefix_2_cluster_rank"] = prefix2_rank[prefix_2]
                    row["source_quantile_index"] = quantile_index
                    row["source_quantile_total"] = len(positions)
                    row["reserve_rule"] = "top10 proxy-prefix2 clusters × all prefix3 groups × source-wise proxy-rank quantiles"
                    selected_rows.append(row)
    reserve = pd.DataFrame(selected_rows).drop_duplicates("candidate_id")
    reserve = reserve.loc[~reserve["candidate_id"].isin(primary_ids)].copy()
    reserve["screening_tier"] = "structural_reserve"
    reserve["channel"] = "hierarchical_prefix_reserve"
    reserve["channel_rank"] = reserve.groupby("scenario_id").cumcount() + 1
    return reserve


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the frozen structural reserve for arbitrary scenarios.")
    parser.add_argument("--input-candidate-pool", required=True)
    parser.add_argument("--candidate-freeze", required=True)
    parser.add_argument("--primary-shortlist", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scenario-count", required=True, type=int)
    args = parser.parse_args()

    pool_path = Path(args.input_candidate_pool)
    freeze_path = Path(args.candidate_freeze)
    primary_path = Path(args.primary_shortlist)
    output = Path(args.output_dir)
    staging = output.with_name(f".{output.name}_staging")
    if output.exists() or staging.exists():
        raise FileExistsError("Structural-screening output or staging already exists")
    staging.mkdir(parents=True)
    (staging / "scripts").mkdir()
    shutil.copy2(Path(__file__), staging / "scripts" / Path(__file__).name)
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if sha256(pool_path) != freeze["candidate_pool_sha256"]:
        raise RuntimeError("Day 3 pool hash mismatch")
    pool = pd.read_csv(pool_path)
    primary = pd.read_csv(primary_path)
    if pool["scenario_id"].nunique() != args.scenario_count or primary["scenario_id"].nunique() != args.scenario_count:
        raise ValueError("Scenario count does not match --scenario-count")
    primary["screening_tier"] = "primary_shortlist"
    primary["prefix_2"] = primary["sequence"].str.split("|").map(lambda values: "|".join(values[:2]))
    primary["prefix_3"] = primary["sequence"].str.split("|").map(lambda values: "|".join(values[:3]))
    primary["prefix_2_cluster_rank"] = np.nan
    primary["source_quantile_index"] = np.nan
    primary["source_quantile_total"] = np.nan
    primary["reserve_rule"] = "not applicable: primary 60-candidate shortlist"

    reserves = []
    for scenario_id, scenario_pool in pool.groupby("scenario_id", sort=True):
        primary_ids = set(primary.loc[primary["scenario_id"] == scenario_id, "candidate_id"])
        reserves.append(structural_reserve(scenario_pool, primary_ids))
    reserve = pd.concat(reserves, ignore_index=True)
    combined = pd.concat([primary, reserve], ignore_index=True, sort=False)
    combined = combined.sort_values(["scenario_id", "screening_tier", "channel", "channel_rank", "candidate_id"], kind="mergesort")

    base_columns = [
        "scenario_id", "candidate_id", "sequence", "screening_tier", "channel", "channel_rank",
        "primary_source", "source_detail", "proxy_rank", "proxy_objective_mean", "ensemble_disagreement",
        "prefix_2", "prefix_3", "prefix_2_cluster_rank", "source_quantile_index", "source_quantile_total", "reserve_rule",
    ]
    for column in base_columns:
        if column not in combined:
            combined[column] = np.nan
    combined[base_columns].to_csv(staging / "screened_candidates.csv", index=False, encoding="utf-8-sig")
    primary[base_columns].to_csv(staging / "primary_shortlist.csv", index=False, encoding="utf-8-sig")
    reserve[base_columns].to_csv(
        staging / "structural_reserve.csv.gz", index=False, encoding="utf-8",
        compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
    )

    channel_summary = primary.groupby(["scenario_id", "channel"], as_index=False).agg(
        selected_count=("candidate_id", "count"),
        minimum_proxy_rank=("proxy_rank", "min"),
        median_proxy_rank=("proxy_rank", "median"),
        maximum_proxy_rank=("proxy_rank", "max"),
    )
    channel_summary.to_csv(staging / "primary_channel_summary.csv", index=False, encoding="utf-8-sig")
    reserve_summary = reserve.groupby(["scenario_id", "primary_source"], as_index=False).agg(
        reserve_count=("candidate_id", "count"),
        prefix2_count=("prefix_2", "nunique"),
        prefix3_count=("prefix_3", "nunique"),
        minimum_proxy_rank=("proxy_rank", "min"),
        median_proxy_rank=("proxy_rank", "median"),
        maximum_proxy_rank=("proxy_rank", "max"),
    )
    reserve_summary.to_csv(staging / "structural_reserve_summary.csv", index=False, encoding="utf-8-sig")

    config = {
        "schema_version": "week3-day4-v1.1",
        "revision_reason": "post-freeze development diagnosis showed that proxy-only compression from 30000 to 60 discarded all candidates within 1.5% true regret",
        "hierarchical_screening": {
            "primary_shortlist_per_scenario": 60,
            "primary_channel_quotas": PRIMARY_CHANNEL_QUOTAS,
            "structural_reserve": {
                "top_prefix2_clusters_by_minimum_proxy_rank": PREFIX2_CLUSTER_COUNT,
                "all_prefix3_groups_within_each_selected_prefix2": True,
                "source_stratification": "primary_source",
                "proxy_rank_quantiles_per_source_prefix3": SOURCE_QUANTILES_PER_PREFIX3,
                "role": "remain eligible for Day 5 adaptive UE-state-budget search; not all sequences are fully UE-evaluated",
            },
        },
        "ue_budget_unchanged": {
            "unit": "unique UE state cache miss",
            "levels": [64, 128, 256, 512],
            "screened_sequence_count_does_not_consume_ue_budget": True,
        },
        "information_boundary": {
            "screening_reads_posthoc_true_quality": False,
            "screening_reads_exact_dp_solution": False,
            "screening_reads_subset_ue_costs": False,
            "screening_reads_exact_reference_cache": False,
            "quality_evaluation_runs_only_after_screened_file_hash_freeze": True,
            "frozen_scenario_inputs_only": True,
        },
        "source_sha256": {
            "candidate_pool": sha256(pool_path),
            "candidate_generation_freeze": sha256(freeze_path),
            "primary_shortlist": sha256(primary_path),
        },
    }
    write_json(staging / "screening_config.json", config)

    scenario_checks = {}
    for scenario_id, scenario_combined in combined.groupby("scenario_id"):
        scenario_primary = primary.loc[primary["scenario_id"] == scenario_id]
        scenario_reserve = reserve.loc[reserve["scenario_id"] == scenario_id]
        channel_counts = scenario_primary["channel"].value_counts().to_dict()
        top_prefix2 = scenario_reserve["prefix_2_cluster_rank"].dropna().astype(int)
        scenario_checks[str(int(scenario_id))] = {
            "primary_count_60": len(scenario_primary) == 60,
            "primary_channel_quotas_exact": channel_counts == PRIMARY_CHANNEL_QUOTAS,
            "reserve_count": int(len(scenario_reserve)),
            "reserve_at_least_2000": len(scenario_reserve) >= 2000,
            "ten_prefix2_clusters_present": set(top_prefix2) == set(range(1, PREFIX2_CLUSTER_COUNT + 1)),
            "combined_candidate_ids_unique": scenario_combined["candidate_id"].nunique() == len(scenario_combined),
            "all_candidates_from_frozen_pool": bool(scenario_combined["candidate_id"].isin(pool.loc[pool["scenario_id"] == scenario_id, "candidate_id"]).all()),
        }
    global_checks = {
        "scenario_count_matches_cli": len(scenario_checks) == args.scenario_count,
        "all_engineering_checks_pass": all(
            value["primary_count_60"] and value["primary_channel_quotas_exact"] and value["reserve_at_least_2000"]
            and value["ten_prefix2_clusters_present"] and value["combined_candidate_ids_unique"]
            and value["all_candidates_from_frozen_pool"]
            for value in scenario_checks.values()
        ),
        "screening_does_not_read_exact_reference": True,
        "frozen_scenario_inputs_only": True,
    }
    report = {
        "status": "pass" if all(global_checks.values()) else "fail",
        "global_checks": global_checks,
        "scenario_checks": scenario_checks,
        "total_primary_candidates": len(primary),
        "total_structural_reserve": len(reserve),
        "total_day5_eligible_sequences": len(combined),
        "scientific_quality_status": "pending_posthoc_frozen_screen_evaluation",
        "day5_permitted": False,
    }
    write_json(staging / "screening_verification_report.json", report)
    screened_path = staging / "screened_candidates.csv"
    freeze_record = {
        "schema_version": "1.0",
        "screened_candidates_sha256": sha256(screened_path),
        "screened_candidates_bytes": screened_path.stat().st_size,
        "primary_shortlist_sha256": sha256(staging / "primary_shortlist.csv"),
        "structural_reserve_sha256": sha256(staging / "structural_reserve.csv.gz"),
        "exact_reference_access_before_freeze": False,
        "posthoc_quality_evaluation_allowed": True,
    }
    write_json(staging / "screening_freeze_record.json", freeze_record)
    (staging / "结果说明.txt").write_text(
        "正式流程采用两层筛选。\n"
        "第一层保留每情景60条多通道优先短名单；第二层保留前缀、来源和代理秩分位分层的结构储备。\n"
        "结构储备不增加UE预算，只有实际发生的唯一UE状态缓存未命中计入预算。\n"
        "筛选文件已冻结，当前等待事后开发情景科学质量验收。\n",
        encoding="utf-8",
    )
    if report["status"] != "pass":
        raise RuntimeError("Day 4 v1.1 engineering gate failed")
    staging.replace(output)
    print(json.dumps({"output": str(output), "status": "engineering_pass", "primary": len(primary), "reserve": len(reserve), "combined": len(combined), "scenario_checks": scenario_checks}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
