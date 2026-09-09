# Surrogate-Guided Road Reopening Sequencing under Urban Flooding

This repository contains the code, frozen configurations, final synthetic flood scenarios, method-specific high-fidelity query ledgers, exact dynamic-programming reference outputs, statistical tables, and figure source data supporting the manuscript *Surrogate-Guided Road Reopening Sequencing under Urban Flooding with Budgeted User-Equilibrium Correction*.

## Scope of the artifact

The study evaluates a fixed 10-road reopening problem on ten held-out severe-flood scenarios (IDs 1001-1010). Candidate generation and screening use a frozen surrogate-guided protocol. Final ranking and local correction use method-specific high-fidelity user-equilibrium queries under budgets of 64, 128, 256, and 512 unique restored-subset states. The complete 1,024-state tables and conditional exact dynamic-programming references were produced only after method outputs were frozen.

The primary budget is 256 states. The final scenario generator seed is `2026080701`. Candidate generation uses the frozen scenario-specific seed rule recorded in `config/final_protocol_v1.1.json`.

## Repository layout

- `code/final_pipeline/`: frozen final-scenario generation, road selection, candidate generation, screening, budgeted UE search, local correction, controls, and exact DP.
- `code/model_backend/`: flood mapping and static UE implementation plus processed Sioux Falls inputs required by the frozen interface.
- `code/statistics/`: script used to produce the final statistical summaries.
- `config/`: final protocol, source-code manifest, and post-study SA configuration.
- `data/final_holdout_scenarios/`: scenarios 1001-1010, hashes, rejection log, and freeze record.
- `data/surrogate_training_and_preprocessing/`: recovery-state data, preprocessing outputs, data-generation code, and validation records.
- `data/network_reference/`: provenance and download information for the public Sioux Falls benchmark.
- `surrogate/final_ensemble/`: trained ensemble members, final preprocessor, fitting configuration, and diagnostics.
- `results/candidate_generation_and_screening/`: frozen 30,000-sequence pools and two-stage screening outputs.
- `results/query_ledgers_and_method_outputs/`: full-method and five-baseline outputs and method-specific UE query ledgers.
- `results/exact_reference_and_regret/`: 1,024-state exact tables, exact DP solutions, and regret calculations.
- `results/statistics/`: final statistical tables, plots, and workbook.
- `results/poststudy_permutation_SA/`: frozen SA configuration, development-grid summaries, final query ledgers, run histories, and results.
- `results/figure_and_table_source_data/`: publication figures and human-readable table source data.

## Environment

The frozen preprocessing manifest records Python 3.12.13, NumPy 2.3.5, and pandas 3.0.1. The ensemble training configuration records CPU PyTorch 2.13.0. A minimal dependency list is provided in `requirements.txt`.

## Reproducing the main frozen pipeline

The final pipeline entry point is `code/final_pipeline/run_final_pipeline.py`. Its command-line arguments are intentionally explicit so that frozen scenarios, protocol hashes, model locations, and output paths cannot be substituted silently.

Run `python code/final_pipeline/run_final_pipeline.py --help` for the full interface. The principal repository-relative inputs are:

```text
--scenario-physical data/final_holdout_scenarios/final_scenarios_physical_links.csv
--scenario-freeze data/final_holdout_scenarios/scenario_generation_freeze_record.json
--protocol config/final_protocol_v1.1.json
--protocol-hash-file config/final_protocol_v1.1_hash.txt
--surrogate-root surrogate/final_ensemble
--surrogate-preprocessor surrogate/final_ensemble/preprocessor_v2.json
--interface code/final_pipeline/interfaces_week3.py
--model-root code/model_backend
--scenario-count 10
```

This end-to-end calculation can be computationally expensive because every scenario may require up to 1,024 converged UE states after the method-output freeze. The frozen outputs are included so that the reported results can be audited without rerunning the complete calculation.

## Integrity and interpretation

`config/formal_code_manifest_v1.1.json` contains SHA-256 hashes for the frozen pipeline source files. The scenario and method-output directories contain additional hash-chain and freeze records. These records distinguish method-visible logical queries from physical cache reuse and document that the exact reference was generated after search outputs were fixed.

The post-study permutation-SA directory contains the complete frozen configuration, tuning summaries, method-specific query ledgers, per-iteration histories, and final outputs found in the archived research materials. The archived materials did not contain the standalone SA implementation source file. The SA results are therefore fully auditable from their recorded histories and ledgers but are not independently executable from this repository alone. The proposed method and the five predeclared baselines are represented by the frozen source files in `code/final_pipeline/`.

All workstation-specific paths, local account names, and contact email addresses were removed from the public artifact before release v1.0.1. Path-only sanitation did not alter the numerical data, method outputs, model parameters, or reported results. The repository-wide SHA-256 manifest was regenerated after sanitation.

## Network data

The Sioux Falls benchmark is maintained by TransportationNetworks:

https://github.com/bstabler/TransportationNetworks/tree/master/SiouxFalls

The repository includes the processed tables consumed by the frozen model backend. Source provenance and units are documented in `data/network_reference/README_SiouxFalls_source.md`.

## License and citation

The repository is released under the MIT License included in `LICENSE`. Please cite the associated manuscript and the permanent Zenodo record when using these materials.
