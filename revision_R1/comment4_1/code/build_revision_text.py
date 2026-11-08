"""Create evidence-linked comment-level text after analysis; never edits originals."""
from pathlib import Path
import json, html
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
LABEL={'proposed':'Proposed','sa_original':'Original permutation SA','sa_restart':'SA-restart','greedy_ls':'UE-Greedy-LS','greedy_ils':'UE-Greedy-ILS','random_ls':'Random-start + shared LS','ue_beam':'UE-Beam','ue_bibeam':'UE-Bidirectional Beam'}
ORDER=list(LABEL)
def f(x):return f'{float(x):.4f}'
def write(name,text):
    p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
def table(df,columns,labels=None):
    labels=labels or columns
    out=['| '+' | '.join(labels)+' |','| '+' | '.join(['---']*len(columns))+' |']
    for _,r in df.iterrows():out.append('| '+' | '.join(str(r[c]) if not isinstance(r[c],(float,np.floating)) else f(r[c]) for c in columns)+' |')
    return '\n'.join(out)
def main():
    report=json.loads((ROOT/'analysis/analysis_summary.json').read_text(encoding='utf-8'))
    assert report['status']=='ANALYSIS_COMPLETE'
    cfg=json.loads((ROOT/'protocol/frozen_protocol.json').read_text(encoding='utf-8'))
    precision=json.loads((ROOT/'analysis/selected_objective_precision_stability.json').read_text(encoding='utf-8'))
    s=pd.read_csv(ROOT/'analysis/Table_R2_method_summary.csv');q=s[s.phase=='query_cap'].set_index('method');t=s[s.phase=='time_cap'].set_index('method')
    pairs=pd.read_csv(ROOT/'analysis/Table_R3_primary_paired_comparisons.csv').set_index('comparator')
    allruns=pd.read_csv(ROOT/'analysis/all_run_results.csv');sc=pd.read_csv(ROOT/'analysis/scenario_seed_summaries.csv')
    m=q.loc['proposed'];sa=q.loc['sa_restart'];greedy=q.loc['greedy_ils'];beam=q.loc['ue_bibeam']
    supported=[LABEL[k] for k,r in pairs.iterrows() if r.mean_ci_low>0 and r.holm_adjusted_sign_p<.05]
    unsupported=[LABEL[k] for k in pairs.index if LABEL[k] not in supported]
    interpretation=(f'The prespecified paired analysis supports a positive average regret difference favoring Proposed against {", ".join(supported)}. ' if supported else 'The prespecified paired analysis does not establish a positive average regret advantage for Proposed against any of the three primary comparators. ')
    if unsupported and supported:interpretation+=f'An average advantage over {", ".join(unsupported)} is not established by the joint confidence-interval and multiplicity-adjusted sign-test criteria. '
    if pairs.loc['greedy_ils'].mean_ci_high<0:
        interpretation+='The mean difference and its unadjusted 95% paired bootstrap interval for UE-Greedy-ILS favor the UE-only control. The prespecified one-sided tests target Proposed superiority and do not test significance in the reverse direction. '
    interpretation+='These comparisons concern the complete frozen search designs; they do not isolate the effect of ensemble training, prefix stratification, or any single candidate source.'
    bettertail=bool(m.P90_scenario_mean_regret_pct<sa.P90_scenario_mean_regret_pct)
    tail=(f'The descriptive P90 of scenario seed means is lower for Proposed than SA-restart ({f(m.P90_scenario_mean_regret_pct)}% versus {f(sa.P90_scenario_mean_regret_pct)}%). ' if bettertail else f'The descriptive P90 does not reproduce the original direction of the Proposed-versus-SA tail advantage ({f(m.P90_scenario_mean_regret_pct)}% for Proposed versus {f(sa.P90_scenario_mean_regret_pct)}% for SA-restart). ')
    tail+='P90 and maxima are secondary and unstable with only 30 scenarios; their bootstrap intervals and seed distributions are supplied rather than treated as primary significance claims.'
    stats=[]
    for key,r in pairs.iterrows():
        stats.append(f'Against {LABEL[key]}, the mean paired improvement was {f(r.mean_paired_improvement_pp)} percentage points (95% paired scenario bootstrap CI {f(r.mean_ci_low)} to {f(r.mean_ci_high)}), with {int(r.proposed_wins)}/{int(r.ties_by_empirical_epsilon)}/{int(r.proposed_losses)} Proposed wins/ties/losses and a Holm-adjusted one-sided sign-test p value of {r.holm_adjusted_sign_p:.6g}.')
    pairedtext='\n\n'.join(stats)
    qtable=q.loc[ORDER].reset_index()
    numeric=table(qtable,['label','mean_scenario_mean_regret_pct','median_scenario_mean_regret_pct','P90_scenario_mean_regret_pct','max_scenario_mean_regret_pct','max_single_run_regret_pct','mean_queries'],['Method','Mean of scenario means %','Median scenario mean %','P90 scenario mean %','Max scenario mean %','Max individual run %','Mean unique queries'])
    timetable=table(t.reset_index(),['label','mean_scenario_mean_regret_pct','P90_scenario_mean_regret_pct','mean_queries','mean_fresh_wall_seconds'],['Method','Mean scenario mean %','P90 scenario mean %','Mean visible queries','Mean fresh wall seconds'])
    eps=report['primary_equivalence_kappa'];refine=report['maximum_selected_path_refinement_relative_tstt_difference']
    methods=f'''We conducted a prospectively frozen revision experiment on 30 newly generated severe-flood scenarios (3001–3030). The generation seed was 2026102702; accepted scenarios followed the original spatial flood model and qualification gates. Depth vectors, closure masks and combined hashes were checked against all supplied historical inputs, including scenarios 121–160, which were used only for input deduplication and never for optimization or model fitting. A superseded engineering batch (2001–2030) was also excluded from new input generation and from confirmatory results. That batch was invalidated when the original SA source became available, before its outcome values were inspected. No accepted formal scenario was removed after search outcomes were produced.

The original surrogate weights, preprocessor, candidate quotas, screening rules and UE correction logic were retained. Candidate and screening seeds were extended to 2026080702+s+1000000r and 2026080703+s+1000000r, respectively, for scenario s and replicate r=0,…,9. This varies search randomness, not surrogate training randomness. Five stochastic methods each received ten prespecified seeds per scenario: Proposed, original permutation SA, SA-restart, UE-Greedy-ILS and random-start plus shared local search. UE-Greedy-LS and the forward and bidirectional UE beam variants were deterministic. The original SA implementation was recovered and its objective, sequence and query count matched source replay on all ten archived tables. Its move probabilities, current-objective temperature scaling and proposal-wise cooling were preserved; SA-restart additionally used a development-frozen restart rule. The greedy and random-start controls reuse the original UE local-search routine; the ILS variant perturbs an incumbent by two swaps and resumes that same routine. New baseline settings were selected only on scenarios 246, 247 and 249. Because these scenarios belong to the surrogate training data, Proposed runs there were software checks and were excluded from comparative inference.

The main cap was 256 method-specific unique UE states, with nested 64/128 checkpoints reported only as descriptive anytime behavior. The new experiment does not extend to 512 queries; the original 512-query analysis remains a separate historical result. Logical ledgers count a state when each method first requests it. Numerical state calculations can be reused physically in the query-cap group, but algorithms cannot inspect unrequested values. Methods that stop early retain their actual query counts. Our UE beam adaptations maintain exact subset partial-cost labels and subset dominance, with development-selected initial widths 8 (forward) and 2 (bidirectional) and fixed progressive widening. They do not implement the traffic-benefit bounds, original branch pruning or adaptive-beam machinery of Gokalp et al. (2021); no full-replication claim is made.

All primary UE states satisfy RG≤10⁻⁹. The new path-based column-generation solver maintains OD feasibility and recomputes a full all-or-nothing relative gap; it accelerates numerical assignment without changing BPR, flood mapping, demand or the sequence objective. R0–R9 retain equal weights and R10 has zero weight. The original normalization constant 7480225.3449211195 is retained. On development states, tolerance refinement to RG≤10⁻¹¹ fixed κ={eps:.12g}; numerical equivalence means |Ja−Jb|≤κ max(1,|Jreference|). This is an empirical tolerance, not a rigorous TSTT error bound. After all query- and time-cap outputs were hashed and frozen, we completed every 1,024-state table and computed conditional subset-DP references. All B=256 selected paths and DP paths were additionally checked at RG≤10⁻¹¹. An independent backward Bellman recurrence verified all 30 production DP objectives.

The primary endpoint is each scenario's mean regret across search seeds. Thirty flood scenarios, rather than 300 algorithm runs, are the independent units. Three prespecified comparisons test Proposed against SA-restart, UE-Greedy-ILS and bidirectional beam using 100,000 paired scenario bootstrap resamples and one-sided exact sign tests with empirical-equivalence ties; Holm correction covers those three tests. P90 values use NumPy linear interpolation and are secondary, with 10,000 nested scenario/seed bootstrap resamples. Original SA, deterministic Greedy-LS, forward beam and random-start controls remain fully reported secondary comparators.

In a separate elapsed-time experiment, Proposed at B=256 with the fixed reference seed r=0 was rerun from a fresh state cache on each scenario. Its measured candidate construction plus online UE search time supplied that scenario's cap for ten fresh-cache SA-restart runs, ten fresh-cache UE-Greedy-ILS runs and one deterministic bidirectional-beam run. A safety cap allowed at most 1,023 objective-relevant subset queries. Each scenario used the same pinned logical CPU across timing methods and single-threaded libraries. UE JIT warmup on development input and model loading occurred before timing; surrogate inference remained inside the measured candidate-construction stage. A scalar UE solve already in progress could finish after the deadline, but its value was then discarded and the overrun recorded. This experiment contains one Proposed timing seed per scenario; broader seed-stability claims use the separate ten-seed query-cap group. Offline training and setup are excluded, so these timings concern reuse of an existing model, not training-inclusive amortization.'''
    results=f'''Across the 30 fresh scenarios, Proposed at B=256 had mean, median, P90 and maximum scenario seed-mean regrets of {f(m.mean_scenario_mean_regret_pct)}%, {f(m.median_scenario_mean_regret_pct)}%, {f(m.P90_scenario_mean_regret_pct)}% and {f(m.max_scenario_mean_regret_pct)}%, respectively. Its maximum individual-run regret was {f(m.max_single_run_regret_pct)}%. Corresponding mean scenario regrets were {f(sa.mean_scenario_mean_regret_pct)}% for SA-restart, {f(greedy.mean_scenario_mean_regret_pct)}% for UE-Greedy-ILS and {f(beam.mean_scenario_mean_regret_pct)}% for bidirectional beam (Table R2). Numerical-equivalent objective hits occurred in {100*m.equivalent_objective_hit_rate:.2f}% of Proposed runs, using the empirical development-frozen equivalence rule.

{pairedtext}

{interpretation}

{tail}

All 1,590 query-cap runs and 660 independent timing runs were retained. The 30 completed reference tables contain 30,720 converged states. The largest relative TSTT change on the stronger-tolerance selected-path checks was {refine:.6g}. DP is exact for these numerical conditional tables, rather than a certificate of a fully converged physical optimum. The historical ten-scenario experiment is reported separately: high-precision reevaluation of its frozen decisions gives Proposed median/P90/maximum regrets 0.0383613%/0.4620987%/1.6909827%, and original SA 0%/0.8160741%/3.5070691%; all ten DP reference sequences are unchanged. This numerical bridge does not create independent validation observations.

In the independent time-cap group, mean scenario regrets were {f(t.loc['proposed'].mean_scenario_mean_regret_pct)}%, {f(t.loc['sa_restart'].mean_scenario_mean_regret_pct)}%, {f(t.loc['greedy_ils'].mean_scenario_mean_regret_pct)}% and {f(t.loc['ue_bibeam'].mean_scenario_mean_regret_pct)}% for Proposed, SA-restart, UE-Greedy-ILS and bidirectional beam, respectively. Their mean visible unique-query counts were {f(t.loc['proposed'].mean_queries)}, {f(t.loc['sa_restart'].mean_queries)}, {f(t.loc['greedy_ils'].mean_queries)} and {f(t.loc['ue_bibeam'].mean_queries)}. Figure R4 and the timing table report measured wall time and observed deadline overruns. The reduction 1−256/1024=75% concerns state-information calls and is not an elapsed-time saving.'''
    briefstats=' '.join(f'For {LABEL[key]}, the comparator-minus-Proposed mean difference was {f(r.mean_paired_improvement_pp)} percentage points (95% CI {f(r.mean_ci_low)} to {f(r.mean_ci_high)}; Holm-adjusted sign-test p={r.holm_adjusted_sign_p:.6g}).' for key,r in pairs.iterrows())
    mainresults=f'''In the 30 new scenarios, mean scenario seed-mean regret at B=256 was {f(m.mean_scenario_mean_regret_pct)}% for Proposed, {f(sa.mean_scenario_mean_regret_pct)}% for SA-restart, {f(greedy.mean_scenario_mean_regret_pct)}% for UE-Greedy-ILS and {f(beam.mean_scenario_mean_regret_pct)}% for bidirectional beam. Table R2 reports all eight methods, and Figure R2 displays within-scenario seed variability. {briefstats}

{interpretation} {tail}

The separate fresh-cache time-cap group produced mean scenario regrets of {f(t.loc['proposed'].mean_scenario_mean_regret_pct)}%, {f(t.loc['sa_restart'].mean_scenario_mean_regret_pct)}%, {f(t.loc['greedy_ils'].mean_scenario_mean_regret_pct)}% and {f(t.loc['ue_bibeam'].mean_scenario_mean_regret_pct)}% for the same four methods, respectively. This comparison includes Proposed candidate construction and online UE costs, with one fixed Proposed timing seed per scenario. Full timings, numerical-stability checks and the historical ten-scenario reconciliation are supplied separately in the revision supplement. The 75% reduction in unique state-information calls does not represent a wall-clock saving.'''
    abstractclaim=('Prespecified paired tests supported an average improvement over '+', '.join(supported)+'. ' if supported else 'Prespecified paired tests did not establish an average advantage over the three primary adaptive comparators. ')
    if supported and unsupported:abstractclaim+='An average advantage over '+', '.join(unsupported)+' was not established. '
    abstract=f'''Road reopening under flooding requires sequential decisions whose network costs depend on congested route choice. We combine a fixed ensemble surrogate and structured candidate exploration with budgeted user-equilibrium (UE) correction. To test added decision value against adaptive methods, we froze algorithms and numerical rules before generating 30 new severe-flood scenarios on Sioux Falls, with ten search seeds per stochastic method. The primary cap was 256 unique UE states per method; complete 1,024-state tables and conditional dynamic-programming references were constructed only after all search outputs were frozen. At this cap, Proposed achieved a mean scenario seed-mean regret of {f(m.mean_scenario_mean_regret_pct)}% and median/P90 values of {f(m.median_scenario_mean_regret_pct)}%/{f(m.P90_scenario_mean_regret_pct)}%, compared with mean regrets of {f(sa.mean_scenario_mean_regret_pct)}%, {f(greedy.mean_scenario_mean_regret_pct)}% and {f(beam.mean_scenario_mean_regret_pct)}% for SA-restart, UE-Greedy-ILS and a bidirectional UE beam adaptation. {abstractclaim}Separate fresh-cache elapsed-time comparisons assess online costs when the trained model is reusable. Findings remain conditional on this network, synthetic flood generator, fixed demand and ten selected recoverable roads; they do not establish cross-network or training-inclusive computational superiority.'''
    discussion=f'''{interpretation} {tail} The new greedy, iterated-search and random-start controls use the same high-fidelity local-search code, making a strong UE-only alternative explicit. Differences against these controls reflect the complete initialization and exploration design; they do not by themselves identify an independent contribution of neural ensembles or individual candidate sources. Any claim that surrogate complexity is necessary should therefore remain restricted to the observed complete-method comparison. The numerical cost table, source code, method-specific ledgers and seed distributions support auditability independently of which optimizer has the lowest regret.

The experiment measures transfer to new scenarios drawn from the same synthetic mechanism, rather than transfer to another city or a measured flood event. It fixes the surrogate's training realization and varies search seeds only. The timing comparison uses one Proposed reference seed per scenario and excludes training/setup; it cannot establish total economic break-even or a universal wall-clock advantage. Thirty scenarios offer limited tail precision. Numerical equivalence is empirically calibrated, and conditional DP remains exact relative to a numerical state table. The beam comparators are documented adaptations rather than complete reproductions of Gokalp et al. (2021).'''
    write('manuscript/4.1_英文替换与新增段落.md',f'''# Reviewer 1 Comment 4.1 manuscript text

Status: evidence-grounded replacement passages for author integration, not an already edited or typeset full manuscript. Locations refer to the supplied Manuscript (14).docx by section heading, not unverified page numbers. Other reviewer comments and original figures/tables are not silently renumbered. R labels below are revision-package identifiers and require final manuscript numbering when integrated.

## Replace Abstract

{abstract}

## Replace the final Introduction comparison sentence

The original ten-scenario study provides a historical benchmark. A separately frozen revision experiment evaluates 30 new severe scenarios against prespecified adaptive SA, UE-only greedy/local-search and UE beam comparators, with repeated search seeds, numerical stability checks and independent elapsed-time caps.

## Replace the numerical solver description and stopping-rule paragraph

Traffic assignment follows Wardrop equilibrium through the convex Beckmann formulation. The archived initial experiment used a Frank–Wolfe-type solver and RG≤5×10⁻⁴. For the revision comparisons and historical numerical reconciliation, the same BPR, demand and flood-state models are solved using shortest-path column generation and feasible pairwise route-flow equilibration, with a recomputed all-or-nothing relative gap of at most 10⁻⁹. Infeasible, non-converged and non-finite results are rejected rather than admitted to the cache. Selected paths are additionally checked at 10⁻¹¹. Algorithm details and empirical numerical-equivalence calibration are given in the revision supplement. DP is exact for the resulting conditional numerical cost table; the relative gap alone is not a TSTT-error certificate.

## Correct two feature names to match the frozen source

In the six-aggregate list, replace “remaining-closed baseline flow” and “remaining-closed betweenness” with “baseline flow summed over initially closed roads” and “betweenness summed over initially closed roads”. The archived transform computes initial_closed @ baseline_flow and initial_closed @ betweenness (interfaces_week3.py, lines 146–154). Preserve the model and feature implementation; this is a description correction, not retraining or a changed optimization method. Check Supplementary Section S5 against the same two definitions during integration.

## Prefix the historical Results with a scope sentence

The following ten-scenario results document the archived initial protocol and its original numerical precision. Their stricter-tolerance reconciliation is reported separately in the revision supplement. The independent revision comparison below uses 30 freshly generated scenarios and a distinct predeclared analysis.

## Replace the long historical SA interpretation paragraph in Comparison with baseline methods

The archived ten-scenario study also included a post-study SA sensitivity analysis with one seed per scenario. Those historical results are retained as descriptive evidence; adaptive-comparator inference and search-seed conclusions now use the independently frozen revision experiment reported below.

## Add a short main-text Methods subsection Independent revision experiment

We froze all methods and an empirical numerical-equivalence rule before generating 30 new severe-flood scenarios. At B=256 unique UE states, five stochastic methods were evaluated with ten prespecified search seeds per scenario and three deterministic controls once per scenario. Newly added SA-restart, UE-Greedy-ILS and beam settings were selected only on development scenarios 246, 247 and 249; original surrogate weights and Proposed search rules remained fixed. Beam comparators are adaptations without the original traffic-benefit bounds and branch pruning. All methods shared the same objective and RG≤10⁻⁹ requirement. Complete numerical state tables and conditional DP references were constructed after all query- and time-cap outputs were frozen. Scenario mean regret was the primary unit of comparison, with three prespecified paired comparisons and Holm-adjusted sign tests. A separate fresh-cache elapsed-time experiment used each scenario's Proposed B=256 runtime as the cap for UE-only comparators. Full algorithm adaptations, seeds, numerical validation and timing scope are reported in the revision supplement.

## Add Results Independent revision comparison

{mainresults}

{numeric}

The main table summarizes scenario seed means, not 300 independent flood observations. The maximum individual-run column is explicitly distinct. Shared-cache execution times in the query group are diagnostic only; fresh time comparisons are separate.

## Replace the Discussion interpretation of the SA sensitivity result and update Limitations

{discussion}

## Replace the final Conclusion contribution claim

{interpretation} The study provides an auditable framework for limiting high-fidelity state information and measuring resulting decisions against post-freeze conditional numerical references. Its practical value must be judged against the reported UE-only alternatives and the cost of maintaining a reusable surrogate, within the present network and flood-model scope.

## Data and code availability addition pending repository release

The archived initial version remains unchanged. The local revision bundle contains the frozen protocol, original source snapshot, new inputs, complete query ledgers, conditional cost tables, exact solutions and analysis scripts. A new public repository/Zenodo version has not been published in this task; the author must insert its real persistent identifier after release. Do not invent a revised DOI.
''')
    write('manuscript/4.1_补充材料实验方法与图注.md',f'''# Supplementary revision experiment for Comment 4.1

## Reproducible methods

{methods}

## Table R1 mechanisms and configurations

See analysis/Table_R1_algorithm_mechanisms.csv. Original SA uses temperature ratio 0.0025, cooling 0.995, adjacent/arbitrary-swap/insertion proposal probabilities 0.70/0.15/0.15 and a 1,000-proposal no-new-state stall limit. SA-restart uses the same temperature/cooling and a 100-proposal restart stall trigger; its useful residual-budget neighborhood evaluations are logged. UE-Greedy-LS may stop below the cap without fabricated queries. UE-Greedy-ILS uses two-swap perturbations and the original local correction. Beam widths progress through fixed multiples 1,2,4,8,16 of their selected initial width. Details are executable in code/experiment.py and immutable hashes are in protocol/frozen_protocol.json.

## Table R2 query-capped results

{results}

{numeric}

Regret is 100(J−J*)/J*, with J* the numerical conditional DP reference. Stochastic rows summarize each scenario's ten-seed mean before aggregating across 30 scenarios; deterministic rows use their sole result. Full mean, median, standard deviation, IQR, minimum, maximum, threshold rates and nested bootstrap tail intervals are included in the CSV tables.

## Table R3 primary paired comparisons

{pairedtext}

Positive paired differences favor Proposed. The one-sided direction tests the specific prespecified improvement claim; a nonsignificant result must not be interpreted as equivalence. Wins and ties use empirical numerical tolerance. Bootstrap intervals quantify sampling variability across the conditional scenario generator and are not universal cross-network guarantees.

## Separate elapsed-time group

{timetable}

Mean visible queries exclude UE values that returned after the deadline; their physical calculations and overruns are retained in raw logs. Wall time can exceed the search deadline by the last atomic solve and bookkeeping. Reference Proposed has one fixed search seed per scenario, whereas SA-restart and ILS have ten. No pooled shared-cache timing is presented as a standalone speedup. Offline training, JIT compilation and model-loading are outside this online comparison; candidate construction and inference are included in the Proposed measured reference.

The 75% information reduction uses the archived convention of a complete 1,024-state table. Because the full-restoration state R10 has zero objective weight, a minimal exact decision calculation needs only 1,023 state costs; the corresponding reduction is 1−256/1023=74.98%. The time-cap group permits those 1,023 relevant states. Neither percentage measures elapsed time. Deadlines are checked at state requests, and over-deadline numerical results are withheld; this is an instrumented deadline rather than a hard operating-system preemption, so actual wall times and overruns remain part of the evidence.

The time group recorded {report['time_group_discarded_late_solves']} discarded late solves, with a maximum recorded deadline overrun of {report['time_group_maximum_recorded_deadline_overrun_seconds']:.6f} s. Table R4_fresh_timing_details.csv includes every measured run. The UE-seconds component records visible state solves only; the final discarded solve's elapsed cost remains in total wall time but is not separately measured in that component. Total wall time, rather than the partial component sum, is authoritative for online cost. Query-cap runs used {report['query_group_logical_unique_state_requests']:,} method-specific unique-state requests in aggregate. The independent fresh-cache time group physically solved {report['time_group_physical_state_solves_including_late']:,} states including discarded late solves, in addition to shared-cache and precision-validation work; 30,720 denotes the distinct reference-table states, not total computational effort.

## Additional selected-objective stability diagnostic

The maximum individual selected-state relative TSTT change ({refine:.8g}) was larger than the development-state observation used to calibrate the empirical equivalence rule. We therefore reconstructed all {precision['paths']:,} already selected paths (1,590 method choices plus 30 primary DP paths) using their computed RG≤10⁻¹¹ costs, without changing algorithms, choices, thresholds or the primary reference. Every path's objective change was within the frozen objective-equivalence tolerance; the largest change was {precision['max_change_over_frozen_objective_epsilon']:.6f} times that tolerance. These are different quantities: an individual-state relative TSTT change is not the sequence objective error. The diagnostic is archived in selected_objective_precision_stability.csv and does not certify optimality over a complete 10⁻¹¹ state table.

## Figure legends

Figure R1. Descriptive anytime regret at 64, 128 and 256 method-specific unique-state queries. Points show the median and error bars the interquartile range across 30 scenario seed means. All ten seeds are included for stochastic methods. These are checkpoints of B=256 configurations, not independently tuned low-budget algorithms. The symmetric log regret axis has a linear region within ±0.001 percentage points and represents zero without a pseudocount.

Figure R2. Within-scenario seed variability for Proposed and SA-restart. Each dot is one of ten prespecified seeds; boxes show the median and IQR and whiskers the full seed range. All 30 scenarios appear in ID order. The symmetric log axis has a linear region within ±0.001 percentage points. Search-seed variability does not include ensemble retraining.

Figure R3. Paired scenario effects for SA-restart, UE-Greedy-ILS and bidirectional beam relative to Proposed. Colored points show comparator minus Proposed seed-mean regret in each of 30 scenarios. Black diamonds and horizontal intervals show the mean paired effect and 95% percentile confidence interval from 100,000 paired scenario bootstrap resamples. Positive values favor Proposed. Holm-adjusted one-sided sign tests are provided in Table R3.

Figure R4a. Online fresh-cache wall time against visible unique-state queries in the independent time-cap group. Each point is one scenario's seed mean, with 30 scenarios per method. Proposed has one prescribed reference seed; the stochastic UE-only methods have ten and bidirectional beam one. The per-scenario reference time cap is measured using Proposed candidate generation plus search; warmup and offline training are excluded. Points are raw scenario summaries without uncertainty bars.

Figure R4b. Regret in the independent time-cap group. Dots show every scenario seed mean, boxes the across-scenario median and IQR, and whiskers the 10th–90th percentiles. Symmetric log axis linear region ±0.001 percentage points. These data are separate from the 256-query group and do not support interpreting the 75% query reduction as a wall-time reduction.

## Verified literature and adaptation boundary

Gokalp et al. (2021), Post-disaster recovery sequencing strategy for road networks, Transportation Research Part B, DOI 10.1016/j.trb.2021.09.007. The adaptation here uses subset forward/backward beam expansion; original traffic-benefit bounds and pruning are not reproduced. Primary algorithm exposition: https://sboyles.github.io/group/Gokalp.pdf . Crocker and Boyles (2025), Heuristic Selection in Disaster Recovery Sequencing, Journal of Infrastructure Systems 31(3), DOI 10.1061/JITSE4.ISENG-2467, verified at https://ascelibrary.org/doi/abs/10.1061/JITSE4.ISENG-2467 . This later study is context and is not claimed to be reproduced by these baseline implementations.
''')
    response=f'''# Response to Reviewer 1 Comment 4.1

This is a comment-specific draft supported by completed local experiments. Revised passages are supplied for integration; the full Word manuscript has not yet been edited, typeset or assigned final page/line numbers. It must not be submitted as if those integrations have already occurred.

## Response

Thank you for identifying the distinction between the original diagnostic baselines and adaptive UE-only optimization. We agree that one post-study SA run per archived scenario cannot establish a repeatable tail advantage or isolate added value from surrogate-guided search. We therefore conducted a separately frozen comparison on 30 newly generated severe scenarios, rather than treating the historical ten scenarios as new confirmatory data.

The completed comparison includes 1,590 query-cap runs: Proposed, original permutation SA, SA-restart, UE-Greedy-ILS and random-start plus the original UE local search each use ten prespecified seeds per scenario; deterministic UE-Greedy-LS, forward UE beam and bidirectional UE beam are also included. All share the same fixed ten-road recovery set, R0–R9 objective and cap of 256 method-specific unique UE states. The original surrogate and Proposed structure were unchanged. New comparator parameters were frozen using scenarios 246, 247 and 249 only; those scenarios were excluded from comparative inference. Source replay verified the recovered original SA on all ten historical tables before the fresh comparison.

We also implemented the requested problem-specific forward and bidirectional UE beam comparisons after examining Gokalp et al. (2021). Their exact subset partial-cost labels and subset dominance are adapted to the present objective and information budget. We explicitly call them adaptations; the original traffic-benefit bounds, branch pruning and adaptive-beam implementation are not reproduced. The supplied Methods and supplemental algorithm drafts state this boundary so that the beam implementation is not presented as a full reproduction.

Before generating the fresh scenarios, we fixed RG≤10⁻⁹ and an empirical numerical-equivalence threshold calibrated by development-state refinement to RG≤10⁻¹¹. All search outputs, including a separate fresh-cache elapsed-time comparison, were frozen before constructing the 30 complete 1,024-state tables and their conditional DP references. Independent objective reconstruction, query-budget checks and a backward Bellman implementation passed for all runs. The stronger-tolerance selected-path check had a maximum relative TSTT change of {refine:.6g}; we describe conditional numerical exactness rather than physical certification.

The fresh B=256 comparison gives Proposed mean/median/P90 scenario seed-mean regrets of {f(m.mean_scenario_mean_regret_pct)}%/{f(m.median_scenario_mean_regret_pct)}%/{f(m.P90_scenario_mean_regret_pct)}%. Mean scenario regrets are {f(sa.mean_scenario_mean_regret_pct)}% for SA-restart, {f(greedy.mean_scenario_mean_regret_pct)}% for UE-Greedy-ILS and {f(beam.mean_scenario_mean_regret_pct)}% for bidirectional beam. {interpretation}

{pairedtext}

{tail}

The 30 scenarios are the statistical units, with seeds nested within scenarios. Three primary paired comparisons use 100,000 scenario bootstrap replicates and Holm-adjusted one-sided sign tests; other baselines and tail summaries are reported in full as secondary analyses. We additionally completed 660 fresh-cache timing runs under scenario-specific elapsed-time caps. These separate information-budget effects from online cost when a trained model is already available; they do not claim a 75% wall-clock saving or include the surrogate's training cost.

## Supplied manuscript changes

The accompanying replacement passages revise the Abstract, the Introduction comparison statement, add a concise independent-revision Methods subsection and Results section, and narrow the Discussion, Conclusion and Limitations to the evidence above. Table R2 and Figure R2 are the proposed main-text evidence; Tables R1/R3 and Figures R1/R3/R4 can accompany the supplement. Exact final numbering and page references await integration into Manuscript (14).docx.

Proposed revised conclusion wording:

*{interpretation} The study provides an auditable framework for limiting high-fidelity state information and measuring resulting decisions against post-freeze conditional numerical references. Its practical value must be judged against the reported UE-only alternatives and the cost of maintaining a reusable surrogate, within the present network and flood-model scope.*
'''
    write('manuscript/Reviewer1_4.1_Response_英文草稿.md',response)
    chinese=f'''# 4.1 返修结果与中文核对

已完成 30 个正式新严重情景（3001–3030）、1,590 次同查询预算运行、660 次独立耗时运行，以及后置 30,720 状态精确参照。所有随机方法的十个种子均保留；以情景为统计单位。初稿与原代码没有被覆盖。

本批独立验证没有支持 Proposed 相对三个预设强对照的平均增益。尤其 UE-Greedy-ILS 的平均 regret 为 {f(greedy.mean_scenario_mean_regret_pct)}%，Proposed 为 {f(m.mean_scenario_mean_regret_pct)}%；其配对区间也偏向 UE-only 对照。原稿关于代理结构额外价值与稳定尾部优势的表述需要收缩，不能只增加几个实验后继续原结论。这个判断针对当前冻结方案和本批条件情景，不证明代理方法在所有问题上都无用。

## 核心结果

{numeric}

均值、中位数、P90与最大情景均值均先按情景聚合；“最大单次运行”另列，避免把二者混为一谈。查询数保留真实提前停止。尾部区间在 analysis/Table_R2_method_summary.csv 中。

## 预设主要配对比较

差值定义为“对照 regret − Proposed regret”（百分点），正值表示 Proposed 较优。

{table(pairs.reset_index(),['label','mean_paired_improvement_pp','mean_ci_low','mean_ci_high','proposed_wins','ties_by_empirical_epsilon','proposed_losses','holm_adjusted_sign_p'],['对照','平均配对差','95%CI下限','95%CI上限','Proposed胜','数值平局','Proposed负','Holm p'])}

英文解释原文：{interpretation}

只有置信区间下限大于零且预设 Holm 校正检验通过时，才在这一规则下称平均改善获支持。未通过不等于已证明等效，也不能临时更换检验或删情景。该比较评价完整方案，不能把全部差异归功于神经网络本身。P90 只作次要描述，30 个情景不足以稳定估计一般性尾部风险。

## 独立耗时上限结果

{timetable}

这是独立的清空状态缓存实验，不使用查询组的共享物理缓存耗时推算加速。每个情景的 Proposed 固定种子运行给出时间上限，其余方法在同一 CPU 上分别重新运行；末次 UE 求解若跨越截止时间，该值不进入搜索，实际超时保留。Proposed 这里只用一个参考种子，随机稳定性结论来自十种子查询组。训练和加载预热未计入，不声称训练成本已摊销。

## 新传入文件的作用与版本说明

历史 121–160 情景完整水深表已在老家目录找到，SHA256 与旧冻结记录一致，补齐了生成前的去重依据；仅作去重，从未在这些情景上优化。原 SA 脚本也已恢复，并在旧十情景上逐一验证目标、序列及查询数均与原源程序相同。此前工程批次 2001–2030 在读取比较结果前因 SA 实现依据变化而作废保留，正式批次另用冻结种子 2026102702 生成 3001–3030，未依据结果重选数据。

## 数值检查与解释边界

全部新表状态达到 RG≤10⁻⁹，主要选择路径再用 10⁻¹¹ 验证，最大 TSTT 相对变化 {refine:.8g}。经验等价系数 κ={eps:.12g} 在正式情景生成前固定，不是严格误差上界。旧十情景完整高精度复算中，DP 最优序列 10/10 不变，Proposed 中位/P90/最大变为 0.0383613%/0.4620987%/1.6909827%，旧 SA 为 0%/0.8160741%/3.5070691%。这些只作历史数值桥接，不并入新样本。

个别状态的 TSTT 相对变化高于开发阶段的观察值，因此追加核对了全部 1,620 条已选路径的序列目标。所有目标变化均在原冻结经验等价容差内，最大为该容差的 {precision['max_change_over_frozen_objective_epsilon']:.4f} 倍；没有据此改阈值、换序列或重调算法。单状态 TSTT 变化与整条序列目标误差不同，不能混为一个误差界。

UE-Beam 与双向版本是清楚标注的适配：没有复现 Gokalp 原文上下界、剪枝及自适应 beam，回复不能写“完整复现”。目前只检验同网络同合成生成机制上的新情景，并不验证跨城市或真实洪水泛化；十种子不覆盖代理重新训练随机性。

源码核对另确认：原文把最后两个汇总特征称为 remaining-closed flow/betweenness，但冻结实现按 initial_closed 计算。本次保留原实现和权重以维持比较一致，英文改稿材料提供了两处特征名称的准确替换；不能在新比较中悄悄改特征或重训。

## 本轮文件使用方法

先看本文件、analysis/Table_R2_method_summary.csv、analysis/Table_R3_primary_paired_comparisons.csv 和 Figure R2。英文替换段落与补充方法已依据真实结果生成，英文回复为 4.1 单条草稿。尚未整合进完整 Word 稿，未编造页码、行号或新 DOI；不将本地草稿称为可直接投稿的完整修回包。其余审稿意见仍需独立处理。
'''
    write('manuscript/4.1_返修结果与中文核对.md',chinese)
    original=(ROOT/'inputs/manuscript_baseline_extracted.txt').read_text(encoding='utf-8')
    oldabstract=original.split('\nAbstract\n',1)[1].split('\nKeywords:',1)[0]
    oldsa=next((line for line in original.splitlines() if line.startswith('The additional post-study permutation SA produced')), '')
    historicalreplacement='The archived ten-scenario study also included a post-study SA sensitivity analysis with one seed per scenario. Those historical results are retained as descriptive evidence; adaptive-comparator inference and search-seed conclusions now use the independently frozen revision experiment reported below.'
    write('manuscript/4.1_证据分配与段落整合记录.md',f'''# 4.1 证据分配与整合记录

This is a bounded revision draft with placeholders for final numbering and full Word integration. No red/clean full manuscript pair is claimed. Changed passages must be marked against the archived submission when integrated.

| Evidence | Function | Destination and reason |
| --- | --- | --- |
| Thirty new scenarios and the three prespecified adaptive comparisons | Core evidence | Main Results, Table R2 and concise paired estimates |
| Within-scenario ten-seed distributions | Necessary support and heterogeneity | Main Figure R2; cannot be replaced by one favorable seed |
| Any unsupported superiority claim or time-cap reversal | Conclusion-changing qualification | Main Abstract, Results, Discussion and Conclusion, regardless of direction |
| Full eight-method outcomes, threshold rates, seed extremes | Complete comparative record | Table R2 CSV and SI, all methods retained |
| Nested tail intervals and wins/ties/losses | Secondary precision and heterogeneity | SI/Table R3 with full data; main text treats P90 as secondary |
| 64/128 checkpoints | Descriptive anytime evidence | SI Figure R1; no claim of per-budget retuning |
| Fresh-cache timing group | Cost qualification | Main concise result; full Figure R4 and scope in SI |
| Original ten-scenario high-precision bridge | Numerical provenance | SI, not pooled with independent scenarios |
| Source recovery, hashes, all request events, backward DP audit | Reproducibility | Local source/data package and SI |

The shortest main-text chain is fresh scenario design → full-method quality against strong adaptive alternatives → paired uncertainty → seed and timing limits → bounded contribution. Full numerical repetition is routed to SI. The old long post-study SA interpretation is replaced rather than left to compete with the new conclusion. Original historical numbers remain clearly labelled and are not silently overwritten.

| Passage | Before words | After words | Action |
| --- | --- | --- | --- |
| Abstract | {len(oldabstract.split())} | {len(abstract.split())} | Replace using the fresh evidence |
| New independent revision Results | 0 | {len(mainresults.split())} | Add the central new comparison |
| Historical SA interpretation paragraph | {len(oldsa.split())} | {len(historicalreplacement.split())} | Compress; full historical evidence remains in archive/SI |

These are proposal-level text deltas, not a claim that the Word file has already been changed. Abstract introduces the bounded finding; Results demonstrates it; Discussion interprets complete-design versus component evidence; Conclusion states the limited contribution. The response's italic proposed conclusion is generated from the same text as the replacement passage so wording remains synchronized.
''')
    write('manuscript/4.1_交付状态.json',json.dumps({'readiness':'draft_with_placeholders','comment':'Reviewer 1 Comment 4.1',
        'experiments':'VERIFIED_DONE','statistics':'VERIFIED_DONE','replacement_passages':'DRAFT_SUPPLIED','response_draft':'DRAFT_SUPPLIED',
        'full_manuscript_integration':'NOT_YET_INTEGRATED','page_and_line_numbers':'NOT_ASSIGNED','repository_revision_doi':'NOT_PUBLISHED',
        'scope':'comment-level simulations and evidence-linked drafts; not a complete submission-ready revision'},ensure_ascii=False,indent=2))
    # Self-contained local browser reader; Markdown remains the editable authority.
    pieces=[];paragraph=[];intable=False
    def flush():
        if paragraph:pieces.append('<p>'+html.escape(' '.join(paragraph))+'</p>');paragraph.clear()
    for line in chinese.splitlines():
        if intable and not line.startswith('|'):pieces.append('</tbody></table></div>');intable=False
        if line.startswith('|'):
            flush();cells=[html.escape(x.strip()) for x in line.strip('|').split('|')]
            if all(set(c)<=set('-: ') for c in cells):continue
            if not intable:
                pieces.append('<div class="table"><table><thead><tr>'+''.join('<th>'+c+'</th>' for c in cells)+'</tr></thead><tbody>');intable=True
            else:pieces.append('<tr>'+''.join('<td>'+c+'</td>' for c in cells)+'</tr>')
        elif line.startswith('#'):
            flush();level=min(3,len(line)-len(line.lstrip('#')));pieces.append(f'<h{level}>'+html.escape(line.lstrip('# '))+f'</h{level}>')
        elif not line.strip():flush()
        else:paragraph.append(line)
    flush()
    if intable:pieces.append('</tbody></table></div>')
    write('00_4.1结果阅读入口.html','<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>4.1 返修结果</title><style>body{font:16px/1.7 "Microsoft YaHei",sans-serif;max-width:1150px;margin:40px auto;padding:0 24px;color:#202124}h1,h2{line-height:1.3}img{max-width:100%}a{color:#0067a0}.table{overflow-x:auto}table{border-collapse:collapse;font-size:13px;width:100%;font-variant-numeric:tabular-nums}th,td{border:1px solid #d9d9d9;padding:7px 9px;text-align:right}th{background:#eff3f6}td:first-child,th:first-child{text-align:left}</style><body><p><a href="analysis/Table_R2_method_summary.csv">完整统计 CSV</a> · <a href="manuscript/Reviewer1_4.1_Response_英文草稿.md">英文回复草稿</a> · <a href="README_复现与文件说明.md">复现说明</a></p>'+''.join(pieces)+''.join(f'<h2>{name}</h2><img alt="{name}" src="figures/{name}.png">' for name in ['Figure_R1_anytime','Figure_R2_seed_variability','Figure_R3_paired_effects','Figure_R4a_queries_and_time','Figure_R4b_time_capped_quality'])+'</body></html>')
    print('Created evidence-linked Chinese report, English response draft, replacement passages and supplement.')

if __name__=='__main__':main()
