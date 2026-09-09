"""Static user-equilibrium traffic assignment for TNTP-style networks.

Implements deterministic all-or-nothing loading and Frank-Wolfe/MSA solution of
Beckmann's user-equilibrium problem with separable BPR link costs.

The implementation is intentionally compact and dependency-light for repeated
Sioux Falls flood/recovery simulations. AequilibraE is recommended as an
independent validation implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import heapq
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import brentq


class DisconnectedOD(RuntimeError):
    """Raised when positive OD demand has no active path."""


@dataclass
class AssignmentResult:
    flows: np.ndarray
    costs: np.ndarray
    tstt: float
    sptt: float
    relative_gap: float
    iterations: int
    converged: bool
    beckmann_objective: float
    history: pd.DataFrame


class StaticUESolver:
    """Static deterministic UE solver for one vehicle class."""

    REQUIRED_LINK_COLUMNS = {
        "arc_id", "from_node", "to_node", "capacity", "free_flow_time",
        "bpr_alpha", "bpr_beta",
    }

    def __init__(
        self,
        links: pd.DataFrame,
        od: pd.DataFrame,
        *,
        active: np.ndarray | None = None,
        effective_capacity: np.ndarray | None = None,
        effective_free_flow_time: np.ndarray | None = None,
    ) -> None:
        missing = self.REQUIRED_LINK_COLUMNS.difference(links.columns)
        if missing:
            raise ValueError(f"Missing link columns: {sorted(missing)}")
        for col in ("origin", "destination", "demand"):
            if col not in od.columns:
                raise ValueError(f"Missing OD column: {col}")

        self.links = links.reset_index(drop=True).copy()
        self.od = od.loc[od["demand"] > 0, ["origin", "destination", "demand"]].copy()

        self.tail = self.links["from_node"].to_numpy(dtype=int)
        self.head = self.links["to_node"].to_numpy(dtype=int)
        self.arc_id = self.links["arc_id"].to_numpy(dtype=int)
        self.capacity = (
            self.links["capacity"].to_numpy(dtype=float)
            if effective_capacity is None else np.asarray(effective_capacity, dtype=float)
        )
        self.fft = (
            self.links["free_flow_time"].to_numpy(dtype=float)
            if effective_free_flow_time is None else np.asarray(effective_free_flow_time, dtype=float)
        )
        self.alpha = self.links["bpr_alpha"].to_numpy(dtype=float)
        self.beta = self.links["bpr_beta"].to_numpy(dtype=float)
        self.active = (
            np.ones(len(self.links), dtype=bool)
            if active is None else np.asarray(active, dtype=bool)
        )

        n = len(self.links)
        if not all(len(x) == n for x in (self.capacity, self.fft, self.alpha, self.beta, self.active)):
            raise ValueError("All link arrays must have the same length")
        if np.any(self.capacity[self.active] <= 0):
            raise ValueError("Active links must have positive capacity")
        if np.any(self.fft[self.active] <= 0):
            raise ValueError("Active links must have positive free-flow time")

        self.nodes = np.unique(np.concatenate([self.tail, self.head]))
        self.node_to_pos = {int(nid): i for i, nid in enumerate(self.nodes)}
        self.pos_to_node = self.nodes.copy()
        self.adj: list[list[tuple[int, int]]] = [[] for _ in self.nodes]
        for e, (u, v, is_active) in enumerate(zip(self.tail, self.head, self.active)):
            if is_active:
                self.adj[self.node_to_pos[int(u)]].append((self.node_to_pos[int(v)], e))

        grouped: dict[int, list[tuple[int, float]]] = {}
        for row in self.od.itertuples(index=False):
            grouped.setdefault(int(row.origin), []).append((int(row.destination), float(row.demand)))
        self.od_by_origin = grouped

    @classmethod
    def from_csv(cls, links_csv: str | Path, od_csv: str | Path) -> "StaticUESolver":
        return cls(pd.read_csv(links_csv), pd.read_csv(od_csv))

    def bpr_cost(self, flows: np.ndarray) -> np.ndarray:
        flows = np.asarray(flows, dtype=float)
        costs = np.full(len(self.links), np.inf, dtype=float)
        ratio = np.zeros_like(flows)
        ratio[self.active] = flows[self.active] / self.capacity[self.active]
        costs[self.active] = self.fft[self.active] * (
            1.0 + self.alpha[self.active] * np.power(ratio[self.active], self.beta[self.active])
        )
        return costs

    def beckmann_objective(self, flows: np.ndarray) -> float:
        x = np.asarray(flows, dtype=float)
        idx = self.active
        return float(np.sum(
            self.fft[idx] * (
                x[idx]
                + self.alpha[idx] * np.power(x[idx], self.beta[idx] + 1)
                / ((self.beta[idx] + 1) * np.power(self.capacity[idx], self.beta[idx]))
            )
        ))

    def _dijkstra(self, origin: int, costs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if origin not in self.node_to_pos:
            raise DisconnectedOD(f"Origin {origin} is not in the active network")
        n = len(self.nodes)
        dist = np.full(n, np.inf, dtype=float)
        pred_edge = np.full(n, -1, dtype=int)
        o = self.node_to_pos[origin]
        dist[o] = 0.0
        heap: list[tuple[float, int]] = [(0.0, o)]
        while heap:
            du, u = heapq.heappop(heap)
            if du != dist[u]:
                continue
            for v, e in self.adj[u]:
                nd = du + costs[e]
                if nd < dist[v] - 1e-12:
                    dist[v] = nd
                    pred_edge[v] = e
                    heapq.heappush(heap, (nd, v))
        return dist, pred_edge

    def all_or_nothing(self, costs: np.ndarray) -> tuple[np.ndarray, float]:
        y = np.zeros(len(self.links), dtype=float)
        sptt = 0.0
        unreachable: list[tuple[int, int, float]] = []

        for origin, destinations in self.od_by_origin.items():
            dist, pred = self._dijkstra(origin, costs)
            for destination, demand in destinations:
                if destination == origin or demand <= 0:
                    continue
                if destination not in self.node_to_pos:
                    unreachable.append((origin, destination, demand))
                    continue
                dpos = self.node_to_pos[destination]
                if not np.isfinite(dist[dpos]):
                    unreachable.append((origin, destination, demand))
                    continue
                sptt += demand * dist[dpos]
                cur = dpos
                opos = self.node_to_pos[origin]
                while cur != opos:
                    e = pred[cur]
                    if e < 0:
                        unreachable.append((origin, destination, demand))
                        break
                    y[e] += demand
                    cur = self.node_to_pos[int(self.tail[e])]

        if unreachable:
            total = sum(x[2] for x in unreachable)
            sample = ", ".join(f"{o}->{d}" for o, d, _ in unreachable[:5])
            raise DisconnectedOD(
                f"{len(unreachable)} positive OD pairs are unreachable "
                f"(total demand={total:.3f}); examples: {sample}"
            )
        return y, float(sptt)

    def _fw_step(self, x: np.ndarray, y: np.ndarray) -> float:
        d = y - x
        if np.max(np.abs(d)) < 1e-14:
            return 0.0

        def derivative(lam: float) -> float:
            return float(np.dot(d[self.active], self.bpr_cost(x + lam * d)[self.active]))

        g0 = derivative(0.0)
        g1 = derivative(1.0)
        if g0 >= -1e-11:
            return 0.0
        if g1 <= 1e-11:
            return 1.0
        return float(brentq(derivative, 0.0, 1.0, xtol=1e-12, rtol=1e-12, maxiter=100))

    def solve(
        self,
        *,
        method: str = "fw",
        relative_gap: float = 1e-6,
        max_iter: int = 500,
        verbose: bool = False,
    ) -> AssignmentResult:
        method = method.lower()
        if method not in {"fw", "msa"}:
            raise ValueError("method must be 'fw' or 'msa'")

        # Feasible initial flow from free-flow all-or-nothing loading.
        x, _ = self.all_or_nothing(self.bpr_cost(np.zeros(len(self.links))))
        records: list[dict[str, float | int]] = []
        converged = False
        final_sptt = np.nan
        final_gap = np.inf

        for iteration in range(1, max_iter + 1):
            costs = self.bpr_cost(x)
            y, sptt = self.all_or_nothing(costs)
            tstt = float(np.dot(x[self.active], costs[self.active]))
            gap = 0.0 if tstt <= 0 else max((tstt - sptt) / tstt, 0.0)
            final_sptt, final_gap = sptt, gap

            if gap <= relative_gap:
                records.append({
                    "iteration": iteration,
                    "relative_gap": gap,
                    "step_size": 0.0,
                    "tstt": tstt,
                    "sptt": sptt,
                    "beckmann_objective": self.beckmann_objective(x),
                })
                converged = True
                break

            step = self._fw_step(x, y) if method == "fw" else 1.0 / (iteration + 1.0)
            records.append({
                "iteration": iteration,
                "relative_gap": gap,
                "step_size": step,
                "tstt": tstt,
                "sptt": sptt,
                "beckmann_objective": self.beckmann_objective(x),
            })
            x = x + step * (y - x)
            x[np.abs(x) < 1e-10] = 0.0

            if verbose and (iteration == 1 or iteration % 25 == 0):
                print(f"iter={iteration:4d} gap={gap:.3e} step={step:.4g} TSTT={tstt:.6f}")

        costs = self.bpr_cost(x)
        y, final_sptt = self.all_or_nothing(costs)
        tstt = float(np.dot(x[self.active], costs[self.active]))
        final_gap = 0.0 if tstt <= 0 else max((tstt - final_sptt) / tstt, 0.0)
        history = pd.DataFrame.from_records(records)
        return AssignmentResult(
            flows=x,
            costs=costs,
            tstt=tstt,
            sptt=final_sptt,
            relative_gap=final_gap,
            iterations=len(records),
            converged=bool(final_gap <= relative_gap),
            beckmann_objective=self.beckmann_objective(x),
            history=history,
        )

    def result_frame(self, result: AssignmentResult) -> pd.DataFrame:
        out = self.links.copy()
        out["ue_flow"] = result.flows
        out["ue_cost"] = result.costs
        out["active"] = self.active.astype(int)
        out["effective_capacity"] = self.capacity
        out["effective_free_flow_time"] = self.fft
        return out
