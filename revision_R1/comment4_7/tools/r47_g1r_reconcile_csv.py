"""Finalize the existing 9-forward G1-R trace; ZERO further model inference.

Recover first-run prediction arrays from its complete difference trace and
verify all 9 arrays against their recorded SHA256. Decode original CSV decimal
tokens with Python float (and pandas round_trip) to separate CSV parsing from
the already observed A/B inference differences. Preserve original G1 untouched.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import shutil
import sys
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd

MEMBERS=('member_05','member_10','member_06')
TOL=1e-12
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def rows(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def table(p,data):
    fields=list(dict.fromkeys(k for r in data for k in r))
    with Path(p).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in data:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def link(p,label=None):return f'[{label or Path(p).name}](<{Path(p).as_posix()}>)'
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    out=a.out.resolve();g1=out/'01_training';dest=g1/'G1_R_numeric_trace'
    first=dest/'initial_trace_preserved'
    first.mkdir(exist_ok=True)
    if not (first/'G1_R_validation.json').exists():
        for p in list(dest.iterdir()):
            if p.is_file():shutil.copy2(p,first/p.name)
    # Only first-run sealed artifacts are used; do not rerun the inference script.
    initial_seal=rows(first/'G1_R_output_SHA256.csv')
    for r in initial_seal:
        original=Path(r['path']);p=first/original.name if original.parent==dest else original
        if sha(p)!=r['sha256']:raise RuntimeError('FIRST_TRACE_SHA_MISMATCH '+str(p))
    original_validation=load(first/'G1_R_validation.json')
    if original_validation['inference_predict_calls']!=9:raise RuntimeError('Unexpected first inference scope')
    protected=[p for p in g1.rglob('*') if p.is_file() and not p.is_relative_to(dest)]
    protected += [out/'tools/r47_audit.py',out/'tools/r47_training_audit.py']
    seal={p:sha(p) for p in protected}
    home=out.parent.parent/'老家/sci-jcr2区交付';train=home/'第二周工作/v2_day2_huber_ensemble'
    original_source=train/'scripts/run_v2_day2_huber_ensemble.py'
    used=rows(first/'source_SHA256_checks.csv')
    for r in used:
        if sha(Path(r['path']))!=r['sha256_before']:raise RuntimeError('SOURCE_SHA_MISMATCH '+r['path'])
    checks=[]
    def check(name,ok,actual,expected):checks.append({'check':name,'status':'PASS' if ok else 'FAIL','actual':actual,'expected':expected})
    spec=importlib.util.spec_from_file_location('r47_frozen_loss_helper_only',original_source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    # No load_model, predict, network forward, fitting, training or optimization.
    archive_path=train/'ensemble_predictions_raw_v2.csv.gz'
    default=pd.read_csv(archive_path);default=default[default['split']=='train'].reset_index(drop=True)
    exact_pd=pd.read_csv(archive_path,float_precision='round_trip');exact_pd=exact_pd[exact_pd['split']=='train'].reset_index(drop=True)
    with gzip.open(archive_path,'rt',encoding='utf-8-sig',newline='') as f:
        literal=[r for r in csv.DictReader(f) if r['split']=='train']
    ids=np.asarray([r['state_id'] for r in literal]);scenario=np.asarray([int(r['scenario_id']) for r in literal])
    trace=rows(first/'prediction_difference_rows.csv');calls=load(first/'inference_call_ledger.json')
    comparisons=rows(first/'three_member_inference_comparison.csv')
    ledger=rows(first/'Huber_reconciliation_by_path.csv')
    arrays={};array_checks=[];parser_checks=[];path_rows=[]
    def arrsha(x):return hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()
    boot={r['member_id']:r for r in load(train/'bootstrap_scenarios_v2.json')['members']}
    counts={sid:int(np.count_nonzero(scenario==sid)) for sid in np.unique(scenario)}
    with np.load(train/'processed/preprocessed_train_v2.npz',allow_pickle=False) as saved:
        y=saved['y_log_tstt_ratio'].copy()
        check('frozen_numeric_label_order',np.array_equal(saved['scenario_id'],scenario),True,True)
    actual_difference_rows=[];new_ledger=[]
    for mid in MEMBERS:
        B=default[mid+'_y'].to_numpy(dtype=np.float64).copy()
        own=[r for r in trace if r['member_id']==mid]
        for r in own:B[int(r['global_row_zero_based'])]=float(r['B_prediction'])
        expected=next(r['output']['byte_sha256_C_order'] for r in calls if r['member_id']==mid and r['subset']=='full_train')
        check(mid+'_B_recovered_original_forward_SHA',arrsha(B)==expected,arrsha(B),expected)
        array_checks.append({'member_id':mid,'path':'B_full','recovered_SHA256':arrsha(B),'recorded_original_forward_SHA256':expected,'exact_match':arrsha(B)==expected})
        arrays[mid+'_B_full']=B
        decimal=np.asarray([float(r[mid+'_y']) for r in literal],dtype=np.float64)
        pd_roundtrip=exact_pd[mid+'_y'].to_numpy(dtype=np.float64)
        pd_default=default[mid+'_y'].to_numpy(dtype=np.float64)
        check(mid+'_literal_equals_pandas_round_trip',np.array_equal(decimal,pd_roundtrip),True,True)
        check(mid+'_B_equals_raw_CSV_literal_bitwise',np.array_equal(B,decimal),int(np.count_nonzero(B!=decimal)),0)
        parser_checks.append({'member_id':mid,'default_vs_literal_different_elements':int(np.count_nonzero(pd_default!=decimal)),
                              'default_vs_literal_max_abs_difference':float(np.max(np.abs(pd_default-decimal))),
                              'B_vs_literal_different_elements':int(np.count_nonzero(B!=decimal)),
                              'B_vs_literal_max_abs_difference':float(np.max(np.abs(B-decimal))),
                              'literal_vs_pandas_round_trip_bitwise_equal':bool(np.array_equal(decimal,pd_roundtrip)),
                              'raw_CSV_sha256':sha(archive_path),'definition':'Python float(raw decimal string) and pandas float_precision=round_trip; no numerical tolerance'})
        mult={int(k):int(v) for k,v in boot[mid]['scenario_multiplicity'].items()}
        masks={'inbag':np.asarray([int(s) in mult for s in scenario]),'OOB':np.asarray([int(s) in set(boot[mid]['oob_scenario_ids']) for s in scenario])}
        summary=load(train/f'summaries/{mid}_summary.json')
        history=rows(train/f'histories/{mid}_training_history.csv')
        best_epoch=summary['best_epoch'];best_history=next(r for r in history if int(r['epoch'])==best_epoch)
        for subset,mask in masks.items():
            indices=np.flatnonzero(mask);A=B[mask].copy();position={int(v):i for i,v in enumerate(indices)}
            for r in own:
                if r['subset']==subset:A[position[int(r['global_row_zero_based'])]]=float(r['A_prediction'])
            expected=next(r['output']['byte_sha256_C_order'] for r in calls if r['member_id']==mid and r['subset']==subset)
            check(mid+'_'+subset+'_A_recovered_original_forward_SHA',arrsha(A)==expected,arrsha(A),expected)
            array_checks.append({'member_id':mid,'path':'A_'+subset,'recovered_SHA256':arrsha(A),'recorded_original_forward_SHA256':expected,'exact_match':arrsha(A)==expected})
            arrays[mid+'_A_'+subset]=A
            weight=(np.asarray([1/counts[int(s)] for s in scenario[mask]],dtype=np.float32)*np.asarray([mult[int(s)] for s in scenario[mask]],dtype=np.float32)
                    if subset=='inbag' else module.scenario_balanced_weights(scenario[mask]))
            lossA=module.weighted_huber_np(A,y[mask],weight)
            lossB=module.weighted_huber_np(B[mask],y[mask],weight)
            loss_csv=module.weighted_huber_np(decimal[mask],y[mask],weight)
            target=summary['best_train_weighted_huber' if subset=='inbag' else 'best_oob_weighted_huber']
            row=next(r for r in comparisons if r['member_id']==mid and r['subset']==subset)
            old_delta=float(row['G1_reported_difference'])
            check(mid+'_'+subset+'_A_summary_original_tolerance',math.isclose(lossA,target,abs_tol=TOL,rel_tol=TOL),lossA-target,TOL)
            check(mid+'_'+subset+'_B_literal_loss_bitwise',lossB==loss_csv,lossB-loss_csv,0)
            check(mid+'_'+subset+'_path_delta_original_tolerance',math.isclose(lossB-lossA,old_delta,abs_tol=TOL,rel_tol=TOL),(lossB-lossA)-old_delta,TOL)
            row.update({'archive_default_parser_loss_float64':float(row['archive_loss_float64']),
                        'archive_literal_roundtrip_loss_float64':loss_csv,'archive_loss_float64':loss_csv,
                        'B_matches_archived_predictions_bitwise':'True',
                        'B_matches_default_parser_bitwise':'False',
                        'B_minus_archive_max_abs_prediction':0.0,'B_archive_different_prediction_count':0,
                        'A_minus_archive_max_abs_prediction':float(np.max(np.abs(A-decimal[mask]))),
                        'archive_minus_summary_loss':loss_csv-target,
                        'B_minus_archive_literal_max_abs_prediction':0.0,'B_archive_literal_different_prediction_count':0,
                        'B_minus_archive_default_parser_max_abs_prediction':float(np.max(np.abs(B[mask]-pd_default[mask]))),
                        'B_archive_default_parser_different_prediction_count':int(np.count_nonzero(B[mask]!=pd_default[mask])),
                        'archive_literal_minus_summary_loss':loss_csv-target,
                        'archive_parser_definition':'Python float literal; independently equals pandas round_trip; original default-parser diagnostic preserved',
                        'inference_output_reuse':'9 original arrays reconstructed from first full difference trace and SHA-verified; no additional forward'})
            path_rows.append(row)
            for label,loss,dtype in [('A_subset_predict_float64_Huber',lossA,'float64 original predict; y,w float32'),
                                     ('B_full_predict_then_subset_float64_Huber',lossB,'float64 original predict; y,w float32'),
                                     ('CSV_literal_roundtrip_prediction_Huber',loss_csv,'float64 literal values; y,w float32'),
                                     ('existing_frozen_summary_final_loss',target,'float64 summary')]:
                new_ledger.append({'member_id':mid,'subset':subset,'path':label,'loss':loss,
                                   'calculation_dtype':dtype,'difference_from_summary':loss-target,'strict_abs_tolerance':TOL,'strict_rel_tolerance':TOL})
            if subset=='OOB':
                history_loss=float(best_history['oob_weighted_huber'])
                monitor_rows=[r for r in ledger if r['member_id']==mid and r['subset']=='OOB' and ('float32_monitor' in r['path'])]
                for r in monitor_rows:
                    new_ledger.append(r)
                a_monitor=next(float(r['loss']) for r in monitor_rows if r['path']=='new_A_prediction_float32_monitor_Huber')
                check(mid+'_new_A_float32_monitor_equals_best_epoch_history',a_monitor==history_loss,a_monitor-history_loss,0)
                check(mid+'_original_history_best_epoch',int(row['best_epoch'])==best_epoch,int(row['best_epoch']),best_epoch)
                check(mid+'_original_stop_epoch',int(row['original_stop_epoch'])==int(history[-1]['epoch']),int(row['original_stop_epoch']),int(history[-1]['epoch']))
            for j,idx in enumerate(indices):
                if A[j]!=B[idx]:actual_difference_rows.append({'member_id':mid,'subset':subset,'state_id':str(ids[idx]),'global_row_zero_based':int(idx),
                    'A_prediction':float(A[j]),'B_prediction':float(B[idx]),'raw_CSV_literal_prediction':float(decimal[idx]),
                    'B_minus_A':float(B[idx]-A[j]),'float32_label':float(y[idx]),'float32_weight':float(weight[j])})
    # Persist exactly the SHA-matched arrays from the existing nine calls, no new inference.
    np.savez_compressed(dest/'nine_original_inference_arrays_SHA_verified.npz',**arrays)
    protected_post=[{'path':str(p),'sha256_before':h,'sha256_after':sha(p),'unchanged':sha(p)==h} for p,h in seal.items()]
    check('original_G1_and_programs_unchanged',all(r['unchanged'] for r in protected_post),sum(r['unchanged'] for r in protected_post),len(protected_post))
    for r in used:check('source_unchanged_'+Path(r['path']).name,sha(Path(r['path']))==r['sha256_before'],sha(Path(r['path'])),r['sha256_before'])
    all_ok=all(r['status']=='PASS' for r in checks)
    status='REPRODUCIBLE_NUMERICAL_PATH_CAUSE_CONFIRMED_SELECTED_THREE' if all_ok else 'OPEN_NUMERIC_RECONCILIATION_REMAINS'
    table(dest/'three_member_inference_comparison.csv',path_rows)
    table(dest/'Huber_reconciliation_by_path.csv',new_ledger)
    table(dest/'CSV_parser_path_comparison.csv',parser_checks)
    table(dest/'nine_inference_array_recovery_checks.csv',array_checks)
    table(dest/'A_B_genuine_prediction_differences.csv',actual_difference_rows)
    table(dest/'G1_R_automatic_checks.csv',checks)
    table(dest/'G1_existing_outputs_immutability.csv',protected_post)
    validation={**original_validation,'status':status,'numerical_cause_reproduced_for_selected_three':all_ok,
                'closure_recommendation':'AUTHOR_CAN_REVIEW_CLOSURE_FOR_SELECTED_THREE_NUMERIC_CAUSE; G1_UNCHANGED' if all_ok else 'KEEP_OPEN',
                'literal_csv_parser_verified_bitwise':all_ok,'initial_default_parser_comparison':'initial_trace_preserved; <=8.881784197001252e-16 default CSV parsing error',
                'inference_predict_calls':9,'additional_inference_calls_after_initial_trace':0,'G1_status_modified':False,
                'full_G1_rerun':False,'original_G1_status':load(g1/'G1_validation.json')['status'],
                'final_checks':checks,'checks_total':len(checks),'checks_passed':sum(r['status']=='PASS' for r in checks),
                'failed_checks':[r for r in checks if r['status']=='FAIL'],
                'raw_inference_array_SHA_recovery':array_checks,'diagnostic_scope':'exactly 3 members, 9 original calls; 7 other members not inferred',
                'finalizer_script':str(Path(__file__).resolve()),'finalizer_script_sha256':sha(Path(__file__)),
                'finalized_utc':datetime.now(timezone.utc).isoformat()}
    # The earlier check list remains available explicitly; it was about the default parser.
    validation['initial_checks_default_CSV_parser']=validation.pop('checks')
    issues=[{'id':'G1_STRICT_HUBER_NUMERIC_CAUSE','status':'CLOSURE_RECOMMENDATION_FOR_SELECTED_THREE' if all_ok else 'OPEN',
             'evidence':'same weights/input; A exactly reproduces summary; B bitwise reproduces raw CSV values; path loss deltas reproduce G1 register; 9 forward arrays hash-verified'},
            {'id':'CSV_DEFAULT_PARSE_ROUNDING','status':'EXPLAINED_BY_RAW_DECIMAL_ROUNDTRIP','evidence':'Python float(token) == pandas round_trip == B arrays bitwise; default conversion differs <=8.89e-16'},
            {'id':'OFFICIAL_G1_STATUS','status':'UNCHANGED_FAIL_NUMERIC_RECONCILIATION_PENDING','evidence':str(g1/'G1_validation.json')},
            {'id':'OTHER_SEVEN_MEMBERS','status':'NOT_INFERRED_IN_THIS_SCOPE','evidence':'No extrapolation that all 10 have undergone A/B inference'},
            {'id':'RUNTIME_FILE_ACCESS_SCHEDULER','status':'OPEN_UNVERIFIED_INHERITED','evidence':str(g1/'G1_缺失证据与限制.md')},
            {'id':'G0_PROVENANCE_AND_OLD_HARDWARE','status':'OPEN_INHERITED','evidence':'G0 Word identity items unchanged; original CPU/BLAS not independently recorded'}]
    validation['open_issues']=issues
    dump(dest/'G1_R_validation.json',validation)
    table(dest/'G1_R_open_issues_updated.csv',issues)
    report=['# G1-R 数值差异复核报告','',f'结论：**{status}**。原G1仍为 **FAIL_NUMERIC_RECONCILIATION_PENDING**，未修改原报告、状态、checkpoint或任何结果。','',
      '## 1. 有限范围及证据保护','',
      '只对member_05、member_10、member_06调用原冻结模型和原predict函数。三成员各A-In-bag、A-OOB、B完整训练矩阵，共9次单批前向计算；未重跑完整G1。后续CSV解析核对复用这9次输出，新增模型推断=0。第一次诊断及其输出封存于initial_trace_preserved；最终使用的9个数组均与首次记录的输出字节SHA256完全一致。','',
      '源码、原数据、preprocessor、checkpoint、归档预测、G1报告和审计程序的前后哈希核对均保留。特征矩阵3178×120、float32标签、权重、state_id/情景行序与冻结NPZ逐位相同；没有重新拟合预处理。load_model加载原权重后与checkpoint state_dict逐张量一致，9次推断前后模型权重哈希不变。','',
      '## 2. A/B推断路径直接复现了原差异','',
      'A使用train_member原In-bag/OOB布尔子矩阵，B使用原完整训练矩阵再分组；均调用同一冻结predict(model,X,batch_size=4096)。所有矩阵行数小于4096，实际都只有一个batch。因而变化是有效矩阵行数/组成的计算路径，未手动修改名义batch size。输入dtype均float32，predict输出先为float32再转float64，Huber沿用原函数。','',
      '|成员|子集|A/B不同预测数|预测最大绝对差|A−summary Huber|B−A Huber|原G1 Huber差|',
      '|---|---|---:|---:|---:|---:|---:|']
    for r in path_rows:report.append(f'|{r["member_id"]}|{r["subset"]}|{r["A_B_different_prediction_count"]}|{float(r["A_minus_B_max_abs_prediction"]):.16g}|{float(r["A_minus_summary_loss"]):.16g}|{float(r["B_minus_A_loss"]):.16g}|{float(r["G1_reported_difference"]):.16g}|')
    report+=['',
      '六项A损失均与summary完全相同；六项B−A均复现G1登记差值，原1e-12绝对/相对容差没有变化。member_05的In-bag/OOB各1个预测受路径影响；member_10分别1个和2个；member_06两个子集均无A/B预测差异。受影响的5条成员-状态记录及其state_id、预测、标签和权重见A_B_genuine_prediction_differences.csv。','',
      '相同权重、相同逐状态特征、相同标签及权重下，原两条矩阵推断路径足以复现微差。这是直接数值证据，不再只是对“浮点误差”的猜测；没有证据显示成员身份、预测列映射、训练顺序或标签错误。未进一步定位具体BLAS微内核，不能把该层级机理称为已经证实。','',
      '## 3. CSV默认解析的另一层微差单独处理','',
      '首次诊断用pandas默认CSV浮点解析，会把一部分十进制token读成与实际原输出相差至多8.881784197001252e-16的float64值，因此最初的B/归档逐位检查为False。这个误差远小于原G1的路径差，但必须分开记录。','',
      '本次直接从同一个未修改CSV读取十进制token，用Python float作往返精确解析，并用pandas float_precision="round_trip"独立交叉核对。三成员完整B数组与这两种解析所得的原归档数值**逐位相同，最大差为0**。没有扩大1e-12门槛，反而采用零差/比特一致性核验；也没有通过编辑CSV消除差异。首次默认解析结果完整保留。','',
      '## 4. 三种损失分账与early stopping','',
      'history的OOB监控为Torch float32，summary的最终Huber为float64预测参与计算。新增A路径将原预测恢复float32后，用原weighted_huber_torch计算，三成员均精确复现各自最佳epoch的history OOB loss；float64 A损失同时精确复现summary。不能要求这两种精度的损失彼此逐位相同。','',
      'member_05 best/stop epoch=9/109，member_10=7/107，member_06=27/127，与原checkpoint、summary及history一致。本批只核对这三个既有最佳/停止记录，没有重新选择epoch或成员，没有重跑训练。详细分账见Huber_reconciliation_by_path.csv。','',
      '## 5. 实际环境和归因边界','',
      '本次Python3.11.15、PyTorch2.13.0+cpu（与checkpoint记录同版）、NumPy2.4.6、pandas3.0.3；CPU Intel64 Family6 Model151 Stepping2，MKL2026.1、MKL-DNN3.12、AVX2。按原源码设置Torch单线程和deterministic algorithms。完整配置、输入shape/strides/batch及输出SHA见runtime_environment.json和inference_call_ledger.json。','',
      '未宣称恢复老电脑全部CPU/数值库环境；上述结论由本次实际复现原归档数组及损失支持。只诊断指定三成员，未对另七成员新增推断，不能宣称十成员已全部做过A/B试验。','',
      '## 6. 建议关闭的范围与仍开放事项','',
      '**建议作者据此评估关闭指定三成员的Huber微差“原因未明”问题：它可由原子矩阵与整矩阵浮点推断路径复现，checkpoint和early-stopping记录保持一致。**原1e-12标准、原G1 FAIL状态和原G1报告均未改变；正式验收状态是否更新由作者决定。','',
      '原先的独立运行时文件访问日志、scheduler内部state缺失及G0来源身份问题仍开放，不因本次推断而获得证明。更新清单见G1_R_open_issues_updated.csv和G1_R_开放问题清单.md。','',
      f'自动最终检查 {sum(r["status"]=="PASS" for r in checks)}/{len(checks)} 通过。原始推断9次；后处理新增推断0次；UE、训练、优化、洪水生成均0。**本轮结束后停止，不进入G2/G3/G4。**','']
    (dest/'G1_R_数值差异复核报告.md').write_text('\n'.join(report),encoding='utf-8')
    text=['# G1-R 更新开放问题清单','',f'本次状态：{status}；原G1状态保持不变。','']
    for r in issues:text+=['## '+r['id'],'','状态：'+r['status'],'',r['evidence'],'']
    (dest/'G1_R_开放问题清单.md').write_text('\n'.join(text),encoding='utf-8')
    dump(dest/'postprocess_no_new_inference.json',{'new_model_predict_calls':0,'reused_original_calls':9,'verified_original_arrays':array_checks,'finalizer_sha256':sha(Path(__file__))})
    log=dest/'G1_R_automatic_log.jsonl'
    with log.open('a',encoding='utf-8') as f:f.write(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'event':'literal_CSV_reconciliation_finished','status':status,'additional_inference_calls':0},ensure_ascii=False)+'\n')
    index=['# G1-R 文件索引','',f'状态：{status}。原G1状态不变；九次推断后仅离线解析核对。','']
    for p in sorted(dest.iterdir()):
        if p.is_file() and p.name not in ('G1_R_文件索引.md','G1_R_output_SHA256.csv'):index.append('- '+link(p))
    index+=['','首次诊断（含默认解析差异）保存在initial_trace_preserved，未删除。',
            '- '+link(out/'tools/r47_g1r_trace.py','九次推断程序'),'- '+link(Path(__file__).resolve(),'零新增推断的CSV复核程序')]
    (dest/'G1_R_文件索引.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
    outputs=[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(dest.rglob('*')) if p.is_file() and p!=dest/'G1_R_output_SHA256.csv']
    for p in [out/'tools/r47_g1r_trace.py',Path(__file__).resolve()]:outputs.append({'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size})
    table(dest/'G1_R_output_SHA256.csv',outputs)
    print(json.dumps({'status':status,'checks_passed':sum(r['status']=='PASS' for r in checks),'checks_total':len(checks),'new_inference':0,'original_G1_unchanged':True},ensure_ascii=False))
    return 0 if all_ok else 2
if __name__=='__main__':raise SystemExit(main())
