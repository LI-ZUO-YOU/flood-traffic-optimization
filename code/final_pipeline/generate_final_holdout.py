from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def vector_hash(values, dtype=np.float64) -> str:
    array = np.asarray(values, dtype=dtype).reshape(-1)
    return hashlib.sha256(array.tobytes()).hexdigest()


def scenario_hash(depth, closed) -> str:
    payload = np.concatenate([
        np.round(np.asarray(depth, dtype=np.float64), 9),
        np.asarray(closed, dtype=np.uint8).astype(np.float64),
    ])
    return hashlib.sha256(payload.tobytes()).hexdigest()


def prior_hashes(paths: list[Path]) -> tuple[set[str], set[str], set[str], list[dict]]:
    depth_hashes: set[str] = set()
    closed_hashes: set[str] = set()
    scenario_hashes: set[str] = set()
    sources = []
    for path in paths:
        frame = pd.read_csv(path)
        required = {"scenario_id", "physical_link_id", "depth_m", "is_closed"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{path} is missing {sorted(missing)}")
        count = 0
        for sid, group in frame.groupby("scenario_id", sort=False):
            group = group.sort_values("physical_link_id")
            if len(group) != 38 or set(group["physical_link_id"].astype(int)) != set(range(1, 39)):
                raise ValueError(f"Prior scenario {sid} in {path} is not a complete 38-road table")
            depth = group["depth_m"].to_numpy(float)
            closed = group["is_closed"].to_numpy(np.uint8)
            depth_hashes.add(vector_hash(np.round(depth, 9)))
            closed_hashes.add(vector_hash(closed, np.uint8))
            scenario_hashes.add(scenario_hash(depth, closed))
            count += 1
        sources.append({"path": str(path), "sha256": sha256_file(path), "scenario_count": count})
    return depth_hashes, closed_hashes, scenario_hashes, sources


def load_generation_functions(model_root: Path):
    if str(model_root) not in sys.path:
        sys.path.insert(0, str(model_root))
    from models.flood_mapping import disruption_from_depth
    from models.spatial_flood_field import SPECS, gaussian_covariance

    def connected_after_removal(nodes: np.ndarray, edges: list[tuple[int, int]], removed: set[int]) -> bool:
        adjacency = {int(node): [] for node in nodes}
        for index, (u, v) in enumerate(edges):
            if index in removed:
                continue
            adjacency[u].append(v)
            adjacency[v].append(u)
        seen = {int(nodes[0])}
        stack = list(seen)
        while stack:
            u = stack.pop()
            for v in adjacency[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        return len(seen) == len(nodes)

    def choose_connected_closures(nodes, edges, ranking, target):
        removed: set[int] = set()
        for index in ranking:
            trial = removed | {int(index)}
            if connected_after_removal(nodes, edges, trial):
                removed = trial
                if len(removed) == target:
                    break
        if len(removed) != target:
            raise RuntimeError(f"Could select only {len(removed)} connected closures; target={target}")
        return [int(index) for index in ranking if int(index) in removed]

    def generate_one(physical: pd.DataFrame, rng: np.random.Generator):
        severity = "severe"
        spec = SPECS[severity]
        xy = physical[["mid_x_km", "mid_y_km"]].to_numpy(float)
        nodes = np.unique(physical[["physical_from", "physical_to"]].to_numpy().ravel()).astype(int)
        edges = [(int(u), int(v)) for u, v in physical[["physical_from", "physical_to"]].itertuples(index=False, name=None)]
        n = len(physical)
        blocked_target = int(rng.integers(spec.blocked_min, spec.blocked_max + 1))
        wet_target = max(int(rng.integers(spec.wet_min, min(spec.wet_max, n) + 1)), blocked_target)
        correlation_length = float(rng.uniform(spec.corr_min_km, spec.corr_max_km))
        covariance = gaussian_covariance(xy, correlation_length)
        latent = np.linalg.cholesky(covariance) @ rng.standard_normal(n)
        center_index = int(rng.integers(0, n))
        center = xy[center_index]
        radial_scale = float(rng.uniform(2.0, 5.0))
        radial = np.exp(-0.5 * (np.linalg.norm(xy - center, axis=1) / radial_scale) ** 2)
        latent += float(rng.uniform(0.5, 1.2)) * radial
        ranking = np.argsort(latent)[::-1]
        closed_indices = choose_connected_closures(nodes, edges, ranking, blocked_target)
        closed_set = set(closed_indices)
        passable_indices = [int(index) for index in ranking if int(index) not in closed_set][: wet_target - blocked_target]
        depth = np.zeros(n, dtype=float)
        if closed_indices:
            ranks = np.linspace(1.0, 0.0, len(closed_indices), endpoint=False)
            depth[closed_indices] = 0.30 + (spec.closed_depth_max_m - 0.30) * (0.35 + 0.65 * ranks)
            depth[closed_indices] += rng.normal(0.0, 0.008, len(closed_indices))
            depth[closed_indices] = np.maximum(depth[closed_indices], 0.3001)
        if passable_indices:
            ranks = np.linspace(1.0, 0.0, len(passable_indices), endpoint=False)
            depth[passable_indices] = 0.05 + (spec.passable_depth_max_m - 0.05) * (0.15 + 0.85 * ranks)
            depth[passable_indices] += rng.normal(0.0, 0.006, len(passable_indices))
            depth[passable_indices] = np.clip(depth[passable_indices], 0.0, 0.299)
        disruption = disruption_from_depth(depth)
        output = physical.copy()
        output["depth_m"] = depth
        output["is_wet"] = (depth > 0).astype(int)
        output["is_closed"] = disruption["is_closed"].astype(int)
        output["speed_ratio"] = disruption["speed_ratio"]
        output["free_flow_time_multiplier"] = disruption["free_flow_time_multiplier"]
        output["capacity_factor"] = disruption["capacity_factor"]
        metadata = {
            "target_blocked_physical_links": blocked_target,
            "target_wet_physical_links": wet_target,
            "correlation_length_km": correlation_length,
            "storm_center_x_km": float(center[0]),
            "storm_center_y_km": float(center[1]),
            "storm_radial_scale_km": radial_scale,
            "connectivity_constrained": True,
        }
        return output, metadata

    return generate_one


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the final untouched severe-flood holdout after Day 7 v1.1 is frozen.")
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-hash-file", required=True)
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--prior-scenario-file", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    protocol_path = Path(args.protocol)
    protocol_hash_path = Path(args.protocol_hash_file)
    model_root = Path(args.model_root)
    output = Path(args.output_dir)
    if output.exists():
        raise FileExistsError(output)
    recorded_hash = protocol_hash_path.read_text(encoding="utf-8").strip().split()[0]
    actual_hash = sha256_file(protocol_path)
    if recorded_hash != actual_hash:
        raise RuntimeError("Protocol hash mismatch; final scenarios were not generated")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("status") != "FROZEN_BEFORE_FINAL_SCENARIO_GENERATION":
        raise RuntimeError("Protocol is not frozen before final scenario generation")
    specification = protocol["final_scenario_generation"]
    count = int(specification["formal_final_scenario_count"])
    first_id, last_id = map(int, specification["scenario_id_range"])
    if last_id - first_id + 1 != count or specification["severity"] != "severe":
        raise ValueError("Protocol final-scenario range/count/severity is inconsistent")
    seed = int(specification["scenario_seed"])

    prior_paths = [Path(value) for value in args.prior_scenario_file]
    prior_depth, prior_closed, prior_scenario, prior_sources = prior_hashes(prior_paths)
    accepted_depth = set(prior_depth)
    accepted_closed = set(prior_closed)
    accepted_scenario = set(prior_scenario)
    physical_source = model_root / "data_src/SiouxFalls_flood_benchmark/processed/physical_links.csv"
    physical = pd.read_csv(physical_source).sort_values("physical_link_id").reset_index(drop=True)
    if len(physical) != 38 or set(physical["physical_link_id"].astype(int)) != set(range(1, 39)):
        raise ValueError("The Sioux Falls physical-road source must contain IDs 1..38 exactly once")
    generate_one = load_generation_functions(model_root)
    rng = np.random.default_rng(seed)
    accepted_frames = []
    summaries = []
    events = []
    draw = 0
    next_id = first_id
    while next_id <= last_id:
        draw += 1
        field, metadata = generate_one(physical, rng)
        field = field.sort_values("physical_link_id").reset_index(drop=True)
        depth = field["depth_m"].to_numpy(float)
        closed = field["is_closed"].to_numpy(np.uint8)
        depth_digest = vector_hash(np.round(depth, 9))
        closed_digest = vector_hash(closed, np.uint8)
        scenario_digest = scenario_hash(depth, closed)
        reasons = []
        if int(closed.sum()) < 10:
            reasons.append("fewer_than_10_initially_closed_roads")
        if depth_digest in accepted_depth:
            reasons.append("duplicate_depth_vector")
        if closed_digest in accepted_closed:
            reasons.append("duplicate_closed_mask")
        if scenario_digest in accepted_scenario:
            reasons.append("duplicate_scenario_hash")
        if reasons:
            events.append({"draw_index": draw, "decision": "reject", "scenario_id": None, "reasons": "|".join(reasons),
                           "closed_physical_links": int(closed.sum()), "depth_sha256": depth_digest,
                           "closed_mask_sha256": closed_digest, "scenario_sha256": scenario_digest})
            continue
        scenario_id = next_id
        next_id += 1
        accepted_depth.add(depth_digest)
        accepted_closed.add(closed_digest)
        accepted_scenario.add(scenario_digest)
        field.insert(0, "severity", "severe")
        field.insert(0, "split", "final_untouched")
        field.insert(0, "scenario_id", scenario_id)
        accepted_frames.append(field)
        summaries.append({"scenario_id": scenario_id, "split": "final_untouched", "severity": "severe",
                          "wet_physical_links": int(field["is_wet"].sum()),
                          "closed_physical_links": int(field["is_closed"].sum()),
                          "mean_depth_wet_m": float(field.loc[field["is_wet"] == 1, "depth_m"].mean()),
                          "max_depth_m": float(field["depth_m"].max()), **metadata,
                          "depth_sha256": depth_digest, "closed_mask_sha256": closed_digest,
                          "scenario_sha256": scenario_digest})
        events.append({"draw_index": draw, "decision": "accept", "scenario_id": scenario_id, "reasons": "",
                       "closed_physical_links": int(closed.sum()), "depth_sha256": depth_digest,
                       "closed_mask_sha256": closed_digest, "scenario_sha256": scenario_digest})

    output.mkdir(parents=True)
    physical_output = output / "final_scenarios_physical_links.csv"
    summary_output = output / "final_scenario_summary.csv"
    rejection_output = output / "final_scenario_rejection_log.csv"
    pd.concat(accepted_frames, ignore_index=True).to_csv(physical_output, index=False, encoding="utf-8-sig")
    pd.DataFrame(summaries).to_csv(summary_output, index=False, encoding="utf-8-sig")
    pd.DataFrame(events).to_csv(rejection_output, index=False, encoding="utf-8-sig")
    hashes = {str(row["scenario_id"]): {key: row[key] for key in ("depth_sha256", "closed_mask_sha256", "scenario_sha256")}
              for row in summaries}
    write_json(output / "final_scenario_hashes.json", hashes)
    freeze = {
        "schema_version": "week4-final-scenario-freeze-v1.0",
        "protocol_sha256": actual_hash,
        "seed": seed,
        "scenario_ids": list(range(first_id, last_id + 1)),
        "accepted_count": count,
        "draw_count": draw,
        "rejected_count": draw - count,
        "all_closed_counts_at_least_10": all(int(row["closed_physical_links"]) >= 10 for row in summaries),
        "zero_overlap_with_prior_scenarios": True,
        "prior_sources": prior_sources,
        "source_physical_links": {"path": str(physical_source), "sha256": sha256_file(physical_source)},
        "outputs": {path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size}
                    for path in (physical_output, summary_output, rejection_output, output / "final_scenario_hashes.json")},
    }
    write_json(output / "scenario_generation_freeze_record.json", freeze)
    print(json.dumps({"status": "pass", "output": str(output), "accepted": count, "rejected": draw - count}, indent=2))


if __name__ == "__main__":
    main()
