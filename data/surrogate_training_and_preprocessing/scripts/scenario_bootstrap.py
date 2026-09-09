from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


def generate_bootstrap_plan(
    scenario_ids: list[int],
    scenario_row_counts: dict[int, int],
    n_members: int = 10,
    bootstrap_seed_base: int = 202608100,
    initialization_seed_base: int = 202608200,
) -> dict:
    """Generate deterministic scenario-level bootstrap plans.

    Each member draws ``len(scenario_ids)`` complete scenarios with replacement.
    Scenarios not selected are the member's out-of-bag validation scenarios.
    """
    scenarios = sorted(int(value) for value in scenario_ids)
    if not scenarios:
        raise ValueError("scenario_ids must not be empty")
    if set(scenarios) != {int(k) for k in scenario_row_counts}:
        raise ValueError("scenario_row_counts keys must exactly match scenario_ids")

    members = []
    for member_index in range(1, n_members + 1):
        bootstrap_seed = bootstrap_seed_base + member_index
        initialization_seed = initialization_seed_base + member_index
        rng = np.random.default_rng(bootstrap_seed)
        draws = [int(value) for value in rng.choice(scenarios, size=len(scenarios), replace=True)]
        multiplicity = Counter(draws)
        oob = [scenario_id for scenario_id in scenarios if scenario_id not in multiplicity]
        if not oob:
            raise RuntimeError(f"member {member_index} has no OOB scenario; change seed")

        conceptual_rows = sum(
            int(multiplicity[scenario_id]) * int(scenario_row_counts[scenario_id])
            for scenario_id in multiplicity
        )
        unique_inbag_rows = sum(int(scenario_row_counts[s]) for s in multiplicity)
        oob_rows = sum(int(scenario_row_counts[s]) for s in oob)
        members.append(
            {
                "member_id": f"member_{member_index:02d}",
                "bootstrap_seed": bootstrap_seed,
                "initialization_seed": initialization_seed,
                "draw_count": len(draws),
                "drawn_scenario_ids": draws,
                "scenario_multiplicity": {str(k): int(v) for k, v in sorted(multiplicity.items())},
                "unique_inbag_scenario_count": len(multiplicity),
                "oob_scenario_ids": oob,
                "oob_scenario_count": len(oob),
                "conceptual_inbag_row_count_with_repeats": conceptual_rows,
                "unique_inbag_row_count": unique_inbag_rows,
                "oob_row_count": oob_rows,
            }
        )

    return {
        "schema_version": "1.0",
        "sampling_unit": "scenario_id",
        "sampling_with_replacement": True,
        "draws_per_member": len(scenarios),
        "training_scenario_count": len(scenarios),
        "n_members": n_members,
        "bootstrap_seed_base": bootstrap_seed_base,
        "initialization_seed_base": initialization_seed_base,
        "weighting_rule": (
            "For scenario s with n_s states and bootstrap multiplicity b_ms, use raw row weight "
            "b_ms/n_s for member m; divide weighted loss by the sum of active weights."
        ),
        "members": members,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate scenario-level bootstrap plans.")
    parser.add_argument("train_csv", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--members", type=int, default=10)
    args = parser.parse_args()

    frame = pd.read_csv(args.train_csv, usecols=["scenario_id"])
    counts = frame.groupby("scenario_id").size().astype(int).to_dict()
    plan = generate_bootstrap_plan(
        scenario_ids=sorted(counts),
        scenario_row_counts={int(k): int(v) for k, v in counts.items()},
        n_members=args.members,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output_json)


if __name__ == "__main__":
    main()
