from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import shutil
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


DEFAULT_SEED_BASE = 2026080702
TARGET_PER_SCENARIO = 30000
SOURCE_QUOTAS = {
    "prefix_stratified": 16000,
    "random": 5000,
    "proxy_subset_dp": 4000,
    "proxy_ga_local": 3000,
    "sequence_diversity": 2000,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def load_interface(path: Path):
    spec = importlib.util.spec_from_file_location("interfaces_week3_day3_v11", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def subset_member_losses(predictor, depth: np.ndarray, closed: np.ndarray, roads: list[int]) -> np.ndarray:
    states = []
    for mask in range(1 << len(roads)):
        restored = np.zeros(38, dtype=np.uint8)
        for bit, road in enumerate(roads):
            if mask & (1 << bit):
                restored[road - 1] = 1
        states.append({"depth_m": depth, "initial_closed": closed, "restored": restored})
    member_loss = np.exp(predictor.predict_members(states)) - 1.0
    if member_loss.shape != (1 << len(roads), 10) or not np.isfinite(member_loss).all():
        raise ValueError("Invalid 2^m-by-10 surrogate subset matrix")
    return member_loss


def successor_policy(cost: np.ndarray, roads: list[int]) -> dict[int, int]:
    n = len(roads)
    full = (1 << n) - 1
    value = np.full(full + 1, np.inf, dtype=float)
    successor: dict[int, int] = {}
    value[full] = 0.0
    for size in range(n - 1, -1, -1):
        for mask in range(full + 1):
            if mask.bit_count() != size:
                continue
            options = []
            for bit, road in enumerate(roads):
                if mask & (1 << bit):
                    continue
                next_mask = mask | (1 << bit)
                add_cost = 0.0 if next_mask == full else float(cost[next_mask])
                options.append((add_cost + value[next_mask], int(road), next_mask))
            best_value, best_road, _ = min(options)
            value[mask] = best_value
            successor[mask] = best_road
    return successor


def complete_by_policy(prefix: Sequence[int], roads: list[int], policy: dict[int, int]) -> tuple[int, ...]:
    road_to_bit = {road: bit for bit, road in enumerate(roads)}
    sequence = list(map(int, prefix))
    mask = 0
    for road in sequence:
        mask |= 1 << road_to_bit[road]
    while len(sequence) < len(roads):
        road = policy[mask]
        sequence.append(road)
        mask |= 1 << road_to_bit[road]
    return tuple(sequence)


class ProxyObjective:
    def __init__(self, member_loss: np.ndarray, roads: list[int]):
        self.member_loss = member_loss
        self.n = len(roads)
        self.road_to_bit = {road: bit for bit, road in enumerate(roads)}
        self.cache: dict[tuple[int, ...], tuple[float, np.ndarray]] = {}

    def evaluate(self, sequence: tuple[int, ...]) -> tuple[float, np.ndarray]:
        if sequence in self.cache:
            return self.cache[sequence]
        masks = [0]
        mask = 0
        for road in sequence[:self.n-1]:
            mask |= 1 << self.road_to_bit[road]
            masks.append(mask)
        member_objective = self.member_loss[masks].mean(axis=0)
        result = float(member_objective.mean()), member_objective
        self.cache[sequence] = result
        return result


def add_unique(
    registry: dict[tuple[int, ...], dict],
    sequence: Iterable[int],
    source: str,
    detail: str,
    counter: int,
) -> tuple[bool, int]:
    key = tuple(map(int, sequence))
    if key in registry:
        registry[key]["source_tags"].add(source)
        return False, counter
    registry[key] = {
        "primary_source": source,
        "source_detail": detail,
        "source_tags": {source},
        "generation_order": counter,
    }
    return True, counter + 1


def random_completion(prefix: tuple[int, ...], roads: list[int], rng: np.random.Generator) -> tuple[int, ...]:
    remaining = [road for road in roads if road not in prefix]
    return prefix + tuple(map(int, rng.permutation(remaining)))


def mutate(sequence: tuple[int, ...], rng: np.random.Generator) -> tuple[int, ...]:
    values = list(sequence)
    i, j = map(int, rng.choice(len(values), size=2, replace=False))
    if rng.random() < 0.5:
        values[i], values[j] = values[j], values[i]
    else:
        road = values.pop(i)
        values.insert(j, road)
    return tuple(values)


def permutation_from_rank(items: list[int], rank: int) -> tuple[int, ...]:
    available = list(items)
    result = []
    for remaining in range(len(items), 0, -1):
        factorial = math.factorial(remaining - 1)
        index, rank = divmod(rank, factorial)
        result.append(available.pop(index))
    return tuple(result)


def fill_prefix_stratified(
    registry: dict[tuple[int, ...], dict],
    roads: list[int],
    mean_policy: dict[int, int],
    member_policies: list[dict[int, int]],
    rng: np.random.Generator,
    counter: int,
) -> int:
    target = SOURCE_QUOTAS["prefix_stratified"]
    added = 0
    for prefix_index, prefix in enumerate(itertools.permutations(roads, 4)):
        candidates = [
            (complete_by_policy(prefix, roads, mean_policy), "all_ordered_prefix4_mean_dp_tail"),
            (complete_by_policy(prefix, roads, member_policies[prefix_index % 10]), "all_ordered_prefix4_member_dp_tail"),
            (random_completion(prefix, roads, rng), "all_ordered_prefix4_random_tail"),
        ]
        for sequence, detail in candidates:
            was_added, counter = add_unique(registry, sequence, "prefix_stratified", detail, counter)
            added += int(was_added)
    attempts = 0
    while added < target:
        attempts += 1
        prefix = tuple(map(int, rng.choice(roads, size=5, replace=False)))
        sequence = random_completion(prefix, roads, rng)
        was_added, counter = add_unique(registry, sequence, "prefix_stratified", "supplemental_prefix5_random_tail", counter)
        added += int(was_added)
        if attempts > 100000:
            raise RuntimeError("Could not fill prefix-stratified quota")
    return counter


def fill_proxy_dp(
    registry: dict[tuple[int, ...], dict],
    roads: list[int],
    member_loss: np.ndarray,
    mean_policy: dict[int, int],
    rng: np.random.Generator,
    counter: int,
) -> int:
    target = SOURCE_QUOTAS["proxy_subset_dp"]
    policies = [mean_policy]
    policies.extend(successor_policy(member_loss[:, index], roads) for index in range(10))
    sd = member_loss.std(axis=1, ddof=1)
    policies.extend([
        successor_policy(member_loss.mean(axis=1) + coefficient * sd, roads)
        for coefficient in (-1.0, -0.5, 0.5, 1.0)
    ])
    for _ in range(64):
        weights = rng.dirichlet(np.ones(10))
        policies.append(successor_policy(member_loss @ weights, roads))
    bases = []
    for policy in policies:
        sequence = complete_by_policy((), roads, policy)
        if sequence not in bases:
            bases.append(sequence)
    added = 0
    for index, sequence in enumerate(bases):
        was_added, counter = add_unique(registry, sequence, "proxy_subset_dp", f"proxy_dp_base_{index}", counter)
        added += int(was_added)
    cursor = 0
    attempts = 0
    while added < target:
        attempts += 1
        base = bases[cursor % len(bases)]
        cursor += 1
        candidate = mutate(base, rng)
        if rng.random() < 0.65:
            candidate = mutate(candidate, rng)
        was_added, counter = add_unique(registry, candidate, "proxy_subset_dp", "proxy_dp_swap_insert_neighborhood", counter)
        added += int(was_added)
        if attempts > 500000:
            raise RuntimeError("Could not fill proxy-DP quota")
    return counter


def fill_diversity(
    registry: dict[tuple[int, ...], dict],
    roads: list[int],
    scenario_seed: int,
    counter: int,
) -> int:
    target = SOURCE_QUOTAS["sequence_diversity"]
    total = math.factorial(len(roads))
    offset = scenario_seed % total
    added = 0
    index = 0
    while added < target:
        rank = (offset + ((2 * index + 1) * total) // (2 * target)) % total
        sequence = permutation_from_rank(roads, rank)
        was_added, counter = add_unique(registry, sequence, "sequence_diversity", "factoradic_even_rank_design", counter)
        added += int(was_added)
        index += 1
        if index > target * 10:
            offset = (offset + 1) % total
    return counter


def fill_random(
    registry: dict[tuple[int, ...], dict],
    roads: list[int],
    rng: np.random.Generator,
    counter: int,
) -> int:
    target = SOURCE_QUOTAS["random"]
    added = 0
    while added < target:
        sequence = tuple(map(int, rng.permutation(roads)))
        was_added, counter = add_unique(registry, sequence, "random", "independent_uniform_permutation", counter)
        added += int(was_added)
    return counter


def fill_ga_local_from_registry(
    registry: dict[tuple[int, ...], dict],
    objective: ProxyObjective,
    roads: list[int],
    rng: np.random.Generator,
    counter: int,
) -> int:
    target = SOURCE_QUOTAS["proxy_ga_local"]
    ranked = sorted(
        ((objective.evaluate(sequence)[0], sequence) for sequence in registry),
        key=lambda item: (item[0], item[1]),
    )
    bases = [sequence for _, sequence in ranked[:2500]]
    if not bases:
        raise RuntimeError("No frozen proxy candidates are available for GA/local mutation")
    added = 0
    cursor = 0
    attempts = 0
    while added < target:
        attempts += 1
        sequence = mutate(bases[cursor % len(bases)], rng)
        cursor += 1
        if rng.random() < 0.35:
            sequence = mutate(sequence, rng)
        was_added, counter = add_unique(
            registry,
            sequence,
            "proxy_ga_local",
            "frozen_proxy_elite_swap_insert_neighborhood",
            counter,
        )
        added += int(was_added)
        if attempts > 500000:
            raise RuntimeError("Could not fill GA/local quota")
    return counter


def candidate_row(scenario_id: int, sequence: tuple[int, ...], metadata: dict, objective: ProxyObjective) -> dict:
    proxy_mean, members = objective.evaluate(sequence)
    row = {
        "scenario_id": scenario_id,
        "candidate_id": hashlib.sha256(f"{scenario_id}|{'|'.join(map(str, sequence))}".encode()).hexdigest(),
        "sequence": "|".join(map(str, sequence)),
        "primary_source": metadata["primary_source"],
        "source_detail": metadata["source_detail"],
        "source_tags": "|".join(sorted(metadata["source_tags"])),
        "generation_order": metadata["generation_order"],
        "proxy_objective_mean": proxy_mean,
        "ensemble_disagreement": float(np.std(members, ddof=1)),
    }
    for index, road in enumerate(sequence, 1):
        row[f"road_{index:02d}"] = road
    for index, value in enumerate(members, 1):
        row[f"member_{index:02d}_objective"] = float(value)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the frozen 30,000-sequence candidate pool for arbitrary final scenarios.")
    parser.add_argument("--scenario-metadata", required=True)
    parser.add_argument("--scenario-physical", required=True)
    parser.add_argument("--surrogate-root", required=True)
    parser.add_argument("--interface", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scenario-count", required=True, type=int)
    parser.add_argument("--seed-base", type=int, default=DEFAULT_SEED_BASE)
    parser.add_argument("--python-dependency", action="append", default=[])
    args = parser.parse_args()

    output = Path(args.output_dir)
    staging = output.with_name(f".{output.name}_staging")
    metadata_path = Path(args.scenario_metadata)
    scenario_file = Path(args.scenario_physical)
    surrogate_dir = Path(args.surrogate_root)
    interface_file = Path(args.interface)
    python_deps = [Path(value) for value in args.python_dependency]
    if output.exists() or staging.exists():
        raise FileExistsError("Candidate output or staging already exists")
    staging.mkdir(parents=True)
    (staging / "scripts").mkdir()
    shutil.copy2(Path(__file__), staging / "scripts" / Path(__file__).name)
    started = time.perf_counter()

    development = json.loads(metadata_path.read_text(encoding="utf-8"))
    scenario_ids = list(map(int, development.get("selected_scenario_ids", [row["scenario_id"] for row in development["scenarios"]])))
    if len(scenario_ids) != args.scenario_count or len(set(scenario_ids)) != args.scenario_count:
        raise ValueError(f"Expected {args.scenario_count} unique scenarios; found {len(set(scenario_ids))}")
    roads_by_scenario = {
        int(row["scenario_id"]): list(map(int, row["selected_recoverable_roads"]))
        for row in development["scenarios"]
    }
    physical = pd.read_csv(scenario_file)
    api = load_interface(interface_file)
    predictor = api.SurrogateV2(surrogate_dir, dependency_paths=python_deps)

    frames = []
    scenario_reports = {}
    for scenario_id in scenario_ids:
        rng = np.random.default_rng(args.seed_base + scenario_id)
        roads = roads_by_scenario[scenario_id]
        scenario = physical.loc[physical["scenario_id"] == scenario_id].sort_values("physical_link_id")
        if len(scenario) != 38:
            raise ValueError(f"Scenario {scenario_id}: expected 38 physical-link rows; found {len(scenario)}")
        member_loss = subset_member_losses(
            predictor,
            scenario["depth_m"].to_numpy(float),
            scenario["is_closed"].to_numpy(np.uint8),
            roads,
        )
        objective = ProxyObjective(member_loss, roads)
        mean_policy = successor_policy(member_loss.mean(axis=1), roads)
        member_policies = [successor_policy(member_loss[:, index], roads) for index in range(10)]
        registry: dict[tuple[int, ...], dict] = {}
        counter = 0
        counter = fill_prefix_stratified(registry, roads, mean_policy, member_policies, rng, counter)
        counter = fill_proxy_dp(registry, roads, member_loss, mean_policy, rng, counter)
        counter = fill_diversity(registry, roads, args.seed_base + scenario_id, counter)
        counter = fill_random(registry, roads, rng, counter)
        counter = fill_ga_local_from_registry(
            registry,
            objective,
            roads,
            rng,
            counter,
        )
        if len(registry) != TARGET_PER_SCENARIO:
            raise AssertionError(f"Expected {TARGET_PER_SCENARIO}; generated {len(registry)}")
        frame = pd.DataFrame([
            candidate_row(scenario_id, sequence, metadata, objective)
            for sequence, metadata in registry.items()
        ]).sort_values(["proxy_objective_mean", "candidate_id"], kind="mergesort").reset_index(drop=True)
        frame["proxy_rank"] = np.arange(1, len(frame) + 1)
        frames.append(frame)
        prefixes = frame["sequence"].str.split("|")
        source_counts = Counter(frame["primary_source"])
        scenario_reports[str(scenario_id)] = {
            "candidate_count": len(frame),
            "unique_sequences": int(frame["sequence"].nunique()),
            "unique_candidate_ids": int(frame["candidate_id"].nunique()),
            "primary_source_counts": dict(sorted(source_counts.items())),
            "ordered_prefix_1_coverage": int(prefixes.map(lambda x: tuple(x[:1])).nunique()),
            "ordered_prefix_2_coverage": int(prefixes.map(lambda x: tuple(x[:2])).nunique()),
            "ordered_prefix_3_coverage": int(prefixes.map(lambda x: tuple(x[:3])).nunique()),
            "ordered_prefix_4_coverage": int(prefixes.map(lambda x: tuple(x[:4])).nunique()),
            "all_proxy_outputs_finite": bool(np.isfinite(frame[["proxy_objective_mean", "ensemble_disagreement"]]).all().all()),
            "best_proxy_objective": float(frame["proxy_objective_mean"].min()),
            "median_proxy_objective": float(frame["proxy_objective_mean"].median()),
        }
        print(json.dumps({"event": "scenario_complete", "scenario_id": scenario_id, **scenario_reports[str(scenario_id)]}, ensure_ascii=False), flush=True)

    pool = pd.concat(frames, ignore_index=True).sort_values(["scenario_id", "proxy_rank"])
    pool_path = staging / "candidate_pool.csv.gz"
    pool.to_csv(pool_path, index=False, encoding="utf-8", compression={"method": "gzip", "compresslevel": 9, "mtime": 0})
    config = {
        "schema_version": "week3-day3-v1.1",
        "random_seed_base": args.seed_base,
        "candidate_count_per_scenario": TARGET_PER_SCENARIO,
        "source_quotas": SOURCE_QUOTAS,
        "prefix_design": {
            "all_5040_ordered_length4_prefixes_covered": True,
            "completion_per_prefix": ["ensemble_mean_proxy_dp", "rotating_member_proxy_dp", "random"],
            "supplement": "random length-5 prefixes with random completion",
        },
        "proxy_subset_dp": "ensemble mean, ten members, mean-plus/minus-SD and 64 Dirichlet member mixtures",
        "sequence_diversity": "evenly spaced factoradic permutation ranks",
        "proxy_objective": "R0-R9 mean predicted loss; R10 zero weight",
        "information_boundary": {
            "generation_reads_exact_reference": False,
            "generation_reads_subset_ue_costs": False,
            "generation_reads_exact_dp_solution": False,
            "posthoc_quality_evaluation_must_run_only_after_pool_hash_freeze": True,
            "final_scenario_inputs_frozen_before_candidate_generation": True,
        },
        "later_screening_revision": {
            "unconditional_high_disagreement_forbidden": True,
            "disagreement_eligibility": "proxy rank within top 30 percent",
            "primary_decision_metric": "true UE relative regret",
            "near_optimal_thresholds": [0.001, 0.005, 0.01, 0.015],
        },
        "source_sha256": {
            "scenario_metadata": sha256(metadata_path),
            "physical_scenarios": sha256(scenario_file),
            "formal_interface": sha256(interface_file),
            "surrogate/preprocessor_v2.json": sha256(surrogate_dir / "preprocessor_v2.json"),
            **{f"surrogate/models/{path.name}": sha256(path) for path in sorted((surrogate_dir / "models").glob("member_*.pt"))},
        },
    }
    write_json(staging / "candidate_generation_config.json", config)
    global_checks = {
        "exactly_30000_per_scenario": all(value["candidate_count"] == TARGET_PER_SCENARIO for value in scenario_reports.values()),
        "all_sequences_unique": all(value["unique_sequences"] == TARGET_PER_SCENARIO for value in scenario_reports.values()),
        "all_candidate_ids_unique": all(value["unique_candidate_ids"] == TARGET_PER_SCENARIO for value in scenario_reports.values()),
        "source_quotas_exact": all(value["primary_source_counts"] == dict(sorted(SOURCE_QUOTAS.items())) for value in scenario_reports.values()),
        "complete_prefix1_coverage": all(value["ordered_prefix_1_coverage"] == 10 for value in scenario_reports.values()),
        "complete_prefix2_coverage": all(value["ordered_prefix_2_coverage"] == 90 for value in scenario_reports.values()),
        "complete_prefix3_coverage": all(value["ordered_prefix_3_coverage"] == 720 for value in scenario_reports.values()),
        "complete_prefix4_coverage": all(value["ordered_prefix_4_coverage"] == 5040 for value in scenario_reports.values()),
        "all_proxy_outputs_finite": all(value["all_proxy_outputs_finite"] for value in scenario_reports.values()),
        "exact_reference_not_read_during_generation": True,
        "scenario_count_matches_cli": len(scenario_reports) == args.scenario_count,
    }
    engineering_report = {
        "status": "pass" if all(global_checks.values()) else "fail",
        "global_checks": global_checks,
        "scenario_reports": scenario_reports,
        "total_candidates": len(pool),
        "generation_elapsed_seconds": time.perf_counter() - started,
        "scientific_quality_status": "pending_posthoc_frozen_pool_evaluation",
        "day4_permitted": False,
    }
    write_json(staging / "candidate_uniqueness_report.json", engineering_report)
    freeze = {
        "schema_version": "1.0",
        "candidate_pool_sha256": sha256(pool_path),
        "candidate_pool_bytes": pool_path.stat().st_size,
        "candidate_count": len(pool),
        "generator_script_sha256": sha256(staging / "scripts" / Path(__file__).name),
        "exact_reference_access_before_freeze": False,
        "quality_evaluation_allowed_after_this_record": True,
    }
    write_json(staging / "generation_freeze_record.json", freeze)
    (staging / "结果说明.txt").write_text(
        "正式候选池已完成工程生成。\n"
        f"{args.scenario_count}个冻结情景各30000条唯一序列，全部5040种有序四道路前缀均被覆盖。\n"
        "候选池哈希已冻结；生成阶段未读取精确DP、真实UE子集成本或精确缓存。\n"
        "当前科学质量状态为待事后验收，尚不允许进入第4天。\n",
        encoding="utf-8",
    )
    manifest = {}
    for path in sorted(staging.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest_generation.json" and path.suffix != ".pyc":
            manifest[str(path.relative_to(staging)).replace("\\", "/")] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    write_json(staging / "artifact_manifest_generation.json", {"schema_version": "1.1", "files": manifest})
    if engineering_report["status"] != "pass":
        raise RuntimeError("Day 3 v1.1 engineering gate failed")
    staging.replace(output)
    print(json.dumps({"output": str(output), "status": "engineering_pass", "rows": len(pool), "pool_sha256": freeze["candidate_pool_sha256"]}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
