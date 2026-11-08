# Reviewer 1 and Reviewer 2 revision increment

This increment is merged into the existing `flood-traffic-optimization` repository root. Keep the original `code/`, `config/`, `data/`, `results/`, `surrogate/`, licence and old version tags. The increment adds revision directories; the original scientific files are not replaced. Root `README.md` is updated and root `MANIFEST.sha256` is regenerated for the merged layout.

## Scientific coverage

| Directory | Contents | Manuscript/Supplement scope |
|---|---|---|
| revision_R1/comment4_1 | Frozen 30-scenario comparison, exact references, saved summaries, post-hoc phase diagnostics, original SA source recovery | Tables 8–9; S10 |
| revision_R1/comment4_2 | Numerical-precision comparison and fixed-order re-evaluation | Table 7; S11 |
| revision_R1/comment4_3 | Isolated serial timing and offline-cost summaries | Table 12; S12 |
| revision_R1/comment4_4 | Exploratory scaling, final matched summaries, unfinished-run evidence and supplemental reference costs | Table 13; S13 |
| revision_R1/comment4_5 | Frozen v2 F0–F9/Greedy-ILS ablation, scenario/seed summaries, LOSO, bootstrap and phase/predictor summaries | Table 14; S14 |
| revision_R1/comment4_6 | Scenario-level and nested uncertainty summaries; variance decomposition | Tables 10–11; S15 |
| revision_R1/comment4_7 | Training/OOB/early-stopping records and conditional-DP/candidate/queue audit | Table 1 and definitions; S16 |
| revision_R1/comment5_2 | Demand/TSTT/ATT/bottleneck tables | Table 15; S17 |
| revision_R1/comment5_4 | Frozen-order transfer to duration-aware conditional DP | Table 16; S18 |
| revision_R1/comment5_5 | Prespecified alternative recovery sets and signed terminal residual comparisons | Tables 17–18; S19 |
| revision_R2/comment3 and comment3_extension | Flood-input sensitivity, CRN checks and threshold intervals | Tables 19–21; S20 |
| revision_R2/comment6_sa_multiseed | SA implementation binding, legacy replay and 100-run statistics | Table 22; S9 extension |

Comments 5.1 and 5.3 are supported by existing code, comparison results and model-scope explanations, not newly invented separate simulations. See `REVISION_RESULTS_CROSSWALK.csv` for exact paths.

## GitHub versus the complete archive

This is a selected, lightweight source-and-summary increment, not the complete numerical archive. All methods, scenarios and adverse results in the selected summary tables are retained. Selection concerns file type, scientific role and size, never observed performance. Large candidate pools, per-query logs, replay arrays, full bootstrap distributions, model artifacts and many detailed raw runs remain in the complete revision release.

`REVISION_ARCHIVE_FILE_INDEX.csv` lists the relative full-archive paths, sizes and SHA256 hashes of revision files not duplicated here. Some listed files are small but are raw records or editorial/provenance details rather than GitHub entry-point material. The full archive's layout is the earlier `public_release` root, not a directory to paste wholesale into this Git repository.

The complete revision archive is openly published as **v1.1.0** (8 November 2026), DOI https://doi.org/10.5281/zenodo.24060645 . Its `public_release.rar` contains the complete revision payload with the `public_release` layout described above; the same record also retains the original v1.0.1 ZIP. `config/revision_archive_locations.json` records the published version, official file metadata and availability. The original DOI https://doi.org/10.5281/zenodo.22669165 still identifies v1.0.1 and must not be presented as containing the revision data. The family DOI https://doi.org/10.5281/zenodo.22664565 links the version series. This GitHub synchronization verifies the official record metadata; it does not certify a fresh download and per-file verification of the entire 5.4 GB remote RAR or complete relocated execution of the experiments.

## Offline inspection

From the repository root or directly from the local increment:

```text
python tools/verify_github_update.py --mode overlay
python tools/inspect_revision_results.py
```

The first command checks the new increment's file hashes; the second reads the saved main counts and all 22 frozen ablation-bootstrap rows. Neither imports research modules nor calls UE, generates scenarios, trains or infers models, or runs search. These commands were actually executed when this increment was prepared.

After merging with the old repository:

```text
python tools/verify_github_update.py --mode merged
```

Merged mode checks the complete old-plus-new `MANIFEST.sha256`, allowing Git's normal LF/CRLF checkout conversion for UTF-8 text. The exact file-byte hashes and any normalized-text matches are reported separately. A changed numeric token or altered code content cannot pass by newline normalization. The original frozen source hashes still refer to their archived bytes.

## Historical execution paths

Revision scripts are exact archived scientific sources and retain original filesystem and output conventions. They are not advertised as newly validated, fully relocatable one-command experiments. See `REVISION_PATHS.md`. Full computational reproduction requires the complete archive and proper working-copy path configuration; use fresh outputs and retain all frozen scientific parameters. Do not execute an old report-generation or audit script casually, since some scripts create directories or write outputs on import.

## Required interpretation

- The 30-scenario comparison uses 1,590 `phase=query_cap` records. Technical seeds are not independent flood scenarios.
- The ablation has 330 completed runs, not a new retrospective 900-run study. S14/Table S20 uses 10,000 paired scenario bootstrap draws, seed 2026102906, 10 independent scenario units and 22 source rows. Intervals are descriptive.
- Scaling has 179/180 completed optimizations. The m=14 primary matched set is 4401–4405; the remaining 4406 evidence and the separately timed supplemental reference work remain available. No missing algorithm run is fabricated.
- G1 historically remains FAIL_NUMERIC_RECONCILIATION_PENDING; G1-R directly explained three members only. G2 retains its state-log archive limitation. Historical results are not silently changed to a global PASS.
- Exact DP is conditional on the stored state costs and chosen road set. Terminal state C(E) has zero equal-duration objective weight.
- ATT is model-implied mean-stage travel time. A ten-road endpoint is distinct from restoring every originally closed road. Signed terminal decompositions are not causal attribution.
- Heterogeneous-duration analysis tests transfer of frozen orders. Best among tested recovery sets is not a global joint optimum.
- No overall surrogate advantage or statistical significance claim is introduced by this release preparation.

The initial local increment preparation did not overwrite old data, checkpoints, algorithms, source protocols or marked Word documents. Following the author's Zenodo publication, this documentation update binds the GitHub materials to the existing v1.1.0 DOI and updates the two affected checksum inventories. It changes no scientific result and creates no additional Zenodo version or GitHub release.
