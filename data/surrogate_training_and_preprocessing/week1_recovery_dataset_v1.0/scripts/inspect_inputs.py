from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import pandas as pd

PACKAGE_ROOT = Path(__file__).resolve().parent
if not (PACKAGE_ROOT / "models").exists() and (PACKAGE_ROOT.parent / "models").exists():
    PACKAGE_ROOT = PACKAGE_ROOT.parent
sys.path.insert(0, str(PACKAGE_ROOT))

from models import build_flooded_solver


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def edge_betweenness(physical: pd.DataFrame) -> dict[int, float]:
    adjacency: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for row in physical.itertuples(index=False):
        edge_id = int(row.physical_link_id)
        u, v = int(row.physical_from), int(row.physical_to)
        adjacency[u].append((v, edge_id))
        adjacency[v].append((u, edge_id))

    score = defaultdict(float)
    for source in sorted(adjacency):
        stack: list[int] = []
        predecessors: dict[int, list[tuple[int, int]]] = {node: [] for node in adjacency}
        paths = {node: 0.0 for node in adjacency}
        distance = {node: -1 for node in adjacency}
        paths[source] = 1.0
        distance[source] = 0
        queue = deque([source])
        while queue:
            v = queue.popleft()
            stack.append(v)
            for w, edge_id in adjacency[v]:
                if distance[w] < 0:
                    queue.append(w)
                    distance[w] = distance[v] + 1
                if distance[w] == distance[v] + 1:
                    paths[w] += paths[v]
                    predecessors[w].append((v, edge_id))
        dependency = {node: 0.0 for node in adjacency}
        while stack:
            w = stack.pop()
            if paths[w] == 0:
                continue
            for v, edge_id in predecessors[w]:
                contribution = (paths[v] / paths[w]) * (1.0 + dependency[w])
                score[edge_id] += contribution
                dependency[v] += contribution
    return {edge_id: value / 2.0 for edge_id, value in score.items()}


def validate(root: Path, benchmark_solves: int, max_iter: int, target_gap: float) -> dict:
    model_root = root / "SiouxFalls_UE_flood_models"
    benchmark_root = root / "SiouxFalls_flood_benchmark"
    connected = model_root / "data_connected"
    processed = benchmark_root / "processed"

    nodes = pd.read_csv(processed / "nodes.csv")
    links = pd.read_csv(processed / "directed_links.csv")
    physical = pd.read_csv(processed / "physical_links.csv")
    od_long = pd.read_csv(processed / "od_long.csv")
    od_matrix = pd.read_csv(processed / "od_matrix.csv")
    benchmark_flows = pd.read_csv(processed / "benchmark_ue_link_flows.csv")
    summary = pd.read_csv(connected / "scenario_summary.csv")
    split = pd.read_csv(connected / "scenario_split.csv")
    scenario_physical = pd.read_csv(connected / "flood_scenarios_physical_links.csv")
    scenario_arcs = pd.read_csv(connected / "flood_scenarios_directed_arcs.csv")

    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str, severity: str = "error") -> None:
        checks.append({"check": name, "passed": bool(passed), "severity": severity, "detail": detail})

    check("node_count", len(nodes) == 24 and nodes.iloc[:, 0].nunique() == 24, f"rows={len(nodes)}")
    check("directed_link_count", len(links) == 76 and links.arc_id.nunique() == 76, f"rows={len(links)}")
    check("physical_link_count", len(physical) == 38 and physical.physical_link_id.nunique() == 38, f"rows={len(physical)}")
    check("directed_to_physical_mapping", links.physical_link_id.notna().all() and set(links.physical_link_id) == set(physical.physical_link_id), "all directed arcs map to 38 physical links")
    positive_od = od_long.loc[od_long.demand > 0]
    check("od_nonzero_pairs", len(positive_od) == 528, f"positive_pairs={len(positive_od)}")
    check("od_total", np.isclose(positive_od.demand.sum(), 360600.0), f"total={positive_od.demand.sum():.6f}")
    check("od_nonnegative", (od_long.demand >= 0).all(), f"min={od_long.demand.min():.6f}")
    matrix_values = od_matrix.drop(columns=["origin"]).select_dtypes(include=[np.number]).to_numpy()
    check("od_matrix_total", np.isclose(matrix_values.sum(), 360600.0), f"numeric_total={matrix_values.sum():.6f}")
    check("scenario_count", summary.scenario_id.nunique() == 120 and len(summary) == 120, f"rows={len(summary)}")
    check("scenario_split_one_to_one", split.scenario_id.nunique() == len(split) == 120, f"rows={len(split)}")
    split_counts = split.groupby(["split", "severity"]).size().to_dict()
    expected = {("train", "mild"): 30, ("train", "moderate"): 30, ("calibration", "mild"): 10, ("calibration", "moderate"): 10, ("test_id", "mild"): 10, ("test_id", "moderate"): 10, ("test_severe", "severe"): 20}
    check("scenario_split_counts", split_counts == expected, json.dumps({str(k): int(v) for k, v in split_counts.items()}, ensure_ascii=False))
    check("scenario_physical_shape", len(scenario_physical) == 120 * 38 and not scenario_physical.duplicated(["scenario_id", "physical_link_id"]).any(), f"rows={len(scenario_physical)}")
    check("scenario_arc_shape", len(scenario_arcs) == 120 * 76 and not scenario_arcs.duplicated(["scenario_id", "arc_id"]).any(), f"rows={len(scenario_arcs)}")
    check("depth_nonnegative", (scenario_physical.depth_m >= 0).all(), f"range=[{scenario_physical.depth_m.min():.6f},{scenario_physical.depth_m.max():.6f}]")
    expected_closed = (scenario_physical.depth_m >= 0.30).astype(int)
    check("closure_threshold_consistency", np.array_equal(expected_closed.to_numpy(), scenario_physical.is_closed.astype(int).to_numpy()), "is_closed equals depth>=0.30 m")
    passable = scenario_physical.is_closed.astype(int) == 0
    finite_passable = np.isfinite(scenario_physical.loc[passable, "free_flow_time_multiplier"]).all()
    check("passable_multiplier_finite", finite_passable, f"passable_rows={int(passable.sum())}")
    check("closed_multiplier_infinite", np.isinf(scenario_physical.loc[~passable, "free_flow_time_multiplier"]).all(), f"closed_rows={int((~passable).sum())}")
    check("connected_flag", summary.connectivity_constrained.astype(bool).all(), "all 120 scenarios marked connectivity constrained")

    arc_pair_depth = scenario_arcs.groupby(["scenario_id", "physical_link_id"]).agg(depth_n=("depth_m", "nunique"), closed_n=("is_closed", "nunique"))
    check("bidirectional_flood_consistency", int(arc_pair_depth.depth_n.max()) == 1 and int(arc_pair_depth.closed_n.max()) == 1, "both directions share depth and closure state")

    flow_map = links[["from_node", "to_node", "physical_link_id"]].merge(
        benchmark_flows[["from_node", "to_node", "benchmark_volume"]],
        on=["from_node", "to_node"], how="left", validate="one_to_one"
    )
    physical_flow = flow_map.groupby("physical_link_id").benchmark_volume.sum()
    betweenness = pd.Series(edge_betweenness(physical), name="betweenness")
    critical = pd.DataFrame({"physical_flow": physical_flow, "betweenness": betweenness}).fillna(0.0)
    critical["high_flow"] = critical.physical_flow >= critical.physical_flow.quantile(0.75)
    critical["high_betweenness"] = critical.betweenness >= critical.betweenness.quantile(0.75)
    critical["critical"] = critical.high_flow | critical.high_betweenness
    critical_ids = set(critical.index[critical.critical].astype(int))
    severe_closed = scenario_physical.loc[(scenario_physical.split == "test_severe") & (scenario_physical.is_closed == 1)]
    severe_critical = severe_closed.assign(is_critical=severe_closed.physical_link_id.isin(critical_ids)).groupby("scenario_id").agg(
        closed_links=("physical_link_id", "nunique"), critical_closed=("is_critical", "sum")
    )
    critical_joint_count = int((severe_critical.critical_closed >= 2).sum())
    check(
        "severe_joint_critical_failures",
        critical_joint_count >= 10,
        f"{critical_joint_count}/20 severe scenarios close at least two top-quartile flow/betweenness links",
        severity="warning",
    )

    solve_rows = []
    benchmark_ids = summary.scenario_id.iloc[:benchmark_solves].astype(int).tolist()
    for scenario_id in benchmark_ids:
        scenario = scenario_arcs.loc[scenario_arcs.scenario_id == scenario_id].copy()
        solver = build_flooded_solver(links, od_long, scenario)
        start = time.perf_counter()
        result = solver.solve(method="fw", relative_gap=target_gap, max_iter=max_iter)
        solve_rows.append({
            "scenario_id": scenario_id,
            "converged": result.converged,
            "relative_gap": result.relative_gap,
            "iterations": result.iterations,
            "tstt": result.tstt,
            "elapsed_seconds": time.perf_counter() - start,
        })
    solve_df = pd.DataFrame(solve_rows)
    check("benchmark_solves_converged", bool(solve_df.converged.all()), f"{int(solve_df.converged.sum())}/{len(solve_df)} converged at gap<={target_gap:g}")

    checks_df = pd.DataFrame(checks)
    critical_out = critical.reset_index().rename(columns={"index": "physical_link_id"})
    return {
        "checks": checks_df,
        "critical_links": critical_out,
        "severe_critical": severe_critical.reset_index(),
        "benchmark_solves": solve_df,
        "hashes": pd.DataFrame([
            {"file": str(path.relative_to(root)), "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in [
                processed / "nodes.csv", processed / "directed_links.csv", processed / "physical_links.csv",
                processed / "od_long.csv", processed / "od_matrix.csv", connected / "scenario_summary.csv",
                connected / "scenario_split.csv", connected / "flood_scenarios_physical_links.csv",
                connected / "flood_scenarios_directed_arcs.csv",
            ]
        ]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--benchmark-solves", type=int, default=10)
    parser.add_argument("--max-iter", type=int, default=2000)
    parser.add_argument("--target-gap", type=float, default=1e-4)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    results = validate(args.root, args.benchmark_solves, args.max_iter, args.target_gap)
    for name, frame in results.items():
        frame.to_csv(args.out / f"{name}.csv", index=False, encoding="utf-8-sig")
    print(results["checks"].to_string(index=False))
    print("\nBenchmark solves:\n", results["benchmark_solves"].to_string(index=False))


if __name__ == "__main__":
    main()
