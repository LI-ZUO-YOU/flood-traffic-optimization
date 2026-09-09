"""Generate spatially correlated flood scenarios constrained to keep all OD pairs connected.

This constraint is required because TSTT-based static UE is undefined for positive
OD demand with no available path. Closed links are selected from the high-depth
spatial field while skipping removals that would disconnect the physical network.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models.flood_mapping import disruption_from_depth
from models.spatial_flood_field import SPECS, gaussian_covariance

DATA = ROOT / "data_src" / "SiouxFalls_flood_benchmark"
OUT = ROOT / "data_connected"
OUT.mkdir(exist_ok=True)
SEED = 20260803
PLAN = {
    "train": [("mild", 30), ("moderate", 30)],
    "calibration": [("mild", 10), ("moderate", 10)],
    "test_id": [("mild", 10), ("moderate", 10)],
    "test_severe": [("severe", 20)],
}


def connected_after_removal(nodes: np.ndarray, edges: list[tuple[int, int]], removed: set[int]) -> bool:
    adj = {int(n): [] for n in nodes}
    for i, (u, v) in enumerate(edges):
        if i in removed:
            continue
        adj[u].append(v)
        adj[v].append(u)
    start = int(nodes[0])
    seen = {start}
    stack = [start]
    while stack:
        u = stack.pop()
        for v in adj[u]:
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return len(seen) == len(nodes)


def choose_connected_closures(nodes: np.ndarray, edges: list[tuple[int, int]], ranking: np.ndarray, target: int) -> list[int]:
    removed: set[int] = set()
    for idx in ranking:
        trial = removed | {int(idx)}
        if connected_after_removal(nodes, edges, trial):
            removed = trial
            if len(removed) == target:
                break
    if len(removed) != target:
        raise RuntimeError(f"Could only select {len(removed)} connectivity-preserving closures; target={target}")
    # Preserve spatial-field order for deterministic depth ranks.
    return [int(i) for i in ranking if int(i) in removed]


def generate_one(physical: pd.DataFrame, severity: str, rng: np.random.Generator):
    spec = SPECS[severity]
    xy = physical[["mid_x_km", "mid_y_km"]].to_numpy(float)
    nodes = np.unique(physical[["physical_from", "physical_to"]].to_numpy().ravel()).astype(int)
    edges = [(int(u), int(v)) for u, v in physical[["physical_from", "physical_to"]].itertuples(index=False, name=None)]
    n = len(physical)

    blocked_target = int(rng.integers(spec.blocked_min, spec.blocked_max + 1))
    wet_target = int(rng.integers(spec.wet_min, min(spec.wet_max, n) + 1))
    wet_target = max(wet_target, blocked_target)
    corr = float(rng.uniform(spec.corr_min_km, spec.corr_max_km))

    cov = gaussian_covariance(xy, corr)
    latent = np.linalg.cholesky(cov) @ rng.standard_normal(n)
    center_idx = int(rng.integers(0, n))
    center = xy[center_idx]
    radial_scale = float(rng.uniform(2.0, 5.0))
    radial = np.exp(-0.5 * (np.linalg.norm(xy - center, axis=1) / radial_scale) ** 2)
    latent += float(rng.uniform(0.5, 1.2)) * radial
    ranking = np.argsort(latent)[::-1]

    closed_idx = choose_connected_closures(nodes, edges, ranking, blocked_target)
    closed_set = set(closed_idx)
    passable_idx = [int(i) for i in ranking if int(i) not in closed_set][: wet_target - blocked_target]

    depth = np.zeros(n, dtype=float)
    if closed_idx:
        ranks = np.linspace(1.0, 0.0, len(closed_idx), endpoint=False)
        depth[closed_idx] = 0.30 + (spec.closed_depth_max_m - 0.30) * (0.35 + 0.65 * ranks)
        depth[closed_idx] += rng.normal(0.0, 0.008, len(closed_idx))
        depth[closed_idx] = np.maximum(depth[closed_idx], 0.3001)
    if passable_idx:
        ranks = np.linspace(1.0, 0.0, len(passable_idx), endpoint=False)
        low = 0.03 if severity == "mild" else 0.05
        depth[passable_idx] = low + (spec.passable_depth_max_m - low) * (0.15 + 0.85 * ranks)
        depth[passable_idx] += rng.normal(0.0, 0.006, len(passable_idx))
        depth[passable_idx] = np.clip(depth[passable_idx], 0.0, 0.299)

    disruption = disruption_from_depth(depth)
    out = physical.copy()
    out["depth_m"] = depth
    out["is_wet"] = (depth > 0).astype(int)
    out["is_closed"] = disruption["is_closed"].astype(int)
    out["speed_ratio"] = disruption["speed_ratio"]
    out["free_flow_time_multiplier"] = disruption["free_flow_time_multiplier"]
    out["capacity_factor"] = disruption["capacity_factor"]
    meta = {
        "target_blocked_physical_links": blocked_target,
        "target_wet_physical_links": wet_target,
        "correlation_length_km": corr,
        "storm_center_x_km": float(center[0]),
        "storm_center_y_km": float(center[1]),
        "storm_radial_scale_km": radial_scale,
        "connectivity_constrained": True,
    }
    return out, meta


def main():
    rng = np.random.default_rng(SEED)
    physical = pd.read_csv(DATA / "processed" / "physical_links.csv")
    directed = pd.read_csv(DATA / "processed" / "directed_links.csv")
    physical_records = []
    summaries = []
    split_records = []
    depth_cols = {}
    sid = 0

    for split, groups in PLAN.items():
        for severity, count in groups:
            for _ in range(count):
                sid += 1
                field, meta = generate_one(physical, severity, rng)
                field.insert(0, "severity", severity)
                field.insert(0, "split", split)
                field.insert(0, "scenario_id", sid)
                physical_records.append(field)
                depth_cols[f"scenario_{sid:03d}"] = field["depth_m"].to_numpy()
                summaries.append({
                    "scenario_id": sid,
                    "split": split,
                    "severity": severity,
                    "wet_physical_links": int(field["is_wet"].sum()),
                    "closed_physical_links": int(field["is_closed"].sum()),
                    "mean_depth_wet_m": float(field.loc[field["is_wet"] == 1, "depth_m"].mean()),
                    "max_depth_m": float(field["depth_m"].max()),
                    **meta,
                })
                split_records.append({"scenario_id": sid, "split": split, "severity": severity})

    phys_all = pd.concat(physical_records, ignore_index=True)
    arc_all = directed[["arc_id", "from_node", "to_node", "physical_link_id"]].merge(
        phys_all,
        on="physical_link_id",
        how="left",
        validate="many_to_many",
    )
    keep = [
        "arc_id", "from_node", "to_node", "physical_link_id", "scenario_id", "split", "severity",
        "physical_from", "physical_to", "depth_m", "is_wet", "is_closed", "speed_ratio",
        "free_flow_time_multiplier", "capacity_factor",
    ]
    arc_all = arc_all[keep].sort_values(["scenario_id", "arc_id"])
    phys_all = phys_all.sort_values(["scenario_id", "physical_link_id"])

    phys_all.to_csv(OUT / "flood_scenarios_physical_links.csv", index=False)
    arc_all.to_csv(OUT / "flood_scenarios_directed_arcs.csv", index=False)
    pd.DataFrame(summaries).to_csv(OUT / "scenario_summary.csv", index=False)
    pd.DataFrame(split_records).to_csv(OUT / "scenario_split.csv", index=False)
    depth_matrix = physical[["physical_link_id"]].copy()
    for name, values in depth_cols.items():
        depth_matrix[name] = values
    depth_matrix.to_csv(OUT / "flood_depth_matrix_m.csv", index=False)
    (OUT / "metadata.json").write_text(json.dumps({
        "seed": SEED,
        "scenario_count": sid,
        "connectivity_constraint": "Every closed-link set preserves connectivity for all positive OD pairs",
        "closure_depth_m": 0.30,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {sid} connectivity-preserving scenarios in {OUT}")


if __name__ == "__main__":
    main()
