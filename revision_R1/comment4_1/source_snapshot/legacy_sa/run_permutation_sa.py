from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEV_TABLE = Path(
    r"D:\sci-jcr2区交付\第三周工作\day2_exact_dp_baseline_v1.1\subset_ue_costs.csv"
)
FINAL_TABLE = Path(
    r"D:\sci-jcr2区交付\第四周工作\day4_exact_reference_regret_v1.0"
    r"\08_exact_reference_after_method_freeze\subset_ue_costs.csv"
)
OUTPUT = Path(
    r"D:\sci-jcr2区交付\第四周工作\P1_poststudy_permutation_SA_v1.0"
)
BUDGET = 256
N_ROADS = 10


@dataclass(frozen=True)
class SAConfig:
    initial_temperature_ratio: float
    cooling_rate: float
    adjacent_probability: float
    insertion_probability: float
    max_stalled_proposals: int = 1000


class LogicalUEOracle:
    """Expose exact-cache values only after a method-specific logical query."""

    def __init__(self, loss_by_mask: dict[int, float], budget: int) -> None:
        self._loss_by_mask = loss_by_mask
        self.budget = budget
        self.queried: set[int] = set()
        self.ledger: list[dict] = []

    @property
    def remaining(self) -> int:
        return self.budget - len(self.queried)

    def evaluate_sequence(self, sequence: tuple[int, ...], iteration: int) -> float | None:
        mask = 0
        masks = [0]
        for bit in sequence[:-1]:
            mask |= 1 << bit
            masks.append(mask)
        missing = [state for state in masks if state not in self.queried]
        if len(missing) > self.remaining:
            return None
        for state in missing:
            self.queried.add(state)
            self.ledger.append(
                {
                    "logical_query_index": len(self.queried),
                    "iteration": iteration,
                    "subset_mask": state,
                    "restored_count": int(state.bit_count()),
                    "loss": self._loss_by_mask[state],
                }
            )
        return float(np.mean([self._loss_by_mask[state] for state in masks]))


def objective_from_table(sequence: tuple[int, ...], loss_by_mask: dict[int, float]) -> float:
    mask = 0
    values = [loss_by_mask[0]]
    for bit in sequence[:-1]:
        mask |= 1 << bit
        values.append(loss_by_mask[mask])
    return float(np.mean(values))


def exact_dp(loss_by_mask: dict[int, float]) -> tuple[float, tuple[int, ...]]:
    full = (1 << N_ROADS) - 1
    value = np.full(full + 1, np.inf)
    predecessor = np.full(full + 1, -1, dtype=int)
    value[0] = loss_by_mask[0]
    for mask in range(1, full + 1):
        stage_cost = 0.0 if mask == full else loss_by_mask[mask]
        for bit in range(N_ROADS):
            if mask & (1 << bit):
                previous = mask ^ (1 << bit)
                candidate = value[previous] + stage_cost
                if candidate < value[mask] - 1e-15:
                    value[mask] = candidate
                    predecessor[mask] = bit
    reversed_bits: list[int] = []
    mask = full
    while mask:
        bit = int(predecessor[mask])
        reversed_bits.append(bit)
        mask ^= 1 << bit
    sequence = tuple(reversed(reversed_bits))
    return float(value[full] / N_ROADS), sequence


def propose(sequence: tuple[int, ...], rng: np.random.Generator, config: SAConfig) -> tuple[int, ...]:
    candidate = list(sequence)
    draw = float(rng.random())
    if draw < config.adjacent_probability:
        i = int(rng.integers(0, N_ROADS - 1))
        candidate[i], candidate[i + 1] = candidate[i + 1], candidate[i]
    elif draw < config.adjacent_probability + config.insertion_probability:
        i, j = rng.choice(N_ROADS, size=2, replace=False).tolist()
        item = candidate.pop(i)
        candidate.insert(j, item)
    else:
        i, j = rng.choice(N_ROADS, size=2, replace=False).tolist()
        candidate[i], candidate[j] = candidate[j], candidate[i]
    return tuple(candidate)


def run_sa(
    scenario_id: int,
    loss_by_mask: dict[int, float],
    config: SAConfig,
    *,
    seed: int,
    budget: int = BUDGET,
) -> tuple[dict, list[dict], list[dict]]:
    rng = np.random.default_rng(seed)
    oracle = LogicalUEOracle(loss_by_mask, budget)
    current = tuple(int(x) for x in rng.permutation(N_ROADS))
    current_objective = oracle.evaluate_sequence(current, iteration=0)
    assert current_objective is not None
    best = current
    best_objective = current_objective
    history = [
        {
            "iteration": 0,
            "temperature": config.initial_temperature_ratio * max(abs(current_objective), 1.0),
            "current_objective": current_objective,
            "best_objective": best_objective,
            "accepted": True,
            "improved_best": True,
            "queried_states": len(oracle.queried),
            "sequence_bits": "-".join(map(str, current)),
        }
    ]
    stalled = 0
    iteration = 0
    while stalled < config.max_stalled_proposals and oracle.remaining > 0:
        iteration += 1
        candidate = propose(current, rng, config)
        candidate_objective = oracle.evaluate_sequence(candidate, iteration)
        if candidate_objective is None:
            stalled += 1
            continue
        stalled = 0 if len(oracle.ledger) and oracle.ledger[-1]["iteration"] == iteration else stalled + 1
        temperature = (
            config.initial_temperature_ratio
            * max(abs(current_objective), 1.0)
            * (config.cooling_rate ** iteration)
        )
        delta = candidate_objective - current_objective
        accepted = delta <= 0 or float(rng.random()) < math.exp(-delta / max(temperature, 1e-15))
        if accepted:
            current = candidate
            current_objective = candidate_objective
        improved = candidate_objective < best_objective - 1e-15
        if improved:
            best = candidate
            best_objective = candidate_objective
        history.append(
            {
                "iteration": iteration,
                "temperature": temperature,
                "candidate_objective": candidate_objective,
                "current_objective": current_objective,
                "best_objective": best_objective,
                "accepted": accepted,
                "improved_best": improved,
                "queried_states": len(oracle.queried),
                "sequence_bits": "-".join(map(str, candidate)),
            }
        )

    exact_objective, exact_sequence = exact_dp(loss_by_mask)
    regret_pct = 100.0 * (best_objective - exact_objective) / exact_objective
    result = {
        "scenario_id": scenario_id,
        "seed": seed,
        "budget": budget,
        "queried_states": len(oracle.queried),
        "best_objective": best_objective,
        "exact_objective": exact_objective,
        "relative_regret_pct": regret_pct,
        "best_sequence_bits": list(best),
        "exact_sequence_bits": list(exact_sequence),
        "iterations_completed": iteration,
        "accepted_moves": int(sum(bool(row.get("accepted")) for row in history[1:])),
        "configuration": asdict(config),
    }
    return result, history, oracle.ledger


def tables_by_scenario(path: Path) -> dict[int, dict[int, float]]:
    frame = pd.read_csv(path, usecols=["scenario_id", "subset_mask", "loss"])
    grouped: dict[int, dict[int, float]] = {}
    for scenario_id, group in frame.groupby("scenario_id", sort=True):
        loss = dict(zip(group["subset_mask"].astype(int), group["loss"].astype(float)))
        if len(loss) != 1 << N_ROADS:
            raise ValueError(f"Scenario {scenario_id} has {len(loss)} states, expected 1024")
        grouped[int(scenario_id)] = loss
    return grouped


def parameter_grid() -> Iterable[SAConfig]:
    for temperature in (0.0025, 0.005, 0.01, 0.02):
        for cooling in (0.97, 0.985, 0.995):
            for adjacent, insertion in ((0.5, 0.25), (0.7, 0.15)):
                yield SAConfig(temperature, cooling, adjacent, insertion)


def config_key(config: SAConfig) -> str:
    payload = json.dumps(asdict(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "development_tuning").mkdir(exist_ok=True)
    (OUTPUT / "final_once_only").mkdir(exist_ok=True)

    dev = tables_by_scenario(DEV_TABLE)
    final = tables_by_scenario(FINAL_TABLE)
    dev_ids = [246, 247, 249]
    tuning_rows: list[dict] = []
    for config in parameter_grid():
        key = config_key(config)
        for scenario_id in dev_ids:
            result, _, _ = run_sa(
                scenario_id,
                dev[scenario_id],
                config,
                seed=2026081000 + scenario_id,
            )
            tuning_rows.append({"config_id": key, **result})

    tuning = pd.DataFrame(tuning_rows)
    tuning.to_csv(OUTPUT / "development_tuning" / "all_configuration_runs.csv", index=False)
    summary = (
        tuning.groupby("config_id", sort=True)
        .agg(
            mean_regret_pct=("relative_regret_pct", "mean"),
            median_regret_pct=("relative_regret_pct", "median"),
            max_regret_pct=("relative_regret_pct", "max"),
            mean_queries=("queried_states", "mean"),
        )
        .reset_index()
        .sort_values(
            ["mean_regret_pct", "median_regret_pct", "max_regret_pct", "config_id"],
            kind="mergesort",
        )
    )
    summary.to_csv(OUTPUT / "development_tuning" / "configuration_summary.csv", index=False)
    selected_id = str(summary.iloc[0]["config_id"])
    selected_dict = tuning.loc[tuning["config_id"].eq(selected_id), "configuration"].iloc[0]
    if isinstance(selected_dict, str):
        selected_dict = json.loads(selected_dict.replace("'", '"'))
    selected = SAConfig(**selected_dict)

    freeze = {
        "method": "budget-constrained permutation simulated annealing",
        "status": "additional post-study comparator configured using development scenarios only",
        "development_scenarios": dev_ids,
        "final_scenarios": sorted(final),
        "final_run_policy": "one run per final scenario; no retuning; all outcomes reported",
        "budget_definition": "method-specific unique high-fidelity restored-subset queries",
        "budget": BUDGET,
        "selected_config_id": selected_id,
        "selected_configuration": asdict(selected),
        "seed_rule": "2026081000 + scenario_id",
        "logical_firewall": (
            "The physical exact table is used as a deterministic UE-result cache. The SA search "
            "can access a state's loss only through the logical oracle after requesting its subset mask."
        ),
        "development_table": str(DEV_TABLE),
        "final_table": str(FINAL_TABLE),
    }
    freeze_text = json.dumps(freeze, indent=2, sort_keys=True)
    (OUTPUT / "sa_configuration_freeze.json").write_text(freeze_text, encoding="utf-8")
    (OUTPUT / "sa_configuration_freeze_hash.txt").write_text(
        hashlib.sha256(freeze_text.encode("utf-8")).hexdigest() + "\n", encoding="ascii"
    )

    final_rows: list[dict] = []
    for scenario_id in sorted(final):
        result, history, ledger = run_sa(
            scenario_id,
            final[scenario_id],
            selected,
            seed=2026081000 + scenario_id,
        )
        scenario_dir = OUTPUT / "final_once_only" / f"scenario_{scenario_id}"
        scenario_dir.mkdir(exist_ok=True)
        pd.DataFrame(history).to_csv(scenario_dir / "sa_history.csv", index=False)
        pd.DataFrame(ledger).to_csv(scenario_dir / "logical_ue_query_ledger.csv", index=False)
        (scenario_dir / "result.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        final_rows.append(result)

    final_frame = pd.DataFrame(final_rows)
    final_frame.to_csv(OUTPUT / "final_once_only" / "sa_final_results.csv", index=False)
    regrets = final_frame["relative_regret_pct"].to_numpy(float)
    aggregate = {
        "n_final_scenarios": int(len(final_frame)),
        "budget": BUDGET,
        "median_regret_pct": float(np.median(regrets)),
        "p90_regret_pct_numpy_linear": float(np.quantile(regrets, 0.9, method="linear")),
        "max_regret_pct": float(np.max(regrets)),
        "exact_objective_hit_count_tolerance_1e-9": int(
            np.sum(np.abs(final_frame["best_objective"] - final_frame["exact_objective"]) <= 1e-9)
        ),
        "within_1_5_pct_count": int(np.sum(regrets <= 1.5)),
        "within_3_pct_count": int(np.sum(regrets <= 3.0)),
        "query_counts": sorted(final_frame["queried_states"].astype(int).unique().tolist()),
        "selected_config_id": selected_id,
    }
    (OUTPUT / "final_once_only" / "sa_aggregate_summary.json").write_text(
        json.dumps(aggregate, indent=2), encoding="utf-8"
    )
    print(json.dumps({"freeze": freeze, "aggregate": aggregate}, indent=2))


if __name__ == "__main__":
    main()
