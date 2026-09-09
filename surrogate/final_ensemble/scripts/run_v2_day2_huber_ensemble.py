from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import shutil
import sys
import time
from pathlib import Path

TORCH_DEPS = os.environ.get("TORCH_DEPS")
if TORCH_DEPS:
    sys.path.insert(0, TORCH_DEPS)

import numpy as np
import pandas as pd
import torch
from torch import nn


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WEEK1 = REPOSITORY_ROOT / "data/surrogate_training_and_preprocessing/week1_recovery_dataset_v1.0"
NEW_DAY1 = REPOSITORY_ROOT / "data/surrogate_training_and_preprocessing/training_expansion"
OUTPUT = REPOSITORY_ROOT / "reproduced_surrogate"
STAGING = REPOSITORY_ROOT / ".reproduced_surrogate_staging"

DATA_FILES = {
    "train_original": WEEK1 / "recovery_states_train.csv",
    "train_expansion": NEW_DAY1 / "recovery/v2_new_training_states.csv.gz",
    "calibration": WEEK1 / "recovery_states_calibration.csv",
    "internal_id": WEEK1 / "recovery_states_test_id.csv",
    "internal_severe": WEEK1 / "recovery_states_test_severe.csv",
}
CRITICAL_LINKS = WEEK1 / "input_validation/critical_links.csv"

N_LINKS = 38
ARCHITECTURE = [120, 128, 64, 32, 1]
N_MEMBERS = 10
ACTIVATION = "ReLU"
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-5
BATCH_SIZE = 128
MAX_EPOCHS = 1000
EARLY_STOPPING_PATIENCE = 100
LR_PATIENCE = 25
LR_FACTOR = 0.5
MIN_LR = 1e-6
MIN_DELTA = 1e-7
HUBER_DELTA = 1.0
BOOTSTRAP_SEEDS = [2026080601 + i * 101 for i in range(N_MEMBERS)]
INITIALIZATION_SEEDS = [2026080701 + i * 103 for i in range(N_MEMBERS)]
DEVICE = "cpu"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def depth_columns() -> list[str]:
    return [f"d_depth_m_pl{i:03d}" for i in range(1, N_LINKS + 1)]


def closed_columns() -> list[str]:
    return [f"d_closed_pl{i:03d}" for i in range(1, N_LINKS + 1)]


def restored_columns() -> list[str]:
    return [f"r_restored_pl{i:03d}" for i in range(1, N_LINKS + 1)]


def load_raw(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = [
        "state_id", "scenario_id", "severity", "restored_count", "state_hash",
        "tstt", "log_tstt_ratio", *depth_columns(), *closed_columns(), *restored_columns(),
    ]
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"Missing columns in {path}: {missing}")
    return df


def raw_aggregate_features(df: pd.DataFrame, flows: np.ndarray, betweenness: np.ndarray) -> pd.DataFrame:
    depth = df[depth_columns()].to_numpy(dtype=np.float64)
    closed = df[closed_columns()].to_numpy(dtype=np.float64)
    restored = df[restored_columns()].to_numpy(dtype=np.float64)
    initially_closed = np.maximum(closed, restored)
    return pd.DataFrame(
        {
            "agg_n_closed": closed.sum(axis=1),
            "agg_n_restored": restored.sum(axis=1),
            "agg_sum_depth_m": depth.sum(axis=1),
            "agg_sum_initially_closed_depth_m": (depth * initially_closed).sum(axis=1),
            "agg_remaining_closed_baseline_flow": closed @ flows,
            "agg_remaining_closed_betweenness": closed @ betweenness,
        },
        index=df.index,
    )


def fit_preprocessor(train: pd.DataFrame, flows: np.ndarray, betweenness: np.ndarray) -> dict:
    depth = train[depth_columns()].to_numpy(dtype=np.float64)
    aggregate = raw_aggregate_features(train, flows, betweenness)
    depth_mean = depth.mean(axis=0)
    depth_std = depth.std(axis=0, ddof=0)
    depth_std[depth_std < 1e-12] = 1.0
    agg_mean = aggregate.mean(axis=0).to_numpy(dtype=np.float64, copy=True)
    agg_std = aggregate.std(axis=0, ddof=0).to_numpy(dtype=np.float64, copy=True)
    agg_std[agg_std < 1e-12] = 1.0
    feature_names: list[str] = []
    for index in range(1, N_LINKS + 1):
        feature_names.extend(
            [f"z_depth_m_pl{index:03d}", f"d_closed_pl{index:03d}", f"r_restored_pl{index:03d}"]
        )
    feature_names.extend([f"z_{name}" for name in aggregate.columns])
    return {
        "depth_mean": depth_mean,
        "depth_std": depth_std,
        "aggregate_names": aggregate.columns.tolist(),
        "aggregate_mean": agg_mean,
        "aggregate_std": agg_std,
        "feature_names": feature_names,
    }


def transform(df: pd.DataFrame, preprocessor: dict, flows: np.ndarray, betweenness: np.ndarray) -> np.ndarray:
    depth = df[depth_columns()].to_numpy(dtype=np.float64)
    closed = df[closed_columns()].to_numpy(dtype=np.float64)
    restored = df[restored_columns()].to_numpy(dtype=np.float64)
    depth_z = (depth - preprocessor["depth_mean"]) / preprocessor["depth_std"]
    link_blocks = np.stack([depth_z, closed, restored], axis=2).reshape(len(df), -1)
    aggregate = raw_aggregate_features(df, flows, betweenness).to_numpy(dtype=np.float64)
    aggregate_z = (aggregate - preprocessor["aggregate_mean"]) / preprocessor["aggregate_std"]
    X = np.column_stack([link_blocks, aggregate_z]).astype(np.float32)
    if X.shape[1] != ARCHITECTURE[0] or not np.isfinite(X).all():
        raise ValueError(f"Invalid transformed matrix: shape={X.shape}, finite={np.isfinite(X).all()}")
    return X


def scenario_balanced_weights(scenario_ids: np.ndarray) -> np.ndarray:
    counts = pd.Series(scenario_ids).value_counts().to_dict()
    return np.asarray([1.0 / counts[int(value)] for value in scenario_ids], dtype=np.float32)


def make_bootstrap_plan(scenario_ids: np.ndarray) -> dict:
    unique = np.sort(np.unique(scenario_ids)).astype(int)
    members = []
    for member_index, (bootstrap_seed, init_seed) in enumerate(
        zip(BOOTSTRAP_SEEDS, INITIALIZATION_SEEDS), start=1
    ):
        rng = np.random.default_rng(bootstrap_seed)
        draws = rng.choice(unique, size=len(unique), replace=True)
        values, counts = np.unique(draws, return_counts=True)
        multiplicity = {str(int(value)): int(count) for value, count in zip(values, counts)}
        oob = sorted(set(unique.tolist()) - set(values.tolist()))
        if len(oob) == 0:
            raise ValueError(f"member_{member_index:02d} has no OOB scenario")
        members.append(
            {
                "member_id": f"member_{member_index:02d}",
                "bootstrap_seed": bootstrap_seed,
                "initialization_seed": init_seed,
                "draw_count": int(len(draws)),
                "unique_inbag_scenario_count": int(len(values)),
                "oob_scenario_count": int(len(oob)),
                "scenario_multiplicity": multiplicity,
                "oob_scenario_ids": oob,
            }
        )
    return {
        "schema_version": "2.0",
        "sampling_unit": "scenario_id",
        "draws_per_member": int(len(unique)),
        "training_scenario_count": int(len(unique)),
        "member_count": N_MEMBERS,
        "members": members,
    }


class RecoveryMLPV2(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(120, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )
        self.reset_parameters()

    def reset_parameters(self) -> None:
        layers = [module for module in self.network if isinstance(module, nn.Linear)]
        for index, layer in enumerate(layers):
            if index < len(layers) - 1:
                nn.init.kaiming_normal_(layer.weight, nonlinearity="relu")
            else:
                nn.init.normal_(layer.weight, mean=0.0, std=math.sqrt(1.0 / layer.in_features))
            nn.init.zeros_(layer.bias)

    def forward(self, X: torch.Tensor) -> torch.Tensor:
        return self.network(X).squeeze(-1)


def huber_elements(pred: torch.Tensor, true: torch.Tensor) -> torch.Tensor:
    error = torch.abs(pred - true)
    quadratic = torch.minimum(error, torch.tensor(HUBER_DELTA, device=error.device, dtype=error.dtype))
    linear = error - quadratic
    return 0.5 * torch.square(quadratic) + HUBER_DELTA * linear


def weighted_huber_torch(pred: torch.Tensor, true: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    return torch.sum(weight * huber_elements(pred, true)) / torch.sum(weight)


def weighted_huber_np(pred: np.ndarray, true: np.ndarray, weight: np.ndarray) -> float:
    error = np.abs(pred - true)
    values = np.where(error <= HUBER_DELTA, 0.5 * error**2, HUBER_DELTA * (error - 0.5 * HUBER_DELTA))
    return float(np.sum(weight * values) / np.sum(weight))


def predict(model: nn.Module, X: np.ndarray, batch_size: int = 4096) -> np.ndarray:
    outputs = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(X), batch_size):
            outputs.append(model(torch.from_numpy(X[start : start + batch_size])).cpu().numpy())
    return np.concatenate(outputs).astype(np.float64)


def r2_score(pred: np.ndarray, true: np.ndarray) -> float:
    denominator = float(np.sum((true - true.mean()) ** 2))
    return float(1.0 - np.sum((pred - true) ** 2) / denominator) if denominator > 0 else float("nan")


def point_metrics(pred: np.ndarray, true: np.ndarray) -> dict:
    error = pred - true
    return {
        "n": int(len(true)),
        "r2_log": r2_score(pred, true),
        "rmse_log": float(np.sqrt(np.mean(error**2))),
        "mae_log": float(np.mean(np.abs(error))),
    }


def ranking_metrics(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows = []
    for (scenario_id, restored_count), group in frame.groupby(["scenario_id", "restored_count"]):
        if len(group) < 2 or group["true_y_log_ratio"].nunique() < 2:
            continue
        true = group["true_y_log_ratio"].to_numpy(dtype=float)
        pred = group["ensemble_mean_y"].to_numpy(dtype=float)
        true_rank = pd.Series(true).rank(method="average").to_numpy()
        pred_rank = pd.Series(pred).rank(method="average").to_numpy()
        spearman = float(np.corrcoef(true_rank, pred_rank)[0, 1]) if np.std(pred_rank) > 0 else float("nan")
        correct = 0
        comparable = 0
        for i in range(len(true)):
            for j in range(i + 1, len(true)):
                true_sign = np.sign(true[i] - true[j])
                pred_sign = np.sign(pred[i] - pred[j])
                if true_sign == 0:
                    continue
                comparable += 1
                correct += int(pred_sign == true_sign)
        rows.append(
            {
                "scenario_id": int(scenario_id),
                "restored_count": int(restored_count),
                "n_states": int(len(group)),
                "spearman": spearman,
                "pairwise_accuracy": correct / comparable if comparable else float("nan"),
                "comparable_pairs": comparable,
            }
        )
    result = pd.DataFrame(rows)
    summary = {
        "eligible_group_count": int(len(result)),
        "median_same_stage_spearman": float(result["spearman"].median()) if len(result) else float("nan"),
        "q25_same_stage_spearman": float(result["spearman"].quantile(0.25)) if len(result) else float("nan"),
        "median_pairwise_accuracy": float(result["pairwise_accuracy"].median()) if len(result) else float("nan"),
        "q25_pairwise_accuracy": float(result["pairwise_accuracy"].quantile(0.25)) if len(result) else float("nan"),
    }
    return result, summary


def train_member(
    member: dict,
    X_all: np.ndarray,
    y_all: np.ndarray,
    scenario_all: np.ndarray,
    base_weight: np.ndarray,
    models_dir: Path,
    histories_dir: Path,
    summaries_dir: Path,
    preprocessor_hash: str,
) -> dict:
    member_id = member["member_id"]
    multiplicity = {int(key): int(value) for key, value in member["scenario_multiplicity"].items()}
    oob_scenarios = set(member["oob_scenario_ids"])
    inbag_mask = np.asarray([int(value) in multiplicity for value in scenario_all], dtype=bool)
    oob_mask = np.asarray([int(value) in oob_scenarios for value in scenario_all], dtype=bool)
    if np.any(inbag_mask & oob_mask) or not np.all(inbag_mask | oob_mask):
        raise ValueError(f"Invalid inbag/OOB partition for {member_id}")

    X_train = X_all[inbag_mask]
    y_train = y_all[inbag_mask]
    scenario_train = scenario_all[inbag_mask]
    w_train = base_weight[inbag_mask] * np.asarray(
        [multiplicity[int(value)] for value in scenario_train], dtype=np.float32
    )
    X_oob = X_all[oob_mask]
    y_oob = y_all[oob_mask]
    scenario_oob = scenario_all[oob_mask]
    w_oob = scenario_balanced_weights(scenario_oob)

    init_seed = int(member["initialization_seed"])
    torch.manual_seed(init_seed)
    rng = np.random.default_rng(init_seed + 10000)
    model = RecoveryMLPV2().to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=LR_FACTOR, patience=LR_PATIENCE, min_lr=MIN_LR
    )
    X_oob_tensor = torch.from_numpy(X_oob)
    y_oob_tensor = torch.from_numpy(y_oob)
    w_oob_tensor = torch.from_numpy(w_oob)
    best_loss = float("inf")
    best_epoch = 0
    best_state = copy.deepcopy(model.state_dict())
    without_improvement = 0
    history = []
    started = time.perf_counter()

    for epoch in range(1, MAX_EPOCHS + 1):
        model.train()
        order = rng.permutation(len(X_train))
        for start in range(0, len(order), BATCH_SIZE):
            idx = order[start : start + BATCH_SIZE]
            optimizer.zero_grad(set_to_none=True)
            loss = weighted_huber_torch(
                model(torch.from_numpy(X_train[idx])),
                torch.from_numpy(y_train[idx]),
                torch.from_numpy(w_train[idx]),
            )
            if not torch.isfinite(loss):
                raise FloatingPointError(f"Non-finite loss for {member_id} epoch {epoch}")
            loss.backward()
            optimizer.step()
        train_pred = predict(model, X_train)
        train_loss = weighted_huber_np(train_pred, y_train, w_train)
        model.eval()
        with torch.no_grad():
            oob_loss = float(weighted_huber_torch(model(X_oob_tensor), y_oob_tensor, w_oob_tensor))
        current_lr = float(optimizer.param_groups[0]["lr"])
        improved = oob_loss < best_loss - MIN_DELTA
        if improved:
            best_loss = oob_loss
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
            without_improvement = 0
        else:
            without_improvement += 1
        history.append(
            {
                "member_id": member_id,
                "epoch": epoch,
                "train_weighted_huber": train_loss,
                "oob_weighted_huber": oob_loss,
                "learning_rate": current_lr,
                "best_oob_huber_so_far": best_loss,
                "improved": improved,
                "epochs_without_improvement": without_improvement,
            }
        )
        scheduler.step(oob_loss)
        if without_improvement >= EARLY_STOPPING_PATIENCE:
            break

    model.load_state_dict(best_state)
    best_train_pred = predict(model, X_train)
    best_oob_pred = predict(model, X_oob)
    training_seconds = time.perf_counter() - started
    best_train_huber = weighted_huber_np(best_train_pred, y_train, w_train)
    best_oob_huber = weighted_huber_np(best_oob_pred, y_oob, w_oob)
    checkpoint = {
        "state_dict": {key: value.cpu() for key, value in best_state.items()},
        "architecture": ARCHITECTURE,
        "activation": ACTIVATION,
        "loss": "scenario-balanced Huber",
        "huber_delta": HUBER_DELTA,
        "member_id": member_id,
        "bootstrap_seed": int(member["bootstrap_seed"]),
        "initialization_seed": init_seed,
        "scenario_multiplicity": member["scenario_multiplicity"],
        "oob_scenario_ids": member["oob_scenario_ids"],
        "best_epoch": best_epoch,
        "best_train_weighted_huber": best_train_huber,
        "best_oob_weighted_huber": best_oob_huber,
        "preprocessor_sha256": preprocessor_hash,
        "torch_version": torch.__version__,
    }
    model_path = models_dir / f"{member_id}.pt"
    torch.save(checkpoint, model_path)
    pd.DataFrame(history).to_csv(
        histories_dir / f"{member_id}_training_history.csv", index=False, encoding="utf-8-sig"
    )
    summary = {
        "member_id": member_id,
        "bootstrap_seed": int(member["bootstrap_seed"]),
        "initialization_seed": init_seed,
        "unique_inbag_scenarios": int(member["unique_inbag_scenario_count"]),
        "oob_scenarios": int(member["oob_scenario_count"]),
        "unique_inbag_rows": int(inbag_mask.sum()),
        "oob_rows": int(oob_mask.sum()),
        "epochs_completed": int(len(history)),
        "best_epoch": int(best_epoch),
        "best_train_weighted_huber": best_train_huber,
        "best_oob_weighted_huber": best_oob_huber,
        "best_oob_rmse_log": float(np.sqrt(np.mean((best_oob_pred - y_oob) ** 2))),
        "oob_r2_log": r2_score(best_oob_pred, y_oob),
        "training_time_seconds": training_seconds,
        "model_hash_sha256": sha256_file(model_path),
        "retained": True,
    }
    write_json(summaries_dir / f"{member_id}_summary.json", summary)
    return summary


def load_model(path: Path) -> tuple[RecoveryMLPV2, dict]:
    checkpoint = torch.load(path, map_location=DEVICE, weights_only=False)
    model = RecoveryMLPV2()
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, checkpoint


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {OUTPUT}")
    if STAGING.exists():
        raise FileExistsError(f"Stale staging directory exists: {STAGING}")
    STAGING.mkdir(parents=True)
    models_dir = STAGING / "models"
    histories_dir = STAGING / "histories"
    summaries_dir = STAGING / "summaries"
    processed_dir = STAGING / "processed"
    scripts_dir = STAGING / "scripts"
    for directory in (models_dir, histories_dir, summaries_dir, processed_dir, scripts_dir):
        directory.mkdir()
    shutil.copy2(Path(__file__), scripts_dir / Path(__file__).name)

    protocol = {
        "version": "v2-day2-frozen-before-fitting",
        "method": "10-member deep ensemble with scenario bootstrap and scenario-balanced Huber loss",
        "training_scenario_ids": "1-60 and 201-260",
        "post_freeze_only": {"calibration": "61-80", "internal_id": "81-100", "internal_severe": "101-120"},
        "permanently_excluded_final_v1": "121-160",
        "new_final_holdout_generated": False,
        "architecture": ARCHITECTURE,
        "aggregate_features": [
            "remaining closed link count", "restored link count", "total depth",
            "initially closed depth sum", "remaining closed baseline flow", "remaining closed betweenness",
        ],
        "huber_delta": HUBER_DELTA,
        "hyperparameter_search": False,
        "member_selection": False,
    }
    write_json(STAGING / "v2_day2_protocol_pre_registered.json", protocol)

    critical = pd.read_csv(CRITICAL_LINKS).sort_values("physical_link_id")
    if critical["physical_link_id"].tolist() != list(range(1, N_LINKS + 1)):
        raise ValueError("Critical-link table does not cover physical links 1-38 in order")
    flows = critical["physical_flow"].to_numpy(dtype=np.float64)
    betweenness = critical["betweenness"].to_numpy(dtype=np.float64)

    old_train = load_raw(DATA_FILES["train_original"])
    new_train = load_raw(DATA_FILES["train_expansion"])
    train = pd.concat([old_train, new_train], ignore_index=True, sort=False)
    expected_ids = set(range(1, 61)) | set(range(201, 261))
    actual_ids = set(train["scenario_id"].astype(int).unique())
    if actual_ids != expected_ids:
        raise ValueError(f"Unexpected training scenarios: missing={expected_ids-actual_ids}, extra={actual_ids-expected_ids}")
    if train["state_hash"].duplicated().any():
        raise ValueError("Duplicate state_hash detected in combined training pool")
    if set(train["scenario_id"]) & set(range(121, 161)):
        raise ValueError("Forbidden v1 final scenarios entered training")

    preprocessor = fit_preprocessor(train, flows, betweenness)
    preprocessor_json = {
        "schema_version": "2.0",
        "fit_scope": "combined training only: scenarios 1-60 and 201-260",
        "input_dimension": ARCHITECTURE[0],
        "depth_columns": depth_columns(),
        "depth_mean": preprocessor["depth_mean"].tolist(),
        "depth_std": preprocessor["depth_std"].tolist(),
        "aggregate_names": preprocessor["aggregate_names"],
        "aggregate_mean": preprocessor["aggregate_mean"].tolist(),
        "aggregate_std": preprocessor["aggregate_std"].tolist(),
        "feature_names": preprocessor["feature_names"],
        "baseline_flow": flows.tolist(),
        "betweenness": betweenness.tolist(),
    }
    preprocessor_path = STAGING / "preprocessor_v2.json"
    write_json(preprocessor_path, preprocessor_json)
    preprocessor_hash = sha256_file(preprocessor_path)

    X_train = transform(train, preprocessor, flows, betweenness)
    y_train = train["log_tstt_ratio"].to_numpy(dtype=np.float32)
    scenario_train = train["scenario_id"].to_numpy(dtype=int)
    base_weight = scenario_balanced_weights(scenario_train)
    np.savez_compressed(
        processed_dir / "preprocessed_train_v2.npz",
        X=X_train,
        y_log_tstt_ratio=y_train,
        scenario_id=scenario_train,
        state_id=train["state_id"].astype(str).to_numpy(),
        severity=train["severity"].astype(str).to_numpy(),
        restored_count=train["restored_count"].to_numpy(dtype=int),
        tstt=train["tstt"].to_numpy(dtype=float),
        sample_weight=base_weight,
    )
    train_manifest = {
        "row_count": int(len(train)),
        "scenario_count": int(train["scenario_id"].nunique()),
        "scenario_id_ranges": ["1-60", "201-260"],
        "severity_scenarios": train.groupby("severity")["scenario_id"].nunique().astype(int).to_dict(),
        "severity_rows": train.groupby("severity").size().astype(int).to_dict(),
        "unique_state_hashes": int(train["state_hash"].nunique()),
        "source_files": {key: {"path": str(path), "sha256": sha256_file(path)} for key, path in DATA_FILES.items()},
        "critical_links": {"path": str(CRITICAL_LINKS), "sha256": sha256_file(CRITICAL_LINKS)},
        "preprocessor_sha256": preprocessor_hash,
    }
    write_json(STAGING / "combined_training_manifest.json", train_manifest)

    bootstrap = make_bootstrap_plan(scenario_train)
    bootstrap_path = STAGING / "bootstrap_scenarios_v2.json"
    write_json(bootstrap_path, bootstrap)

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    summaries = []
    total_started = time.perf_counter()
    for index, member in enumerate(bootstrap["members"], start=1):
        summary = train_member(
            member, X_train, y_train, scenario_train, base_weight,
            models_dir, histories_dir, summaries_dir, preprocessor_hash,
        )
        summaries.append(summary)
        print(json.dumps({
            "progress": f"{index}/{N_MEMBERS}", "member": summary["member_id"],
            "best_epoch": summary["best_epoch"], "oob_rmse_log": summary["best_oob_rmse_log"],
            "oob_r2_log": summary["oob_r2_log"], "seconds": summary["training_time_seconds"],
        }, ensure_ascii=False), flush=True)
    total_training_seconds = time.perf_counter() - total_started
    summary_frame = pd.DataFrame(summaries)
    summary_frame.to_csv(STAGING / "ensemble_training_summary.csv", index=False, encoding="utf-8-sig")

    # Only now, after all checkpoints are frozen, are calibration and internal validation files read.
    models = []
    checkpoint_ok = True
    for member in bootstrap["members"]:
        path = models_dir / f"{member['member_id']}.pt"
        model, checkpoint = load_model(path)
        checkpoint_ok &= checkpoint["member_id"] == member["member_id"]
        checkpoint_ok &= checkpoint["preprocessor_sha256"] == preprocessor_hash
        models.append((member["member_id"], model))

    split_frames = {"train": train}
    for split in ("calibration", "internal_id", "internal_severe"):
        split_frames[split] = load_raw(DATA_FILES[split])
    predictions = []
    split_metrics = {}
    ranking_summaries = {}
    nonfinite = 0
    baseline_tstt = float((train["tstt"] / np.exp(train["log_tstt_ratio"])).median())
    for split, frame in split_frames.items():
        X = X_train if split == "train" else transform(frame, preprocessor, flows, betweenness)
        member_y = np.column_stack([predict(model, X) for _, model in models])
        member_tstt = baseline_tstt * np.exp(member_y)
        nonfinite += int((~np.isfinite(member_y)).sum() + (~np.isfinite(member_tstt)).sum())
        output = pd.DataFrame(
            {
                "state_id": frame["state_id"].astype(str),
                "scenario_id": frame["scenario_id"].astype(int),
                "split": split,
                "severity": frame["severity"].astype(str),
                "restored_count": frame["restored_count"].astype(int),
                "true_y_log_ratio": frame["log_tstt_ratio"].astype(float),
                "true_tstt": frame["tstt"].astype(float),
                "ensemble_mean_y": member_y.mean(axis=1),
                "ensemble_std_y_ddof1": member_y.std(axis=1, ddof=1),
                "ensemble_mean_tstt_member_scale": member_tstt.mean(axis=1),
                "ensemble_std_tstt_member_scale_ddof1": member_tstt.std(axis=1, ddof=1),
            }
        )
        for model_index, (member_id, _) in enumerate(models):
            output[f"{member_id}_y"] = member_y[:, model_index]
            output[f"{member_id}_tstt"] = member_tstt[:, model_index]
        predictions.append(output)
        split_metrics[split] = point_metrics(
            output["ensemble_mean_y"].to_numpy(), output["true_y_log_ratio"].to_numpy()
        )
        ranking_detail, ranking_summary = ranking_metrics(output)
        ranking_detail.to_csv(
            STAGING / f"same_stage_ranking_{split}.csv", index=False, encoding="utf-8-sig"
        )
        ranking_summaries[split] = ranking_summary

    prediction_frame = pd.concat(predictions, ignore_index=True)
    prediction_frame.to_csv(
        STAGING / "ensemble_predictions_raw_v2.csv.gz", index=False, compression="gzip", encoding="utf-8"
    )
    write_json(STAGING / "point_metrics_internal.json", split_metrics)
    write_json(STAGING / "same_stage_ranking_summary.json", ranking_summaries)

    config = {
        "framework": "PyTorch",
        "torch_version": torch.__version__,
        "device": DEVICE,
        "architecture": ARCHITECTURE,
        "activation": ACTIVATION,
        "optimizer": "Adam",
        "learning_rate": LEARNING_RATE,
        "weight_decay": WEIGHT_DECAY,
        "batch_size": BATCH_SIZE,
        "maximum_epochs": MAX_EPOCHS,
        "early_stopping_patience": EARLY_STOPPING_PATIENCE,
        "lr_scheduler": {"type": "ReduceLROnPlateau", "patience": LR_PATIENCE, "factor": LR_FACTOR, "minimum_lr": MIN_LR},
        "loss": "scenario-balanced, bootstrap-multiplicity-weighted Huber on log(TSTT/TSTT0)",
        "huber_delta": HUBER_DELTA,
        "member_count": N_MEMBERS,
        "member_retention": "all 10 retained; no OOB/calibration/test selection",
        "training_access": "only scenarios 1-60 and 201-260 until all checkpoints frozen",
        "post_freeze_access": "61-120 only for calibration/internal diagnostics after checkpoint freeze",
        "forbidden_access": "v1 final scenarios 121-160 not read; no new final holdout generated",
        "total_training_seconds": total_training_seconds,
    }
    write_json(STAGING / "ensemble_training_config_v2.json", config)

    checks = {
        "combined_training_rows_3178": len(train) == 3178,
        "combined_training_scenarios_120": train["scenario_id"].nunique() == 120,
        "training_has_15_severe_scenarios": train.loc[train["severity"] == "severe", "scenario_id"].nunique() == 15,
        "unique_training_state_hashes": train["state_hash"].nunique() == len(train),
        "input_dimension_120": X_train.shape[1] == 120,
        "model_files_10": len(list(models_dir.glob("member_*.pt"))) == 10,
        "unique_model_hashes_10": summary_frame["model_hash_sha256"].nunique() == 10,
        "all_checkpoints_reload": bool(checkpoint_ok),
        "all_members_retained": bool(summary_frame["retained"].all()),
        "nonfinite_predictions_zero": nonfinite == 0,
        "prediction_rows_4078": len(prediction_frame) == 4078,
        "forbidden_v1_final_absent": not prediction_frame["scenario_id"].isin(range(121, 161)).any(),
        "new_final_holdout_not_generated": True,
    }
    verification = {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "training_summary": {
            "oob_rmse_log_range": [float(summary_frame["best_oob_rmse_log"].min()), float(summary_frame["best_oob_rmse_log"].max())],
            "oob_r2_log_range": [float(summary_frame["oob_r2_log"].min()), float(summary_frame["oob_r2_log"].max())],
            "total_training_seconds": total_training_seconds,
        },
        "internal_point_metrics": split_metrics,
        "same_stage_ranking": ranking_summaries,
        "interpretation": "Internal metrics are development diagnostics, not untouched final evidence.",
    }
    write_json(STAGING / "verification_report.json", verification)

    report = "v2 第二天：聚合特征 + scenario 均衡 Huber 深度集成\n\n"
    report += f"结论：{verification['status'].upper()}\n"
    report += f"训练池：120 个情景、3178 个状态；严重情景 15 个。\n"
    report += "输入：原 114 维状态变量 + 6 个聚合变量 = 120 维。\n"
    report += "模型：10 个 120-128-64-32-1 MLP；scenario bootstrap；Huber δ=1.0；全部成员保留。\n"
    report += f"OOB R²(log) 范围：{summary_frame['oob_r2_log'].min():.4f} 至 {summary_frame['oob_r2_log'].max():.4f}。\n"
    report += f"内部普通验证 R²(log)：{split_metrics['internal_id']['r2_log']:.4f}。\n"
    report += f"内部严重验证 R²(log)：{split_metrics['internal_severe']['r2_log']:.4f}。\n"
    report += f"训练集同阶段 Spearman 中位数：{ranking_summaries['train']['median_same_stage_spearman']:.4f}；配对准确率中位数：{ranking_summaries['train']['median_pairwise_accuracy']:.4f}。\n"
    report += "边界：校准/内部验证仅在模型冻结后读取；v1 终验 121-160 未读取；尚未生成新终验集。\n"
    report += "下一步：基于冻结预测重建独立校准，并按严重度构建 scenario-OOB 认知误差轨迹库。\n"
    (STAGING / "结果说明.txt").write_text(report, encoding="utf-8")

    hashes = {}
    for path in sorted(STAGING.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            hashes[str(path.relative_to(STAGING)).replace("\\", "/")] = {
                "sha256": sha256_file(path), "bytes": path.stat().st_size,
            }
    write_json(STAGING / "artifact_manifest.json", {"schema_version": "2.0", "files": hashes})
    STAGING.replace(OUTPUT)
    print(json.dumps({
        "output": str(OUTPUT), "status": verification["status"],
        "training_rows": len(train), "training_scenarios": train["scenario_id"].nunique(),
        "total_training_seconds": total_training_seconds,
        "internal_id_r2_log": split_metrics["internal_id"]["r2_log"],
        "internal_severe_r2_log": split_metrics["internal_severe"]["r2_log"],
        "train_same_stage_spearman_median": ranking_summaries["train"]["median_same_stage_spearman"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
