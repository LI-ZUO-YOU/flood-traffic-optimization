from __future__ import annotations

import hashlib
import json
import math
import os
import pickle
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from scenario_bootstrap import generate_bootstrap_plan


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE = REPOSITORY_ROOT / "data/surrogate_training_and_preprocessing/week1_recovery_dataset_v1.0"
SECOND_WEEK = REPOSITORY_ROOT / "reproduced_preprocessing"
FINAL_ROOT = SECOND_WEEK / "day1_freeze_preprocess"
STAGING_ROOT = SECOND_WEEK / ".day1_freeze_preprocess_staging_v2"
FROZEN_NAME = "week1_recovery_dataset_v1.0"
VERSION = "1.0"
SPLIT_FILES = {
    "train": "recovery_states_train.csv",
    "calibration": "recovery_states_calibration.csv",
    "test_id": "recovery_states_test_id.csv",
    "test_severe": "recovery_states_test_severe.csv",
}
EXPECTED_ROWS = {"train": 1500, "calibration": 300, "test_id": 300, "test_severe": 300}
EXPECTED_SCENARIOS = {"train": 60, "calibration": 20, "test_id": 20, "test_severe": 20}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict | list) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def feature_columns(columns: list[str]) -> tuple[list[str], list[str], list[str]]:
    depth = sorted([c for c in columns if c.startswith("d_depth_m_pl")])
    closed = sorted([c for c in columns if c.startswith("d_closed_pl")])
    restored = sorted([c for c in columns if c.startswith("r_restored_pl")])
    if not (len(depth) == len(closed) == len(restored) == 38):
        raise ValueError(f"Expected 38/38/38 features, got {len(depth)}/{len(closed)}/{len(restored)}")
    suffixes = lambda values: [value.rsplit("pl", 1)[-1] for value in values]
    if suffixes(depth) != suffixes(closed) or suffixes(depth) != suffixes(restored):
        raise ValueError("Depth/closed/restored physical-link identifiers do not align")
    return depth, closed, restored


def finite(values: np.ndarray) -> bool:
    return bool(np.isfinite(values).all())


def load_and_validate(frozen: Path, config: dict) -> tuple[dict[str, pd.DataFrame], dict]:
    frames: dict[str, pd.DataFrame] = {}
    checks: list[dict] = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})
        if not passed:
            raise ValueError(f"QC failed: {name}: {detail}")

    for split, filename in SPLIT_FILES.items():
        frame = pd.read_csv(frozen / filename)
        frames[split] = frame
        record(f"{split}_row_count", len(frame) == EXPECTED_ROWS[split], f"observed={len(frame)}")
        record(
            f"{split}_split_column",
            set(frame["split"].astype(str)) == {split},
            f"values={sorted(frame['split'].astype(str).unique())}",
        )
        record(
            f"{split}_scenario_count",
            frame["scenario_id"].nunique() == EXPECTED_SCENARIOS[split],
            f"observed={frame['scenario_id'].nunique()}",
        )

    depth_cols, closed_cols, restored_cols = feature_columns(frames["train"].columns.tolist())
    for split, frame in frames.items():
        record(f"{split}_same_feature_schema", feature_columns(frame.columns.tolist()) == (depth_cols, closed_cols, restored_cols), "114 features aligned")
        depth_values = frame[depth_cols].to_numpy(dtype=np.float64)
        closed_values = frame[closed_cols].to_numpy(dtype=np.float64)
        restored_values = frame[restored_cols].to_numpy(dtype=np.float64)
        tstt = frame["tstt"].to_numpy(dtype=np.float64)
        record(f"{split}_finite_depth", finite(depth_values), "all finite")
        record(f"{split}_nonnegative_depth", bool((depth_values >= 0).all()), f"min={depth_values.min():.12g}")
        record(f"{split}_binary_closed", set(np.unique(closed_values)).issubset({0.0, 1.0}), f"values={np.unique(closed_values).tolist()}")
        record(f"{split}_binary_restored", set(np.unique(restored_values)).issubset({0.0, 1.0}), f"values={np.unique(restored_values).tolist()}")
        record(f"{split}_restored_subset", bool((restored_values <= closed_values).all()), "r <= c")
        record(f"{split}_positive_finite_tstt", finite(tstt) and bool((tstt > 0).all()), f"range=[{tstt.min():.6g},{tstt.max():.6g}]")
        record(f"{split}_ue_converged", bool(frame["converged"].astype(bool).all()), f"converged={int(frame['converged'].astype(bool).sum())}/{len(frame)}")
        record(
            f"{split}_gap_within_target",
            float(frame["relative_gap"].max()) <= float(config["ue_target_relative_gap"]) + 1e-12,
            f"max={float(frame['relative_gap'].max()):.12g}",
        )

    scenario_sets = {split: set(frame["scenario_id"].astype(int)) for split, frame in frames.items()}
    intersections: dict[str, list[int]] = {}
    split_names = list(SPLIT_FILES)
    for i, left in enumerate(split_names):
        for right in split_names[i + 1 :]:
            key = f"{left}__{right}"
            intersections[key] = sorted(scenario_sets[left] & scenario_sets[right])
    record(
        "scenario_level_no_leakage",
        all(len(values) == 0 for values in intersections.values()),
        json.dumps(intersections, ensure_ascii=False),
    )

    all_rows = pd.concat(frames.values(), ignore_index=True)
    record("unique_state_id", all_rows["state_id"].nunique() == len(all_rows), f"unique={all_rows['state_id'].nunique()}")
    record("unique_state_hash", all_rows["state_hash"].nunique() == len(all_rows), f"unique={all_rows['state_hash'].nunique()}")
    record("total_rows", len(all_rows) == 2400, f"observed={len(all_rows)}")

    baseline = float(config["baseline_tstt"])
    recomputed = np.log(all_rows["tstt"].to_numpy(dtype=np.float64) / baseline)
    existing = all_rows["log_tstt_ratio"].to_numpy(dtype=np.float64)
    max_label_diff = float(np.max(np.abs(recomputed - existing)))
    record("log_label_reproduction", max_label_diff <= 1e-10, f"max_abs_difference={max_label_diff:.3e}")

    return frames, {
        "checks": checks,
        "scenario_ids": {split: sorted(values) for split, values in scenario_sets.items()},
        "cross_split_intersections": intersections,
        "depth_columns": depth_cols,
        "closed_columns": closed_cols,
        "restored_columns": restored_cols,
        "max_log_label_difference_vs_week1": max_label_diff,
    }


def save_processed(
    frames: dict[str, pd.DataFrame],
    config: dict,
    validation: dict,
    processed_dir: Path,
) -> tuple[dict, dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    depth_cols = validation["depth_columns"]
    closed_cols = validation["closed_columns"]
    restored_cols = validation["restored_columns"]
    baseline = float(config["baseline_tstt"])

    train_depth_raw = frames["train"][depth_cols].to_numpy(dtype=np.float64)
    depth_mean = train_depth_raw.mean(axis=0)
    depth_var = train_depth_raw.var(axis=0, ddof=0)
    depth_scale = np.sqrt(depth_var)
    depth_scale = np.where(depth_scale == 0.0, 1.0, depth_scale)

    def transform_depth(values: np.ndarray) -> np.ndarray:
        return (values - depth_mean) / depth_scale
    processed_feature_names = (
        [name.replace("d_depth_m_", "z_depth_") for name in depth_cols]
        + [name.replace("d_", "") for name in closed_cols]
        + [name.replace("r_", "") for name in restored_cols]
    )

    preprocessor = {
        "schema_version": VERSION,
        "fit_split": "train",
        "fit_sample_count": len(frames["train"]),
        "fit_scenario_ids": sorted(frames["train"]["scenario_id"].astype(int).unique().tolist()),
        "depth_scaler": {
            "implementation": "numpy_standard_scaler",
            "with_mean": True,
            "with_std": True,
            "mean_": depth_mean,
            "var_": depth_var,
            "scale_": depth_scale,
            "n_samples_seen_": len(frames["train"]),
            "transform_formula": "(X_depth - mean_) / scale_",
        },
        "depth_columns": depth_cols,
        "closed_columns": closed_cols,
        "restored_columns": restored_cols,
        "input_feature_names": processed_feature_names,
        "input_dimension": 114,
        "baseline_tstt": baseline,
        "target_formula": "ln(tstt / baseline_tstt)",
    }
    with (STAGING_ROOT / "preprocessor.pkl").open("wb") as handle:
        pickle.dump(preprocessor, handle, protocol=pickle.HIGHEST_PROTOCOL)

    scenario_counts = frames["train"].groupby("scenario_id").size().astype(int)
    n_train = len(frames["train"])
    n_scenarios = len(scenario_counts)
    scenario_total_target = n_train / n_scenarios
    row_weight_by_scenario = {int(s): scenario_total_target / int(n) for s, n in scenario_counts.items()}
    scenario_weight_rows = []
    for scenario_id, count in scenario_counts.items():
        severity = str(frames["train"].loc[frames["train"]["scenario_id"] == scenario_id, "severity"].iloc[0])
        row_weight = row_weight_by_scenario[int(scenario_id)]
        scenario_weight_rows.append(
            {
                "scenario_id": int(scenario_id),
                "severity": severity,
                "state_count": int(count),
                "raw_row_weight_1_over_ns": 1.0 / int(count),
                "normalized_row_weight": row_weight,
                "scenario_total_weight": row_weight * int(count),
            }
        )
    scenario_weights = pd.DataFrame(scenario_weight_rows).sort_values("scenario_id")
    scenario_weights.to_csv(processed_dir / "scenario_equal_weights.csv", index=False, encoding="utf-8-sig")

    split_summary_rows = []
    all_feature_stats = []
    processed_hash_targets: list[Path] = []
    for split, frame in frames.items():
        depth_raw = frame[depth_cols].to_numpy(dtype=np.float64)
        depth_z = transform_depth(depth_raw)
        closed = frame[closed_cols].to_numpy(dtype=np.float64)
        restored = frame[restored_cols].to_numpy(dtype=np.float64)
        X = np.concatenate([depth_z, closed, restored], axis=1).astype(np.float32)
        y = np.log(frame["tstt"].to_numpy(dtype=np.float64) / baseline).astype(np.float64)
        weights = (
            frame["scenario_id"].astype(int).map(row_weight_by_scenario).to_numpy(dtype=np.float64)
            if split == "train"
            else np.ones(len(frame), dtype=np.float64)
        )
        if X.shape != (len(frame), 114):
            raise ValueError(f"{split}: unexpected X shape {X.shape}")
        if not finite(X) or not finite(y) or not finite(weights):
            raise ValueError(f"{split}: non-finite processed values")
        if not np.array_equal(X[:, 38:76], closed.astype(np.float32)):
            raise ValueError(f"{split}: closed indicators changed during preprocessing")
        if not np.array_equal(X[:, 76:114], restored.astype(np.float32)):
            raise ValueError(f"{split}: restored indicators changed during preprocessing")

        npz_path = processed_dir / f"preprocessed_{split}.npz"
        np.savez_compressed(
            npz_path,
            X=X,
            y_log_tstt_ratio=y,
            tstt=frame["tstt"].to_numpy(dtype=np.float64),
            scenario_id=frame["scenario_id"].to_numpy(dtype=np.int32),
            state_id=np.asarray(frame["state_id"].astype(str).tolist(), dtype="U"),
            severity=np.asarray(frame["severity"].astype(str).tolist(), dtype="U"),
            initial_closed_count=frame["initial_closed_count"].to_numpy(dtype=np.int16),
            restored_count=frame["restored_count"].to_numpy(dtype=np.int16),
            sample_weight=weights,
            feature_names=np.asarray(processed_feature_names),
        )
        processed_hash_targets.append(npz_path)

        output_frame = pd.DataFrame(X, columns=processed_feature_names)
        metadata = pd.DataFrame(
            {
                "state_id": frame["state_id"].astype(str),
                "scenario_id": frame["scenario_id"].astype(int),
                "split": split,
                "severity": frame["severity"].astype(str),
                "tstt": frame["tstt"].astype(float),
                "y_log_tstt_ratio": y,
                "sample_weight": weights,
            }
        )
        csv_path = processed_dir / f"preprocessed_{split}.csv.gz"
        pd.concat([metadata.reset_index(drop=True), output_frame], axis=1).to_csv(
            csv_path, index=False, compression="gzip", encoding="utf-8"
        )
        processed_hash_targets.append(csv_path)

        split_summary_rows.append(
            {
                "split": split,
                "sample_count": len(frame),
                "scenario_count": int(frame["scenario_id"].nunique()),
                "scenario_id_min": int(frame["scenario_id"].min()),
                "scenario_id_max": int(frame["scenario_id"].max()),
                "tstt_min": float(frame["tstt"].min()),
                "tstt_median": float(frame["tstt"].median()),
                "tstt_max": float(frame["tstt"].max()),
                "y_min": float(y.min()),
                "y_mean": float(y.mean()),
                "y_max": float(y.max()),
            }
        )

    train_depth_z = transform_depth(frames["train"][depth_cols].to_numpy(dtype=np.float64))
    for idx, raw_name in enumerate(depth_cols):
        all_feature_stats.append(
            {
                "feature_index": idx,
                "processed_name": processed_feature_names[idx],
                "raw_name": raw_name,
                "block": "depth_standardized",
                "train_raw_mean": float(depth_mean[idx]),
                "train_raw_std_population": float(math.sqrt(depth_var[idx])),
                "scaler_scale": float(depth_scale[idx]),
                "train_transformed_mean": float(train_depth_z[:, idx].mean()),
                "train_transformed_std_population": float(train_depth_z[:, idx].std(ddof=0)),
            }
        )
    for offset, raw_names, block in ((38, closed_cols, "initial_closed_binary"), (76, restored_cols, "restored_binary")):
        values = frames["train"][raw_names].to_numpy(dtype=np.float64)
        for idx, raw_name in enumerate(raw_names):
            all_feature_stats.append(
                {
                    "feature_index": offset + idx,
                    "processed_name": processed_feature_names[offset + idx],
                    "raw_name": raw_name,
                    "block": block,
                    "train_raw_mean": float(values[:, idx].mean()),
                    "train_raw_std_population": float(values[:, idx].std(ddof=0)),
                    "scaler_scale": 1.0,
                    "train_transformed_mean": float(values[:, idx].mean()),
                    "train_transformed_std_population": float(values[:, idx].std(ddof=0)),
                }
            )

    split_summary = pd.DataFrame(split_summary_rows)
    feature_stats = pd.DataFrame(all_feature_stats)
    split_summary.to_csv(processed_dir / "split_summary.csv", index=False, encoding="utf-8-sig")
    feature_stats.to_csv(processed_dir / "feature_statistics.csv", index=False, encoding="utf-8-sig")
    processed_hash_targets.extend([processed_dir / "split_summary.csv", processed_dir / "feature_statistics.csv", processed_dir / "scenario_equal_weights.csv"])

    feature_config = {
        "schema_version": VERSION,
        "input_dimension": 114,
        "physical_link_count": 38,
        "block_order": ["standardized_depth", "initial_closed", "restored"],
        "blocks": {
            "standardized_depth": {
                "indices_zero_based": [0, 37],
                "dimension": 38,
                "raw_columns": depth_cols,
                "processed_columns": processed_feature_names[:38],
                "transform": "NumPy standard scaler fitted on training split only: (x - mean) / population_std; zero std uses scale 1",
            },
            "initial_closed": {
                "indices_zero_based": [38, 75],
                "dimension": 38,
                "raw_columns": closed_cols,
                "processed_columns": processed_feature_names[38:76],
                "transform": "identity; preserve binary 0/1",
            },
            "restored": {
                "indices_zero_based": [76, 113],
                "dimension": 38,
                "raw_columns": restored_cols,
                "processed_columns": processed_feature_names[76:114],
                "transform": "identity; preserve binary 0/1",
            },
        },
        "auxiliary_features_included": False,
        "target": {
            "name": "y_log_tstt_ratio",
            "formula": "ln(tstt / baseline_tstt)",
            "baseline_tstt": baseline,
            "inverse_member_formula": "tstt_hat_member = baseline_tstt * exp(y_hat_member)",
        },
        "data_policy": {
            "fit_preprocessor_on": "train only",
            "calibration_role": "normalized split conformal calibration only",
            "test_id_role": "in-distribution evaluation only",
            "test_severe_role": "out-of-distribution stress evaluation only; never tune or recalibrate",
            "split_unit": "complete scenario_id",
        },
        "processed_feature_names": processed_feature_names,
        "dtypes": {"X": "float32", "y_log_tstt_ratio": "float64", "tstt": "float64"},
    }
    write_json(STAGING_ROOT / "feature_config.json", feature_config)

    processed_hashes = {
        str(path.relative_to(STAGING_ROOT)).replace("\\", "/"): {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in processed_hash_targets
    }
    preprocess_metrics = {
        "train_depth_transformed_max_abs_mean": float(np.max(np.abs(train_depth_z.mean(axis=0)))),
        "train_depth_zero_variance_feature_count": int(np.sum(depth_var == 0)),
        "train_depth_nonzero_variance_std_max_abs_error_from_one": float(
            np.max(np.abs(train_depth_z[:, depth_var > 0].std(axis=0, ddof=0) - 1.0))
            if np.any(depth_var > 0)
            else 0.0
        ),
        "scenario_total_weight_min": float(scenario_weights["scenario_total_weight"].min()),
        "scenario_total_weight_max": float(scenario_weights["scenario_total_weight"].max()),
        "training_row_weight_sum": float(
            sum(row_weight_by_scenario[int(value)] for value in frames["train"]["scenario_id"].astype(int))
        ),
    }
    return feature_config, preprocess_metrics, split_summary, feature_stats, scenario_weights


def main() -> None:
    if not SOURCE.is_dir():
        raise FileNotFoundError(SOURCE)
    if FINAL_ROOT.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {FINAL_ROOT}")
    if STAGING_ROOT.exists():
        raise FileExistsError(f"Remove or inspect stale staging directory first: {STAGING_ROOT}")

    STAGING_ROOT.mkdir(parents=True)
    frozen = STAGING_ROOT / FROZEN_NAME
    processed_dir = STAGING_ROOT / "processed"
    scripts_dir = STAGING_ROOT / "scripts"
    processed_dir.mkdir()
    scripts_dir.mkdir()

    shutil.copytree(SOURCE, frozen)
    shutil.copy2(Path(__file__), scripts_dir / Path(__file__).name)
    bootstrap_source = Path(__file__).with_name("scenario_bootstrap.py")
    shutil.copy2(bootstrap_source, scripts_dir / bootstrap_source.name)

    config = json.loads((frozen / "recovery_dataset_config.json").read_text(encoding="utf-8"))
    frames, validation = load_and_validate(frozen, config)
    feature_config, preprocess_metrics, split_summary, feature_stats, scenario_weights = save_processed(
        frames, config, validation, processed_dir
    )

    train_counts = frames["train"].groupby("scenario_id").size().astype(int).to_dict()
    bootstrap_plan = generate_bootstrap_plan(
        scenario_ids=sorted(int(value) for value in train_counts),
        scenario_row_counts={int(k): int(v) for k, v in train_counts.items()},
        n_members=10,
    )
    write_json(STAGING_ROOT / "bootstrap_scenarios.json", bootstrap_plan)
    bootstrap_summary = pd.DataFrame(
        [
            {
                "member_id": member["member_id"],
                "bootstrap_seed": member["bootstrap_seed"],
                "initialization_seed": member["initialization_seed"],
                "unique_inbag_scenario_count": member["unique_inbag_scenario_count"],
                "oob_scenario_count": member["oob_scenario_count"],
                "conceptual_inbag_row_count_with_repeats": member["conceptual_inbag_row_count_with_repeats"],
                "unique_inbag_row_count": member["unique_inbag_row_count"],
                "oob_row_count": member["oob_row_count"],
                "oob_scenario_ids": ",".join(str(value) for value in member["oob_scenario_ids"]),
            }
            for member in bootstrap_plan["members"]
        ]
    )
    bootstrap_summary.to_csv(processed_dir / "bootstrap_summary.csv", index=False, encoding="utf-8-sig")

    frozen_hashes = {}
    for path in sorted(frozen.rglob("*")):
        if path.is_file():
            rel = str(path.relative_to(frozen)).replace("\\", "/")
            frozen_hashes[rel] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}

    generated_paths = [
        STAGING_ROOT / "preprocessor.pkl",
        STAGING_ROOT / "feature_config.json",
        STAGING_ROOT / "bootstrap_scenarios.json",
        processed_dir / "bootstrap_summary.csv",
        scripts_dir / "freeze_and_preprocess.py",
        scripts_dir / "scenario_bootstrap.py",
    ] + sorted(processed_dir.glob("preprocessed_*")) + [
        processed_dir / "split_summary.csv",
        processed_dir / "feature_statistics.csv",
        processed_dir / "scenario_equal_weights.csv",
    ]
    generated_hashes = {
        str(path.relative_to(STAGING_ROOT)).replace("\\", "/"): {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in generated_paths
    }

    qc_checks = list(validation["checks"])
    qc_checks.extend(
        [
            {
                "check": "input_dimension_114",
                "passed": feature_config["input_dimension"] == 114,
                "detail": "38 standardized depth + 38 closed + 38 restored",
            },
            {
                "check": "training_depth_centered",
                "passed": preprocess_metrics["train_depth_transformed_max_abs_mean"] < 1e-10,
                "detail": f"max_abs_mean={preprocess_metrics['train_depth_transformed_max_abs_mean']:.3e}",
            },
            {
                "check": "training_depth_scaled",
                "passed": preprocess_metrics["train_depth_nonzero_variance_std_max_abs_error_from_one"] < 1e-10,
                "detail": f"max_abs_std_error={preprocess_metrics['train_depth_nonzero_variance_std_max_abs_error_from_one']:.3e}",
            },
            {
                "check": "scenario_equal_total_weight",
                "passed": abs(preprocess_metrics["scenario_total_weight_max"] - preprocess_metrics["scenario_total_weight_min"]) < 1e-12,
                "detail": f"total_per_scenario={preprocess_metrics['scenario_total_weight_min']:.12g}",
            },
            {
                "check": "bootstrap_oob_available",
                "passed": all(member["oob_scenario_count"] > 0 for member in bootstrap_plan["members"]),
                "detail": "all 10 members have non-empty OOB scenarios",
            },
        ]
    )
    qc_frame = pd.DataFrame(qc_checks)
    qc_frame.to_csv(processed_dir / "qc_checks.csv", index=False, encoding="utf-8-sig")

    manifest = {
        "dataset_version": FROZEN_NAME,
        "schema_version": VERSION,
        "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "source_dataset_path": str(SOURCE),
        "frozen_dataset_relative_path": FROZEN_NAME,
        "freeze_method": "byte-for-byte copy plus SHA-256 manifest; original first-week files were not modified",
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "preprocessor_implementation": "NumPy training-only mean and population standard deviation",
        "baseline_tstt": float(config["baseline_tstt"]),
        "splits": {
            split: {
                "file": SPLIT_FILES[split],
                "sample_count": int(len(frame)),
                "scenario_count": int(frame["scenario_id"].nunique()),
                "scenario_ids": sorted(frame["scenario_id"].astype(int).unique().tolist()),
                "allowed_use": {
                    "train": "fit model weights and training-only preprocessing",
                    "calibration": "fit normalized split-conformal calibration parameters only",
                    "test_id": "frozen in-distribution evaluation only",
                    "test_severe": "frozen OOD stress evaluation only; no tuning or recalibration",
                }[split],
            }
            for split, frame in frames.items()
        },
        "cross_split_scenario_intersections": validation["cross_split_intersections"],
        "feature_dimension": 114,
        "target_formula": "ln(tstt / baseline_tstt)",
        "preprocessing_fit_split": "train",
        "max_log_label_difference_vs_week1": validation["max_log_label_difference_vs_week1"],
        "preprocessing_metrics": preprocess_metrics,
        "bootstrap": {
            "n_members": bootstrap_plan["n_members"],
            "sampling_unit": bootstrap_plan["sampling_unit"],
            "draws_per_member": bootstrap_plan["draws_per_member"],
            "with_replacement": True,
            "oob_used_for": "member-specific validation and early stopping",
        },
        "all_qc_passed": bool(qc_frame["passed"].all()),
        "qc_check_count": int(len(qc_frame)),
        "frozen_file_hashes": frozen_hashes,
        "generated_artifact_hashes": generated_hashes,
    }
    write_json(STAGING_ROOT / "dataset_manifest.json", manifest)

    readme = f"""# 第二周第1天：数据冻结与预处理

## 完成状态

- 冻结版本：`{FROZEN_NAME}`（第一周目录逐字节复制，原文件未修改）
- 四类样本：train={len(frames['train'])}、calibration={len(frames['calibration'])}、test_id={len(frames['test_id'])}、test_severe={len(frames['test_severe'])}
- 情景数：60 / 20 / 20 / 20，任意两类的 scenario_id 交集均为 0
- 输入：114维，顺序为 38 个标准化水深 + 38 个初始关闭标记 + 38 个已恢复标记
- 标签：`ln(TSTT / {float(config['baseline_tstt']):.10f})`
- 标准化器：只在训练集上拟合；校准和测试数据只调用 transform
- 权重：训练集中每个情景的总权重均为 {preprocess_metrics['scenario_total_weight_min']:.6g}
- bootstrap：10 组，按 60 个训练情景有放回抽取 60 次，每组均保留非空 OOB 情景
- 质量检查：{int(qc_frame['passed'].sum())}/{len(qc_frame)} 通过

## 核心交付物

- `preprocessor.pkl`：训练集水深 StandardScaler、列顺序、基准 TSTT 和目标定义
- `feature_config.json`：114 维输入、特征块、数据用途和反变换公式
- `dataset_manifest.json`：版本、划分、质量检查、软件版本和 SHA-256 哈希
- `bootstrap_scenarios.json`：10 个成员的情景抽样、重复次数、OOB 情景和随机种子
- `processed/preprocessed_*.npz`：第二天模型直接读取的四类数组
- `processed/preprocessed_*.csv.gz`：便于审计的压缩表格版本
- `processed/scenario_equal_weights.csv`：训练情景均衡权重
- `scripts/scenario_bootstrap.py`：可独立复现 bootstrap 计划

## 不可违反的数据用途

1. 校准集不参与模型权重训练或 OOB 早停。
2. 普通测试集不用于网络结构选择。
3. 严重测试集不用于调参或重新估计共形分位数。
4. 不得重新合并四类数据后随机划分。
"""
    (STAGING_ROOT / "README_CN.md").write_text(readme, encoding="utf-8")

    os.replace(STAGING_ROOT, FINAL_ROOT)
    print(json.dumps({
        "output": str(FINAL_ROOT),
        "all_qc_passed": manifest["all_qc_passed"],
        "qc_check_count": manifest["qc_check_count"],
        "preprocess_metrics": preprocess_metrics,
        "bootstrap_oob_counts": [m["oob_scenario_count"] for m in bootstrap_plan["members"]],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
