"""Spatially correlated synthetic flood-depth field generator.

For the 38 physical links of Sioux Falls, direct covariance-matrix Cholesky
sampling is simpler and numerically adequate. The structure follows standard
Gaussian random-field simulation; an optional smooth storm-centre component
creates coherent local flooding clusters.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from .flood_mapping import disruption_from_depth


@dataclass(frozen=True)
class SeveritySpec:
    blocked_min: int
    blocked_max: int
    wet_min: int
    wet_max: int
    corr_min_km: float
    corr_max_km: float
    passable_depth_max_m: float
    closed_depth_max_m: float


SPECS = {
    "mild": SeveritySpec(1, 3, 7, 10, 2.0, 4.0, 0.22, 0.45),
    "moderate": SeveritySpec(4, 7, 13, 18, 2.5, 5.0, 0.285, 0.48),
    "severe": SeveritySpec(8, 12, 20, 28, 3.0, 6.0, 0.285, 0.55),
}


def gaussian_covariance(xy: np.ndarray, correlation_length_km: float, nugget: float = 1e-8) -> np.ndarray:
    xy = np.asarray(xy, dtype=float)
    dist = np.linalg.norm(xy[:, None, :] - xy[None, :, :], axis=2)
    cov = np.exp(-0.5 * (dist / correlation_length_km) ** 2)
    cov.flat[:: len(cov) + 1] += nugget
    return cov


def generate_correlated_depths(
    physical_links: pd.DataFrame,
    *,
    severity: str,
    seed: int,
    closure_depth_m: float = 0.30,
) -> tuple[pd.DataFrame, dict]:
    """Generate one clustered flood-depth realization on physical link midpoints."""
    if severity not in SPECS:
        raise ValueError(f"severity must be one of {sorted(SPECS)}")
    spec = SPECS[severity]
    rng = np.random.default_rng(seed)
    xy = physical_links[["mid_x_km", "mid_y_km"]].to_numpy(dtype=float)
    n = len(xy)
    blocked = int(rng.integers(spec.blocked_min, spec.blocked_max + 1))
    wet_total = int(rng.integers(spec.wet_min, min(spec.wet_max, n) + 1))
    wet_total = max(wet_total, blocked)
    corr = float(rng.uniform(spec.corr_min_km, spec.corr_max_km))

    cov = gaussian_covariance(xy, corr)
    chol = np.linalg.cholesky(cov)
    latent = chol @ rng.standard_normal(n)

    center_idx = int(rng.integers(0, n))
    center = xy[center_idx]
    radial_scale = float(rng.uniform(2.0, 5.0))
    radial = np.exp(-0.5 * (np.linalg.norm(xy - center, axis=1) / radial_scale) ** 2)
    latent += float(rng.uniform(0.5, 1.2)) * radial

    order = np.argsort(latent)[::-1]
    closed_idx = order[:blocked]
    passable_idx = order[blocked:wet_total]
    depth = np.zeros(n, dtype=float)

    if len(closed_idx):
        ranks = np.linspace(1.0, 0.0, len(closed_idx), endpoint=False)
        depth[closed_idx] = closure_depth_m + (spec.closed_depth_max_m - closure_depth_m) * (0.35 + 0.65 * ranks)
        depth[closed_idx] += rng.normal(0.0, 0.008, len(closed_idx))
        depth[closed_idx] = np.maximum(depth[closed_idx], closure_depth_m + 1e-4)

    if len(passable_idx):
        ranks = np.linspace(1.0, 0.0, len(passable_idx), endpoint=False)
        low = 0.03 if severity == "mild" else 0.05
        depth[passable_idx] = low + (spec.passable_depth_max_m - low) * (0.15 + 0.85 * ranks)
        depth[passable_idx] += rng.normal(0.0, 0.006, len(passable_idx))
        depth[passable_idx] = np.clip(depth[passable_idx], 0.0, closure_depth_m - 1e-3)

    mapping = disruption_from_depth(depth, closure_depth_m=closure_depth_m)
    out = physical_links.copy()
    out["depth_m"] = depth
    out["is_wet"] = (depth > 0).astype(int)
    out["is_closed"] = mapping["is_closed"].astype(int)
    out["speed_ratio"] = mapping["speed_ratio"]
    out["free_flow_time_multiplier"] = mapping["free_flow_time_multiplier"]
    out["capacity_factor"] = mapping["capacity_factor"]

    meta = {
        "seed": int(seed),
        "severity": severity,
        "blocked_physical_links": int(out["is_closed"].sum()),
        "wet_physical_links": int(out["is_wet"].sum()),
        "correlation_length_km": corr,
        "storm_center_physical_link_id": int(physical_links.iloc[center_idx]["physical_link_id"]),
        "storm_radial_scale_km": radial_scale,
    }
    return out, meta
