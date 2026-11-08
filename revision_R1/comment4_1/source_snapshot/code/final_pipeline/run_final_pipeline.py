from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str]) -> None:
    print(json.dumps({"event": "launch", "command": command}, ensure_ascii=False), flush=True)
    subprocess.run(command, check=True)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen end-to-end final optimization pipeline; final scenarios must already be frozen.")
    parser.add_argument("--scenario-physical", required=True)
    parser.add_argument("--scenario-freeze", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-hash-file", required=True)
    parser.add_argument("--surrogate-root", required=True)
    parser.add_argument("--surrogate-preprocessor", required=True)
    parser.add_argument(
        "--python-dependency",
        action="append",
        default=[],
        help="Additional import root required by the frozen surrogate (repeatable).",
    )
    parser.add_argument("--interface", required=True)
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scenario-count", required=True, type=int)
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--warm-cache-template", help="Old-scenario cache used only for an explicitly labelled smoke test.")
    args = parser.parse_args()
    if args.warm_cache_template and not args.smoke_test:
        raise ValueError("A warm cache is permitted only with --smoke-test")

    output = Path(args.output_dir)
    if output.exists():
        raise FileExistsError(output)
    protocol_path = Path(args.protocol)
    protocol_hash_path = Path(args.protocol_hash_file)
    recorded_hash = protocol_hash_path.read_text(encoding="utf-8").strip().split()[0]
    if sha256(protocol_path) != recorded_hash:
        raise RuntimeError("Protocol hash mismatch")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if not args.smoke_test and int(protocol["final_scenario_generation"]["formal_final_scenario_count"]) != args.scenario_count:
        raise ValueError("Final scenario count differs from the frozen protocol")
    scenario_freeze = json.loads(Path(args.scenario_freeze).read_text(encoding="utf-8"))
    if len(scenario_freeze["scenario_ids"]) != args.scenario_count:
        raise ValueError("Scenario generation freeze count differs from --scenario-count")
    scenario_ids = list(map(int, scenario_freeze["scenario_ids"]))
    output.mkdir(parents=True)
    code_root = Path(__file__).resolve().parent
    started = time.perf_counter()
    python = sys.executable

    selection_dir = output / "01_road_selection"
    run([python, str(code_root / "select_final_recoverable_roads.py"),
         "--scenario-physical", args.scenario_physical,
         "--scenario-freeze", args.scenario_freeze,
         "--surrogate-preprocessor", args.surrogate_preprocessor,
         "--protocol", args.protocol,
         "--output-dir", str(selection_dir),
         "--scenario-count", str(args.scenario_count)])

    candidate_dir = output / "02_candidate_pool"
    candidate_command = [python, str(code_root / "generate_candidate_pool.py"),
         "--scenario-metadata", str(selection_dir / "final_scenarios.json"),
         "--scenario-physical", args.scenario_physical,
         "--surrogate-root", args.surrogate_root,
         "--interface", args.interface,
         "--output-dir", str(candidate_dir),
         "--scenario-count", str(args.scenario_count),
         "--seed-base", str(int(protocol["candidate_pool"]["candidate_seed_rule"].split("+")[0].strip()))]
    for dependency in args.python_dependency:
        candidate_command.extend(["--python-dependency", dependency])
    run(candidate_command)

    primary_dir = output / "03_primary_screening"
    run([python, str(code_root / "screen_primary.py"),
         "--input-candidate-pool", str(candidate_dir / "candidate_pool.csv.gz"),
         "--candidate-freeze", str(candidate_dir / "generation_freeze_record.json"),
         "--scenario-metadata", str(selection_dir / "final_scenarios.json"),
         "--candidate-road-audit", str(selection_dir / "candidate_road_selection_audit.csv"),
         "--output-dir", str(primary_dir),
         "--scenario-count", str(args.scenario_count),
         "--seed-base", str(int(protocol["screening"]["screening_seed_rule"].split("+")[0].strip()))])

    structural_dir = output / "04_structural_screening"
    run([python, str(code_root / "screen_structural_reserve.py"),
         "--input-candidate-pool", str(candidate_dir / "candidate_pool.csv.gz"),
         "--candidate-freeze", str(candidate_dir / "generation_freeze_record.json"),
         "--primary-shortlist", str(primary_dir / "screened_candidates.csv"),
         "--output-dir", str(structural_dir),
         "--scenario-count", str(args.scenario_count)])

    cache_dir = output / "05_shared_physical_cache"
    cache_dir.mkdir()
    full_root = output / "06_full_method"
    controls_root = output / "07_live_controls"
    full_freezes = []
    control_freezes = []
    for sid in scenario_ids:
        cache_path = cache_dir / f"scenario_{sid}.sqlite"
        namespace = f"final_live_ue_s{sid}"
        if args.warm_cache_template:
            with sqlite3.connect(args.warm_cache_template) as source:
                source_tables = {row[0] for row in source.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if "subset_costs" in source_tables:
                    source_rows = source.execute(
                        "SELECT state_hash,scenario_id,restored_links,tstt,normalized_tstt,loss,"
                        "relative_gap,iterations,converged,elapsed_seconds FROM subset_costs").fetchall()
                elif "ue_states" in source_tables:
                    source_rows = source.execute(
                        "SELECT state_hash,scenario_key,restored_links,tstt,normalized_tstt,loss,"
                        "relative_gap,iterations,converged,elapsed_seconds FROM ue_states").fetchall()
                else:
                    raise RuntimeError("Warm-cache template has neither subset_costs nor ue_states")
            with sqlite3.connect(cache_path) as connection:
                connection.execute("CREATE TABLE cache_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                connection.execute("INSERT INTO cache_metadata(key,value) VALUES('namespace',?)", (namespace,))
                connection.execute("""CREATE TABLE ue_states (
                    state_hash TEXT PRIMARY KEY, scenario_key TEXT NOT NULL, restored_links TEXT NOT NULL,
                    tstt REAL NOT NULL, normalized_tstt REAL NOT NULL, loss REAL NOT NULL,
                    relative_gap REAL NOT NULL, iterations INTEGER NOT NULL, converged INTEGER NOT NULL,
                    elapsed_seconds REAL NOT NULL, created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
                connection.executemany(
                    "INSERT OR IGNORE INTO ue_states(state_hash,scenario_key,restored_links,tstt,normalized_tstt,loss,"
                    "relative_gap,iterations,converged,elapsed_seconds) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    source_rows,
                )
                warm_rows = int(connection.execute("SELECT COUNT(*) FROM ue_states").fetchone()[0])
            if warm_rows < 1024:
                raise RuntimeError(f"Warm-cache smoke requires at least 1024 verified states; found {warm_rows}")
        full_command = [python, str(code_root / "run_full_method_live_ue.py"),
             "--scenario", str(sid),
             "--output-dir", str(full_root),
             "--screened-candidates", str(structural_dir / "screened_candidates.csv"),
             "--scenario-physical", args.scenario_physical,
             "--scenario-metadata", str(selection_dir / "final_scenarios.json"),
             "--interface", args.interface,
             "--model-root", args.model_root,
             "--cache-path", str(cache_path),
             "--cache-namespace", namespace,
             "--max-budget", "512"]
        if args.warm_cache_template:
            full_command.append("--allow-prewarmed-cache")
        for dependency in args.python_dependency:
            full_command.extend(["--python-dependency", dependency])
        run(full_command)
        full_scenario_dir = full_root / f"scenario_{sid}"
        full_artifacts = [
            "budget_snapshots_pre_reference.csv",
            "ue_reranking_results.csv",
            "local_search_history.csv",
            "ue_state_audit_log.csv.gz",
            "budget_usage_pre_reference.json",
        ]
        full_freeze = {
            "schema_version": "final-full-method-output-freeze-v1.0",
            "scenario_id": sid,
            "method": "full_method",
            "method_output_frozen_before_exact_reference": True,
            "files": {name: sha256(full_scenario_dir / name) for name in full_artifacts},
            "screened_candidates_sha256": sha256(structural_dir / "screened_candidates.csv"),
            "scenario_physical_sha256": sha256(Path(args.scenario_physical)),
            "scenario_metadata_sha256": sha256(selection_dir / "final_scenarios.json"),
            "exact_reference_read": False,
        }
        full_freeze_path = full_scenario_dir / "full_method_output_freeze.json"
        write_json(full_freeze_path, full_freeze)
        full_freezes.append(full_freeze_path)

        control_command = [python, str(code_root / "run_final_controls_live_ue.py"),
             "--scenario", str(sid),
             "--candidate-pool", str(candidate_dir / "candidate_pool.csv.gz"),
             "--screened-candidates", str(structural_dir / "screened_candidates.csv"),
             "--scenario-physical", args.scenario_physical,
             "--scenario-metadata", str(selection_dir / "final_scenarios.json"),
             "--interface", args.interface,
             "--model-root", args.model_root,
             "--shared-cache", str(cache_path),
             "--cache-namespace", namespace,
             "--reference-logic", str(code_root / "run_controls_reference.py"),
             "--output-dir", str(controls_root),
             "--random-seed-base", "2026080704"]
        for dependency in args.python_dependency:
            control_command.extend(["--python-dependency", dependency])
        run(control_command)
        control_freezes.append(controls_root / f"scenario_{sid}" / "controls_output_freeze.json")

    exact_dir = output / "08_exact_reference_after_method_freeze"
    exact_command = [python, str(code_root / "run_exact_reference_after_method_freeze.py"),
                     "--scenario-physical", args.scenario_physical,
                     "--scenario-metadata", str(selection_dir / "final_scenarios.json"),
                     "--output-dir", str(exact_dir),
                     "--model-root", args.model_root,
                     "--interface", args.interface,
                     "--cache-dir", str(cache_dir),
                     "--cache-namespace", "final_live_ue"]
    for path in [*full_freezes, *control_freezes]:
        exact_command.extend(["--method-output-freeze", str(path)])
    for dependency in args.python_dependency:
        exact_command.extend(["--python-dependency", dependency])
    run(exact_command)

    freeze = {
        "schema_version": "final-pipeline-output-freeze-v1.0",
        "status": "pass",
        "smoke_test": bool(args.smoke_test),
        "scenario_ids": scenario_ids,
        "execution_order": [
            "road selection",
            "candidate generation",
            "primary and structural screening",
            "full method live UE",
            "five controls live UE",
            "method-output hash freeze",
            "1024-state exact reference",
            "dynamic programming and regret-ready outputs",
        ],
        "information_firewall_respected": True,
        "warm_cache_smoke_only": bool(args.warm_cache_template),
        "warm_cache_template_sha256": sha256(Path(args.warm_cache_template)) if args.warm_cache_template else None,
        "protocol_sha256": sha256(protocol_path),
        "scenario_physical_sha256": sha256(Path(args.scenario_physical)),
        "scenario_freeze_sha256": sha256(Path(args.scenario_freeze)),
        "road_selection_freeze_sha256": sha256(selection_dir / "candidate_road_selection_freeze.json"),
        "candidate_freeze_sha256": sha256(candidate_dir / "generation_freeze_record.json"),
        "screening_freeze_sha256": sha256(structural_dir / "screening_freeze_record.json"),
        "exact_reference_freeze_sha256": sha256(exact_dir / "exact_reference_freeze.json"),
        "wall_seconds": time.perf_counter() - started,
    }
    write_json(output / "pipeline_output_freeze.json", freeze)
    print(json.dumps({"status": "pass", "output": str(output), "scenarios": scenario_ids}, indent=2))


if __name__ == "__main__":
    main()
