from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

PACKAGE_ROOT = Path(__file__).resolve().parent
if not (PACKAGE_ROOT / "models").exists() and (PACKAGE_ROOT.parent / "models").exists():
    PACKAGE_ROOT = PACKAGE_ROOT.parent
sys.path.insert(0, str(PACKAGE_ROOT))

from models import build_flooded_solver


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scenarios", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    args = parser.parse_args()
    processed = args.root / "SiouxFalls_flood_benchmark" / "processed"
    connected = args.root / "SiouxFalls_UE_flood_models" / "data_connected"
    links = pd.read_csv(processed / "directed_links.csv")
    od = pd.read_csv(processed / "od_long.csv")
    scenarios = pd.read_csv(connected / "flood_scenarios_directed_arcs.csv")
    rows = []
    for scenario_id in args.scenarios:
        scenario = scenarios.loc[scenarios.scenario_id == scenario_id].copy()
        solver = build_flooded_solver(links, od, scenario)
        start = time.perf_counter()
        production = solver.solve(method="fw", relative_gap=5e-4, max_iter=1000)
        production_seconds = time.perf_counter() - start
        start = time.perf_counter()
        reference = solver.solve(method="fw", relative_gap=1e-4, max_iter=5000)
        reference_seconds = time.perf_counter() - start
        rows.append({
            "scenario_id": scenario_id,
            "production_tstt": production.tstt,
            "production_gap": production.relative_gap,
            "production_iterations": production.iterations,
            "production_seconds": production_seconds,
            "reference_tstt": reference.tstt,
            "reference_gap": reference.relative_gap,
            "reference_iterations": reference.iterations,
            "reference_converged": reference.converged,
            "reference_seconds": reference_seconds,
            "absolute_relative_tstt_difference": abs(production.tstt - reference.tstt) / reference.tstt,
        })
    output = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(output.to_string(index=False))


if __name__ == "__main__":
    main()
