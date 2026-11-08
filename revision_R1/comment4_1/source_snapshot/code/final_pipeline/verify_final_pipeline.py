from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a frozen Day7 v1.1 warm- or cold-cache pipeline result.")
    parser.add_argument("--pipeline-root", required=True)
    parser.add_argument("--expected-mode", choices=["warm", "cold"], required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path(args.pipeline_root).resolve()
    pipeline_path = root / "pipeline_output_freeze.json"
    pipeline = load(pipeline_path)
    scenario_ids = list(map(int, pipeline["scenario_ids"]))
    checks: dict[str, bool] = {
        "pipeline_status_pass": pipeline.get("status") == "pass",
        "explicit_smoke_test": pipeline.get("smoke_test") is True,
        "one_old_scenario_only": len(scenario_ids) == 1 and scenario_ids[0] == 146,
        "warm_cold_flag_matches": bool(pipeline.get("warm_cache_smoke_only")) == (args.expected_mode == "warm"),
        "information_firewall_declared": pipeline.get("information_firewall_respected") is True,
    }
    method_freezes = []
    control_freezes = []
    for sid in scenario_ids:
        full_dir = root / f"06_full_method/scenario_{sid}"
        control_dir = root / f"07_live_controls/scenario_{sid}"
        full_freeze_path = full_dir / "full_method_output_freeze.json"
        control_freeze_path = control_dir / "controls_output_freeze.json"
        usage = load(full_dir / "budget_usage_pre_reference.json")
        controls = load(control_freeze_path)
        checks[f"s{sid}_full_budget_512"] = int(usage["unique_ue_calls"]) == 512
        checks[f"s{sid}_full_all_converged"] = usage.get("all_ue_converged") is True
        checks[f"s{sid}_physical_cache_mode"] = (
            int(usage.get("physical_cache_hits", 0)) == 512 if args.expected_mode == "warm"
            else int(usage.get("physical_cache_hits", -1)) == 0
        )
        checks[f"s{sid}_five_controls_frozen"] = controls.get("all_five_controls_frozen") is True
        checks[f"s{sid}_five_control_count"] = len(controls.get("methods", {})) == 5
        method_freezes.append(full_freeze_path)
        control_freezes.append(control_freeze_path)

    exact_dir = root / "08_exact_reference_after_method_freeze"
    exact_freeze_path = exact_dir / "exact_reference_freeze.json"
    exact_freeze = load(exact_freeze_path)
    exact_verify = load(exact_dir / "verification_report.json")
    costs = pd.read_csv(exact_dir / "subset_ue_costs.csv")
    checks["exact_1024_per_scenario"] = len(costs) == 1024 * len(scenario_ids)
    checks["exact_all_converged"] = exact_verify.get("all_converged") is True
    checks["exact_freeze_after_methods"] = exact_freeze_path.stat().st_mtime >= max(
        path.stat().st_mtime for path in method_freezes + control_freezes
    )
    checks["pipeline_after_exact"] = pipeline_path.stat().st_mtime >= exact_freeze_path.stat().st_mtime
    checks["exact_freeze_hash_matches_pipeline"] = sha256(exact_freeze_path) == pipeline["exact_reference_freeze_sha256"]

    status = "pass" if all(checks.values()) else "fail"
    report = {
        "schema_version": "day7-v1.1-pipeline-independent-verification-v1.0",
        "status": status,
        "mode": args.expected_mode,
        "pipeline_root": str(root),
        "pipeline_output_freeze_sha256": sha256(pipeline_path),
        "checks": checks,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if status != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
