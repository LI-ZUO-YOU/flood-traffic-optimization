from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def normalized_desc_score(values: pd.Series) -> pd.Series:
    count = len(values)
    if count == 1:
        return pd.Series([1.0], index=values.index)
    rank = values.rank(method="min", ascending=False)
    return (count - rank) / (count - 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze the ten recoverable roads before proxy or UE outcomes are available.")
    parser.add_argument("--scenario-physical", required=True)
    parser.add_argument("--scenario-freeze", required=True)
    parser.add_argument("--surrogate-preprocessor", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scenario-count", required=True, type=int)
    args = parser.parse_args()

    physical_path = Path(args.scenario_physical)
    scenario_freeze_path = Path(args.scenario_freeze)
    preprocessor_path = Path(args.surrogate_preprocessor)
    protocol_path = Path(args.protocol)
    output = Path(args.output_dir)
    if output.exists():
        raise FileExistsError(output)
    scenario_freeze = json.loads(scenario_freeze_path.read_text(encoding="utf-8"))
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    preprocessor = json.loads(preprocessor_path.read_text(encoding="utf-8"))
    flow = np.asarray(preprocessor["baseline_flow"], dtype=float)
    betweenness = np.asarray(preprocessor["betweenness"], dtype=float)
    if len(flow) != 38 or len(betweenness) != 38 or not np.isfinite(flow).all() or not np.isfinite(betweenness).all():
        raise ValueError("Frozen preprocessor must contain 38 finite flow and betweenness values")
    frame = pd.read_csv(physical_path)
    scenario_ids = sorted(map(int, frame["scenario_id"].astype(int).unique()))
    if len(scenario_ids) != args.scenario_count:
        raise ValueError(f"Expected {args.scenario_count} scenarios; found {len(scenario_ids)}")
    expected_ids = list(map(int, scenario_freeze["scenario_ids"]))
    if scenario_ids != expected_ids:
        raise ValueError("Scenario IDs differ from their frozen generation record")
    records = []
    metadata_rows = []
    for sid in scenario_ids:
        scenario = frame[frame["scenario_id"].astype(int) == sid].sort_values("physical_link_id").copy()
        if len(scenario) != 38 or set(scenario["physical_link_id"].astype(int)) != set(range(1, 39)):
            raise ValueError(f"Scenario {sid}: physical road IDs must be exactly 1..38")
        if not np.isin(scenario["is_closed"], [0, 1]).all():
            raise ValueError(f"Scenario {sid}: is_closed must be binary")
        scenario["physical_flow"] = flow
        scenario["betweenness"] = betweenness
        scenario["eligible_initially_closed"] = scenario["is_closed"].astype(int) == 1
        closed = scenario[scenario["eligible_initially_closed"]].copy()
        if len(closed) < 10:
            raise ValueError(f"Scenario {sid}: fewer than ten initially closed roads")
        closed["flow_score"] = normalized_desc_score(closed["physical_flow"])
        closed["betweenness_score"] = normalized_desc_score(closed["betweenness"])
        closed["combined_score"] = 0.5 * closed["flow_score"] + 0.5 * closed["betweenness_score"]
        closed = closed.sort_values(
            ["combined_score", "physical_flow", "betweenness", "physical_link_id"],
            ascending=[False, False, False, True],
            kind="mergesort",
        )
        selected = closed.head(10)["physical_link_id"].astype(int).tolist()
        scenario = scenario.merge(
            closed[["physical_link_id", "flow_score", "betweenness_score", "combined_score"]],
            on="physical_link_id", how="left", validate="one_to_one",
        )
        scenario["selected_recoverable"] = scenario["physical_link_id"].astype(int).isin(selected)
        scenario["selection_rank"] = scenario["physical_link_id"].map(
            {road: rank for rank, road in enumerate(selected, start=1)}
        )
        scenario.insert(0, "scenario_id_audit", sid)
        records.append(scenario.rename(columns={"scenario_id_audit": "audit_scenario_id"}))
        metadata_rows.append({
            "scenario_id": sid,
            "severity": str(scenario["severity"].iloc[0]) if "severity" in scenario else "severe",
            "initially_closed_roads": list(map(int, scenario.loc[scenario["is_closed"].astype(int) == 1, "physical_link_id"])),
            "selected_recoverable_roads": list(map(int, selected)),
            "unselected_closed_roads_remain_closed": True,
        })
    audit = pd.concat(records, ignore_index=True)
    output.mkdir(parents=True)
    audit_path = output / "candidate_road_selection_audit.csv"
    metadata_path = output / "final_scenarios.json"
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")
    metadata = {
        "schema_version": "final-recoverable-road-selection-v1.0",
        "selected_scenario_ids": scenario_ids,
        "scenarios": metadata_rows,
        "selection_rule": protocol["candidate_road_selection"],
    }
    write_json(metadata_path, metadata)
    freeze = {
        "schema_version": "final-recoverable-road-selection-freeze-v1.0",
        "scenario_physical_sha256": sha256(physical_path),
        "scenario_generation_freeze_sha256": sha256(scenario_freeze_path),
        "surrogate_preprocessor_sha256": sha256(preprocessor_path),
        "protocol_sha256": sha256(protocol_path),
        "final_scenarios_sha256": sha256(metadata_path),
        "candidate_road_selection_audit_sha256": sha256(audit_path),
        "scenario_count": len(scenario_ids),
        "ten_selected_per_scenario": all(len(row["selected_recoverable_roads"]) == 10 for row in metadata_rows),
        "all_selected_roads_initially_closed": all(
            set(row["selected_recoverable_roads"]).issubset(row["initially_closed_roads"])
            for row in metadata_rows
        ),
        "proxy_or_ue_outcomes_read": False,
    }
    write_json(output / "candidate_road_selection_freeze.json", freeze)
    print(json.dumps({"status": "pass", "output": str(output), "scenarios": len(scenario_ids)}, indent=2))


if __name__ == "__main__":
    main()
