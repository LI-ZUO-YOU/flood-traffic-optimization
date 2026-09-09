"""Apply a physical-link flood scenario to the directed traffic network."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .ue_static import StaticUESolver


def build_flooded_solver(
    links: pd.DataFrame,
    od: pd.DataFrame,
    scenario_arcs: pd.DataFrame,
) -> StaticUESolver:
    required = {"arc_id", "is_closed", "free_flow_time_multiplier", "capacity_factor"}
    missing = required.difference(scenario_arcs.columns)
    if missing:
        raise ValueError(f"Scenario is missing columns: {sorted(missing)}")

    scenario = scenario_arcs[list(required)].drop_duplicates("arc_id")
    merged = links.merge(scenario, on="arc_id", how="left", validate="one_to_one")
    if merged[list(required - {"arc_id"})].isna().any().any():
        raise ValueError("Scenario does not contain a disruption record for every directed arc")

    active = merged["is_closed"].to_numpy(dtype=int) == 0
    cap = merged["capacity"].to_numpy(dtype=float) * merged["capacity_factor"].to_numpy(dtype=float)
    fft = merged["free_flow_time"].to_numpy(dtype=float) * merged["free_flow_time_multiplier"].to_numpy(dtype=float)
    # Closed arcs are omitted from adjacency; replace their non-finite values only
    # to keep array validation and output serialization safe.
    cap[~active] = 1.0
    fft[~active] = 1.0e9
    return StaticUESolver(
        links,
        od,
        active=active,
        effective_capacity=cap,
        effective_free_flow_time=fft,
    )
