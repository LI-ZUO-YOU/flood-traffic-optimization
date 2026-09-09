from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


N_PHYSICAL_LINKS = 38
BASELINE_TSTT = 7480225.3449211195
TARGET_RELATIVE_GAP = 5e-4
MAX_UE_ITERATIONS = 1000


def _torch_import(dependency_paths: Sequence[str | Path] | None = None):
    for dependency in dependency_paths or ():
        dependency_path = Path(dependency)
        if str(dependency_path) not in sys.path:
            sys.path.insert(0, str(dependency_path))
    import torch
    from torch import nn
    return torch, nn


def _as_vector(values, dtype, name: str) -> np.ndarray:
    vector = np.asarray(values, dtype=dtype).reshape(-1)
    if len(vector) != N_PHYSICAL_LINKS:
        raise ValueError(f"{name} must contain {N_PHYSICAL_LINKS} values; got {len(vector)}")
    return vector


def _validated_link_ids(values: Iterable[int], name: str) -> tuple[int, ...]:
    validated = []
    for value in values:
        if isinstance(value, (bool, np.bool_)):
            raise ValueError(f"{name} must contain integer physical_link_id values")
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must contain integer physical_link_id values") from exc
        if not np.isfinite(numeric) or not numeric.is_integer():
            raise ValueError(f"{name} must contain integer physical_link_id values")
        link_id = int(numeric)
        if link_id < 1 or link_id > N_PHYSICAL_LINKS:
            raise ValueError("physical_link_id must be between 1 and 38")
        validated.append(link_id)
    return tuple(validated)


def get_state_hash(depth_m, initial_closed, restored) -> str:
    """Canonical hash compatible with the frozen week-1/V2 state convention."""
    depth = _as_vector(depth_m, np.float64, "depth_m")
    closed_raw = _as_vector(initial_closed, np.float64, "initial_closed")
    restored_raw = _as_vector(restored, np.float64, "restored")
    if not np.isin(closed_raw, [0, 1]).all():
        raise ValueError("initial_closed must be binary")
    if not np.isin(restored_raw, [0, 1]).all():
        raise ValueError("restored must be binary")
    closed = closed_raw.astype(np.uint8)
    restored_mask = restored_raw.astype(np.uint8)
    if np.any(restored_mask > closed):
        raise ValueError("A restored road must belong to the initially closed set")
    payload = np.concatenate([np.round(depth, 9), restored_mask.astype(np.float64)])
    return hashlib.sha256(payload.tobytes()).hexdigest()


def restored_mask_from_links(restored_links: Iterable[int]) -> np.ndarray:
    mask = np.zeros(N_PHYSICAL_LINKS, dtype=np.uint8)
    for link_id in _validated_link_ids(restored_links, "restored_links"):
        mask[link_id - 1] = 1
    return mask


class RecoveryMLPV2:
    @staticmethod
    def build(dependency_paths: Sequence[str | Path] | None = None):
        torch, nn = _torch_import(dependency_paths)

        class Network(nn.Module):
            def __init__(self):
                super().__init__()
                self.network = nn.Sequential(
                    nn.Linear(120, 128), nn.ReLU(),
                    nn.Linear(128, 64), nn.ReLU(),
                    nn.Linear(64, 32), nn.ReLU(),
                    nn.Linear(32, 1),
                )

            def forward(self, X):
                return self.network(X).squeeze(-1)

        return Network()


class SurrogateV2:
    """Read-only V2 surrogate interface for candidate generation and screening."""

    def __init__(
        self,
        surrogate_dir: str | Path,
        dependency_paths: Sequence[str | Path] | None = None,
    ):
        self.surrogate_dir = Path(surrogate_dir)
        self.dependency_paths = list(dependency_paths or ())
        self.preprocessor = json.loads((self.surrogate_dir / "preprocessor_v2.json").read_text(encoding="utf-8"))
        self.depth_mean = np.asarray(self.preprocessor["depth_mean"], dtype=np.float64)
        self.depth_std = np.asarray(self.preprocessor["depth_std"], dtype=np.float64)
        self.aggregate_mean = np.asarray(self.preprocessor["aggregate_mean"], dtype=np.float64)
        self.aggregate_std = np.asarray(self.preprocessor["aggregate_std"], dtype=np.float64)
        self.baseline_flow = np.asarray(self.preprocessor["baseline_flow"], dtype=np.float64)
        self.betweenness = np.asarray(self.preprocessor["betweenness"], dtype=np.float64)
        torch, _ = _torch_import(self.dependency_paths)
        self.torch = torch
        self.models = []
        for model_path in sorted((self.surrogate_dir / "models").glob("member_*.pt")):
            checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
            model = RecoveryMLPV2.build(self.dependency_paths)
            model.load_state_dict(checkpoint["state_dict"])
            model.eval()
            self.models.append(model)
        if len(self.models) != 10:
            raise ValueError(f"Expected 10 V2 members; loaded {len(self.models)}")

    def transform(self, states: Sequence[dict]) -> np.ndarray:
        rows = []
        for state in states:
            depth = _as_vector(state["depth_m"], np.float64, "depth_m")
            closed = _as_vector(state["initial_closed"], np.float64, "initial_closed")
            restored = _as_vector(state["restored"], np.float64, "restored")
            if not np.isin(closed, [0, 1]).all():
                raise ValueError("initial_closed must be binary")
            if not np.isin(restored, [0, 1]).all():
                raise ValueError("restored must be binary")
            if np.any(restored > closed):
                raise ValueError("restored mask is not a subset of initial_closed")
            depth_z = (depth - self.depth_mean) / self.depth_std
            link_features = np.stack([depth_z, closed, restored], axis=1).reshape(-1)
            # Frozen-V2 compatibility: the last two aggregates used initial_closed directly.
            # Do not change this without retraining all ten checkpoints.
            aggregates = np.asarray([
                closed.sum(),
                restored.sum(),
                depth.sum(),
                (depth * np.maximum(closed, restored)).sum(),
                closed @ self.baseline_flow,
                closed @ self.betweenness,
            ], dtype=np.float64)
            aggregate_z = (aggregates - self.aggregate_mean) / self.aggregate_std
            rows.append(np.concatenate([link_features, aggregate_z]))
        X = np.asarray(rows, dtype=np.float32)
        if X.shape != (len(states), 120) or not np.isfinite(X).all():
            raise ValueError(f"Invalid surrogate input matrix: {X.shape}")
        return X

    def predict_members(self, states: Sequence[dict]) -> np.ndarray:
        X = self.transform(states)
        tensor = self.torch.from_numpy(X)
        with self.torch.no_grad():
            prediction = np.column_stack([model(tensor).numpy() for model in self.models])
        return prediction.astype(np.float64)

    def predict_mean(self, states: Sequence[dict]) -> np.ndarray:
        return self.predict_members(states).mean(axis=1)

    def evaluate_proxy_sequence(self, sequence: Sequence[int], depth_m, initial_closed) -> dict:
        sequence = _validated_link_ids(sequence, "sequence")
        if len(sequence) != 10 or len(set(sequence)) != 10:
            raise ValueError("A recovery sequence must contain ten distinct physical links")
        closed_raw = _as_vector(initial_closed, np.float64, "initial_closed")
        if not np.isin(closed_raw, [0, 1]).all():
            raise ValueError("initial_closed must be binary")
        closed = closed_raw.astype(np.uint8)
        if any(closed[link_id - 1] != 1 for link_id in sequence):
            raise ValueError("Every sequenced road must be initially closed")
        states = []
        restored = np.zeros(N_PHYSICAL_LINKS, dtype=np.uint8)
        for stage in range(11):
            if stage > 0:
                restored[sequence[stage - 1] - 1] = 1
            states.append({"depth_m": depth_m, "initial_closed": closed, "restored": restored.copy()})
        member_y = self.predict_members(states)
        member_stage_loss = np.exp(member_y) - 1.0
        member_objective = member_stage_loss.mean(axis=0)
        return {
            "sequence": list(sequence),
            "stage_count": 11,
            "member_objectives": member_objective.tolist(),
            "proxy_objective_mean": float(member_objective.mean()),
            "ensemble_disagreement": float(member_objective.std(ddof=1)),
            "stage_mean_log_prediction": member_y.mean(axis=1).tolist(),
        }


@dataclass
class UEResult:
    state_hash: str
    tstt: float
    normalized_tstt: float
    loss: float
    relative_gap: float
    iterations: int
    converged: bool
    elapsed_seconds: float
    cache_hit: bool


class UECache:
    def __init__(self, sqlite_path: str | Path, namespace: str = "week3_v1"):
        self.sqlite_path = Path(sqlite_path)
        self.namespace = str(namespace)
        self.connection = sqlite3.connect(self.sqlite_path)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS cache_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        existing = self.connection.execute(
            "SELECT value FROM cache_metadata WHERE key='namespace'"
        ).fetchone()
        if existing is not None and existing[0] != self.namespace:
            self.connection.close()
            raise RuntimeError(
                f"Cache namespace mismatch: database={existing[0]!r}, requested={self.namespace!r}"
            )
        self.connection.execute(
            "INSERT OR IGNORE INTO cache_metadata(key,value) VALUES('namespace',?)", (self.namespace,)
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ue_states (
                state_hash TEXT PRIMARY KEY,
                scenario_key TEXT NOT NULL,
                restored_links TEXT NOT NULL,
                tstt REAL NOT NULL,
                normalized_tstt REAL NOT NULL,
                loss REAL NOT NULL,
                relative_gap REAL NOT NULL,
                iterations INTEGER NOT NULL,
                converged INTEGER NOT NULL,
                elapsed_seconds REAL NOT NULL,
                created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.commit()

    def get(self, state_hash: str) -> UEResult | None:
        row = self.connection.execute(
            "SELECT state_hash,tstt,normalized_tstt,loss,relative_gap,iterations,converged,elapsed_seconds "
            "FROM ue_states WHERE state_hash=?", (state_hash,),
        ).fetchone()
        if row is None:
            return None
        return UEResult(*row[:6], bool(row[6]), row[7], True)

    def put(self, result: UEResult, scenario_key: str, restored_links: Sequence[int]) -> None:
        self.connection.execute(
            "INSERT INTO ue_states(state_hash,scenario_key,restored_links,tstt,normalized_tstt,loss,relative_gap,iterations,converged,elapsed_seconds) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                result.state_hash, str(scenario_key), ";".join(map(str, sorted(restored_links))), result.tstt,
                result.normalized_tstt, result.loss, result.relative_gap, result.iterations,
                int(result.converged), result.elapsed_seconds,
            ),
        )
        self.connection.commit()

    def count(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM ue_states").fetchone()[0])

    def close(self) -> None:
        self.connection.close()


class UEInterface:
    """High-fidelity static-UE evaluator with a unique-state SQLite cache."""

    def __init__(
        self,
        cache_path: str | Path,
        model_root: str | Path,
        dependency_paths: Sequence[str | Path] | None = None,
        cache_namespace: str = "week3_v1",
    ):
        for dependency in dependency_paths or ():
            dependency_path = Path(dependency)
            if str(dependency_path) not in sys.path:
                sys.path.insert(0, str(dependency_path))
        model_root = Path(model_root)
        if str(model_root) not in sys.path:
            sys.path.insert(0, str(model_root))
        from models import build_flooded_solver

        self.build_flooded_solver = build_flooded_solver
        data_root = model_root / "data_src/SiouxFalls_flood_benchmark/processed"
        self.links = pd.read_csv(data_root / "directed_links.csv")
        self.od = pd.read_csv(data_root / "od_long.csv")
        self.arc_map = self.links[["arc_id", "from_node", "to_node", "physical_link_id"]].copy()
        self.cache = UECache(cache_path, namespace=cache_namespace)

    @staticmethod
    def _validate_scenario_physical(scenario: pd.DataFrame, restored_links: Sequence[int]) -> pd.DataFrame:
        scenario = scenario.copy()
        required = {
            "physical_link_id", "depth_m", "is_wet", "is_closed", "speed_ratio",
            "free_flow_time_multiplier", "capacity_factor",
        }
        missing = required - set(scenario.columns)
        if missing:
            raise ValueError(f"Scenario physical table is missing: {sorted(missing)}")
        if len(scenario) != N_PHYSICAL_LINKS:
            raise ValueError(f"Scenario physical table must contain exactly 38 rows; got {len(scenario)}")
        physical_ids_raw = scenario["physical_link_id"].to_numpy(dtype=float)
        if not np.isfinite(physical_ids_raw).all() or not np.equal(physical_ids_raw, np.floor(physical_ids_raw)).all():
            raise ValueError("physical_link_id values must be finite integers")
        if scenario["physical_link_id"].duplicated().any():
            raise ValueError("physical_link_id must be unique")
        actual_ids = set(physical_ids_raw.astype(int))
        expected_ids = set(range(1, N_PHYSICAL_LINKS + 1))
        if actual_ids != expected_ids:
            raise ValueError("physical_link_id set must be exactly 1..38")
        for column in ["is_closed", "is_wet"]:
            if not np.isin(scenario[column].to_numpy(), [0, 1]).all():
                raise ValueError(f"{column} must be binary")
        closed_mask = scenario["is_closed"].to_numpy(dtype=int) == 1
        open_mask = ~closed_mask
        for column in ["capacity_factor", "free_flow_time_multiplier", "speed_ratio"]:
            values = scenario[column].to_numpy(dtype=float)
            if not np.isfinite(values[open_mask]).all() or np.any(values[open_mask] <= 0):
                raise ValueError(f"{column} must be finite and strictly positive for open roads")
        capacity = scenario["capacity_factor"].to_numpy(dtype=float)
        time_multiplier = scenario["free_flow_time_multiplier"].to_numpy(dtype=float)
        speed_ratio = scenario["speed_ratio"].to_numpy(dtype=float)
        if not (
            np.all(capacity[closed_mask] == 0)
            and np.all(np.isposinf(time_multiplier[closed_mask]))
            and np.all(speed_ratio[closed_mask] == 0)
        ):
            raise ValueError(
                "Closed roads must use frozen sentinels: capacity_factor=0, "
                "free_flow_time_multiplier=+Inf, speed_ratio=0"
            )
        depth = scenario["depth_m"].to_numpy(dtype=float)
        if not np.isfinite(depth).all() or np.any(depth < 0):
            raise ValueError("depth_m must be finite and nonnegative")
        restored = list(_validated_link_ids(restored_links, "restored_links"))
        if len(restored) != len(set(restored)):
            raise ValueError("restored_links must not contain duplicates")
        if any(value < 1 or value > N_PHYSICAL_LINKS for value in restored):
            raise ValueError("restored physical_link_id must be between 1 and 38")
        initially_closed = set(
            scenario.loc[scenario["is_closed"].astype(int) == 1, "physical_link_id"].astype(int)
        )
        if not set(restored).issubset(initially_closed):
            raise ValueError("Every restored road must be initially closed")
        return scenario.sort_values("physical_link_id").reset_index(drop=True)

    def run_ue(self, scenario_physical: pd.DataFrame, restored_links: Sequence[int], scenario_key: str) -> UEResult:
        scenario = self._validate_scenario_physical(scenario_physical, restored_links)
        depth = scenario["depth_m"].to_numpy(float)
        initial_closed = scenario["is_closed"].to_numpy(np.uint8)
        restored = restored_mask_from_links(restored_links)
        state_key = get_state_hash(depth, initial_closed, restored)
        cached = self.cache.get(state_key)
        if cached is not None:
            return cached

        restored_set = set(int(v) for v in restored_links)
        mask = scenario["physical_link_id"].isin(restored_set)
        scenario.loc[mask, ["depth_m", "is_wet", "is_closed"]] = [0.0, 0, 0]
        scenario.loc[mask, ["speed_ratio", "free_flow_time_multiplier", "capacity_factor"]] = [1.0, 1.0, 1.0]
        scenario_arcs = self.arc_map.merge(
            scenario[["physical_link_id", "is_closed", "free_flow_time_multiplier", "capacity_factor"]],
            on="physical_link_id", how="left", validate="many_to_one",
        )
        solver = self.build_flooded_solver(self.links, self.od, scenario_arcs)
        started = time.perf_counter()
        assignment = solver.solve(method="fw", relative_gap=TARGET_RELATIVE_GAP, max_iter=MAX_UE_ITERATIONS)
        if not assignment.converged:
            assignment = solver.solve(method="fw", relative_gap=TARGET_RELATIVE_GAP, max_iter=3000)
        elapsed = time.perf_counter() - started
        tolerance = 1e-12
        if (
            not assignment.converged
            or not np.isfinite(assignment.tstt)
            or not np.isfinite(assignment.relative_gap)
            or assignment.relative_gap > TARGET_RELATIVE_GAP + tolerance
        ):
            raise RuntimeError("UE failed to converge; result was not cached")
        result = UEResult(
            state_hash=state_key,
            tstt=float(assignment.tstt),
            normalized_tstt=float(assignment.tstt / BASELINE_TSTT),
            loss=float(assignment.tstt / BASELINE_TSTT - 1.0),
            relative_gap=float(assignment.relative_gap),
            iterations=int(assignment.iterations),
            converged=bool(assignment.converged),
            elapsed_seconds=elapsed,
            cache_hit=False,
        )
        self.cache.put(result, scenario_key, restored_links)
        return result

    def evaluate_ue_sequence(
        self,
        sequence: Sequence[int],
        scenario_physical: pd.DataFrame,
        scenario_key: str,
        remaining_new_state_budget: int | None = None,
    ) -> dict:
        sequence = _validated_link_ids(sequence, "sequence")
        if len(sequence) != 10 or len(set(sequence)) != 10:
            raise ValueError("A recovery sequence must contain ten distinct roads")
        scenario_physical = self._validate_scenario_physical(scenario_physical, sequence)
        before = self.cache.count()
        stage_results = []
        restored_links: list[int] = []
        for stage in range(11):
            if stage > 0:
                restored_links.append(sequence[stage - 1])
            scenario = scenario_physical.sort_values("physical_link_id")
            key = get_state_hash(
                scenario["depth_m"].to_numpy(float),
                scenario["is_closed"].to_numpy(np.uint8),
                restored_mask_from_links(restored_links),
            )
            is_new = self.cache.get(key) is None
            used = self.cache.count() - before
            if is_new and remaining_new_state_budget is not None and used >= remaining_new_state_budget:
                return {"complete": False, "stopped_before_stage": stage, "new_ue_calls": used}
            result = self.run_ue(scenario_physical, restored_links, scenario_key)
            stage_results.append({"stage": stage, "restored_links": restored_links.copy(), **result.__dict__})
        new_calls = self.cache.count() - before
        return {
            "complete": True,
            "sequence": list(sequence),
            "stage_count": 11,
            "ue_objective": float(np.mean([row["loss"] for row in stage_results])),
            "new_ue_calls": int(new_calls),
            "cache_hits": int(11 - new_calls),
            "stages": stage_results,
        }
