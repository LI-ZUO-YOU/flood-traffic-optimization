from __future__ import annotations

import argparse
import hashlib
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root / "dataset_manifest.json").read_text(encoding="utf-8"))
    config = json.loads((root / "feature_config.json").read_text(encoding="utf-8"))
    bootstrap = json.loads((root / "bootstrap_scenarios.json").read_text(encoding="utf-8"))
    with (root / "preprocessor.pkl").open("rb") as handle:
        preprocessor = pickle.load(handle)

    checks = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})
        if not passed:
            raise AssertionError(f"{name}: {detail}")

    check("manifest_qc", manifest["all_qc_passed"] is True, f"qc={manifest['qc_check_count']}")
    check("feature_dimension", config["input_dimension"] == 114, str(config["input_dimension"]))
    check("bootstrap_members", bootstrap["n_members"] == 10 and len(bootstrap["members"]) == 10, "10 members")
    check("bootstrap_oob", all(member["oob_scenario_count"] > 0 for member in bootstrap["members"]), "all non-empty")

    split_map = {
        "train": "recovery_states_train.csv",
        "calibration": "recovery_states_calibration.csv",
        "test_id": "recovery_states_test_id.csv",
        "test_severe": "recovery_states_test_severe.csv",
    }
    frozen = root / manifest["frozen_dataset_relative_path"]
    depth_cols = preprocessor["depth_columns"]
    closed_cols = preprocessor["closed_columns"]
    restored_cols = preprocessor["restored_columns"]
    scaler = preprocessor["depth_scaler"]
    baseline = float(preprocessor["baseline_tstt"])

    scenario_sets = {}
    for split, filename in split_map.items():
        raw = pd.read_csv(frozen / filename)
        data = np.load(root / "processed" / f"preprocessed_{split}.npz")
        X_expected = np.concatenate(
            [
                (raw[depth_cols].to_numpy(dtype=np.float64) - scaler["mean_"]) / scaler["scale_"],
                raw[closed_cols].to_numpy(dtype=np.float64),
                raw[restored_cols].to_numpy(dtype=np.float64),
            ],
            axis=1,
        ).astype(np.float32)
        y_expected = np.log(raw["tstt"].to_numpy(dtype=np.float64) / baseline)
        check(f"{split}_shape", data["X"].shape == (len(raw), 114), str(data["X"].shape))
        check(f"{split}_X_reproduction", np.array_equal(data["X"], X_expected), "exact float32 match")
        check(f"{split}_y_reproduction", np.max(np.abs(data["y_log_tstt_ratio"] - y_expected)) < 1e-12, "max diff < 1e-12")
        check(f"{split}_state_order", np.array_equal(data["state_id"].astype(str), raw["state_id"].astype(str)), "row order preserved")
        scenario_sets[split] = set(raw["scenario_id"].astype(int))

    names = list(scenario_sets)
    check(
        "scenario_disjoint",
        all(not (scenario_sets[names[i]] & scenario_sets[names[j]]) for i in range(len(names)) for j in range(i + 1, len(names))),
        "all six pairwise intersections empty",
    )
    train_data = np.load(root / "processed" / "preprocessed_train.npz")
    check("training_weight_sum", abs(float(train_data["sample_weight"].sum()) - 1500.0) < 1e-10, "sum=1500")
    weight_frame = pd.DataFrame({"scenario_id": train_data["scenario_id"], "weight": train_data["sample_weight"]})
    totals = weight_frame.groupby("scenario_id")["weight"].sum().to_numpy()
    check("scenario_equal_weight", np.max(np.abs(totals - 25.0)) < 1e-10, "each scenario total=25")

    for relative, info in manifest["frozen_file_hashes"].items():
        check(f"frozen_hash::{relative}", sha256_file(frozen / relative) == info["sha256"], "SHA-256 match")
    for relative, info in manifest["generated_artifact_hashes"].items():
        check(f"artifact_hash::{relative}", sha256_file(root / relative) == info["sha256"], "SHA-256 match")

    report = {
        "all_passed": all(item["passed"] for item in checks),
        "check_count": len(checks),
        "checks": checks,
    }
    (root / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"all_passed": report["all_passed"], "check_count": report["check_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
