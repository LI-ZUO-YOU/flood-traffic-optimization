"""Flood-depth to road-disruption mappings used in the case study."""
from __future__ import annotations

import numpy as np


def pregnolato_speed_ratio(depth_m: np.ndarray | float, closure_depth_m: float = 0.30) -> np.ndarray:
    """Return safe-speed ratio from Pregnolato et al. (2017) central function.

    The polynomial uses water depth in millimetres and produces speed in km/h.
    The dry reference speed is 86.9448 km/h. Ordinary roads are marked closed
    at or above ``closure_depth_m`` for this study.
    """
    d = np.asarray(depth_m, dtype=float)
    w_mm = d * 1000.0
    v0 = 86.9448
    v = 0.0009 * w_mm**2 - 0.5529 * w_mm + v0
    v = np.clip(v, 0.0, v0)
    ratio = v / v0
    return np.where(d >= closure_depth_m, 0.0, ratio)


def disruption_from_depth(
    depth_m: np.ndarray | float,
    *,
    closure_depth_m: float = 0.30,
    capacity_reduction: bool = False,
) -> dict[str, np.ndarray]:
    """Map depth to speed, travel-time and optional capacity factors."""
    d = np.asarray(depth_m, dtype=float)
    ratio = pregnolato_speed_ratio(d, closure_depth_m=closure_depth_m)
    closed = d >= closure_depth_m
    tt_mult = np.full_like(ratio, np.inf, dtype=float)
    np.divide(1.0, ratio, out=tt_mult, where=ratio > 1e-12)
    if capacity_reduction:
        # Optional sensitivity mapping only; main analysis keeps capacity unchanged
        # for passable links to avoid double-counting speed and capacity impacts.
        capacity_factor = np.where(closed, 0.0, np.clip(ratio, 0.25, 1.0))
    else:
        capacity_factor = np.where(closed, 0.0, 1.0)
    return {
        "depth_m": d,
        "speed_ratio": ratio,
        "free_flow_time_multiplier": tt_mult,
        "capacity_factor": capacity_factor,
        "is_closed": closed,
    }
