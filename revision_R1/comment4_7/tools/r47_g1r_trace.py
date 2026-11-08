"""Bounded G1-R: exactly 3 frozen members, A-subset/B-full read-only inference.

Never imports or runs the full G1 audit. Original module is imported under a
non-main name, and only load_raw/transform/load_model/predict/Huber helpers run.
No fitting, optimization, scenario generation, UE, parameter update, or original
artifact writing. Output is confined to 01_training/G1_R_numeric_trace.
"""
from __future__ import annotations
import argparse
import ast
import csv
import hashlib
import importlib.util
import inspect
import json
import math
import os
import platform
import sys
import time
import traceback
from datetime import datetime,timezone
from pathlib import Path

MEMBERS=('member_05','member_10','member_06')
TOL=1e-12

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def rows(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def dump(p,data):Path(p).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def table(p,data,fields=None):
    fields=fields or list(dict.fromkeys(k for r in data for k in r))
    with Path(p).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in data:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict,tuple)) else v for k,v in r.items()})

def link(p,label=None,line=None):return f'[{label or Path(p).name}](<{Path(p).as_posix()}{":"+str(line) if line else ""}>)'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    out=args.out.resolve();g1=out/'01_training';g0=out/'00_audit'
    dest=g1/'G1_R_numeric_trace';dest.mkdir(parents=True,exist_ok=True)
    home=out.parent.parent/'老家/sci-jcr2区交付'
    train=home/'第二周工作/v2_day2_huber_ensemble'
    training_source=train/'scripts/run_v2_day2_huber_ensemble.py'
    original_csv=home/'第二周工作/day1_freeze_preprocess/week1_recovery_dataset_v1.0/recovery_states_train.csv'
    expanded_csv=home/'第二周工作/v2_day1_training_expansion/recovery/v2_new_training_states.csv.gz'
    preprocessor_path=train/'preprocessor_v2.json'
    archived_path=train/'ensemble_predictions_raw_v2.csv.gz'
    npz_path=train/'processed/preprocessed_train_v2.npz'
    start=time.perf_counter();events=[];checks=[];inputs={};inference_calls=[]
    comparisons=[];ledger=[];diff_rows=[];issues=[];source_locations=[]
    def log(event,**data):
        r={'utc':datetime.now(timezone.utc).isoformat(),'event':event,**data};events.append(r)
        print(json.dumps(r,ensure_ascii=False),flush=True)
        (dest/'G1_R_automatic_log.jsonl').write_text('\n'.join(json.dumps(v,ensure_ascii=False) for v in events)+'\n',encoding='utf-8')
    def check(name,ok,observed,expected,kind='integrity',detail=''):
        checks.append({'check':name,'status':'PASS' if ok else 'FAIL','kind':kind,'observed':observed,'expected':expected,'detail':detail})
    frozen={str(Path(r['path']).resolve()):r['sha256'] for r in rows(g0/'source_manifest.csv')}
    g1_seal={str(Path(r['path']).resolve()):r['sha256'] for r in rows(g1/'G1_output_sha256.csv')}
    protected=[p for p in g1.rglob('*') if p.is_file() and not p.is_relative_to(dest)]
    protected += [out/'tools/r47_training_audit.py',out/'tools/r47_audit.py']
    protected_before={p:sha(p) for p in protected}
    def use(p,role,expected=None):
        p=Path(p).resolve();actual=sha(p)
        expected=expected or frozen.get(str(p)) or g1_seal.get(str(p))
        inputs[p]={'path':str(p),'role':role,'sha256_before':actual,'expected_sha256':expected or '',
                   'matches_frozen_expected':actual==expected if expected else 'CURRENT_READONLY_REFERENCE'}
        if expected and actual!=expected:raise RuntimeError('SOURCE_SHA_MISMATCH '+str(p))
        return p
    def location(function):
        lines,n=inspect.getsourcelines(function)
        source_locations.append({'symbol':function.__qualname__,'path':str(training_source),'line':n,'end_line':n+len(lines)-1,'sha256':sha(training_source)})
        return link(training_source,function.__qualname__,n)
    log('start',members=list(MEMBERS),G1_status_unchanged=load(g1/'G1_validation.json')['status'])
    env={}
    fatal=None
    try:
        use(g0/'source_manifest.csv','G0_source_index')
        use(g1/'G1_output_sha256.csv','accepted_G1_output_seal')
        for p in [g1/'numeric_discrepancy_register.csv',g1/'member_OOB_early_stopping_audit.csv',
                  g1/'G1_validation.json',g1/'G1_中文验收报告.md',g1/'G1_unverified_evidence.csv',
                  g1/'G1_缺失证据与限制.md',training_source,original_csv,expanded_csv,
                  preprocessor_path,archived_path,npz_path,train/'bootstrap_scenarios_v2.json',train/'ensemble_training_config_v2.json']:
            use(p,'frozen_diagnostic_input')
        discrepancies=rows(g1/'numeric_discrepancy_register.csv')
        audits={r['member_id']:r for r in rows(g1/'member_OOB_early_stopping_audit.csv')}
        for mid in MEMBERS:
            for p in [train/f'models/{mid}.pt',train/f'summaries/{mid}_summary.json',train/f'histories/{mid}_training_history.csv']:
                use(p,'selected_original_member_asset')
            recorded=next(r for r in discrepancies if r['member_id']==mid)
            check(mid+'_checkpoint_G1_register_SHA',sha(train/f'models/{mid}.pt')==recorded['checkpoint_sha256'],sha(train/f'models/{mid}.pt'),recorded['checkpoint_sha256'])
        # No G1 script is imported. No training function is called.
        import numpy as np
        import pandas as pd
        import torch
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        spec=importlib.util.spec_from_file_location('r47_frozen_training_READONLY_DIAGNOSTIC',training_source)
        frozen_module=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=frozen_module
        spec.loader.exec_module(frozen_module)
        m=frozen_module
        predict_location=location(m.predict);transform_location=location(m.transform)
        huber_np_location=location(m.weighted_huber_np);huber_torch_location=location(m.weighted_huber_torch)
        load_model_location=location(m.load_model)
        env={'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'CPU':platform.processor(),
             'torch':str(torch.__version__),'numpy':np.__version__,'pandas':pd.__version__,
             'torch_num_threads':torch.get_num_threads(),'torch_num_interop_threads':torch.get_num_interop_threads(),
             'torch_deterministic_algorithms':torch.are_deterministic_algorithms_enabled(),
             'mkldnn_enabled':torch.backends.mkldnn.enabled,'device':'cpu','CUDA_used':False,
             'torch_build':torch.__config__.show(),'parallel_info':torch.__config__.parallel_info(),
             'environment':{k:os.environ.get(k) for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','CUDA_VISIBLE_DEVICES']},
             'module_imported_as':spec.name,'frozen_main_called':False,
             'predict_default_batch_size':inspect.signature(m.predict).parameters['batch_size'].default,
             'historical_environment_limit':'checkpoint records torch version; historical CPU/BLAS and NumPy/Pandas versions not independently logged'}
        dump(dest/'runtime_environment.json',env)
        pre=load(preprocessor_path)
        # Same frozen CSV reader, transform, preprocessing constants and feature order.
        frame=pd.concat([m.load_raw(original_csv),m.load_raw(expanded_csv)],ignore_index=True,sort=False)
        ids=frame['state_id'].astype(str).to_numpy()
        scenario=frame['scenario_id'].to_numpy(dtype=int)
        X=m.transform(frame,pre,np.asarray(pre['baseline_flow'],dtype=np.float64),np.asarray(pre['betweenness'],dtype=np.float64))
        y=frame['log_tstt_ratio'].to_numpy(dtype=np.float32)
        base_weight=m.scenario_balanced_weights(scenario)
        with np.load(npz_path,allow_pickle=True) as saved:
            identity_checks={'state_ID_order':np.array_equal(ids,saved['state_id']),
                             'scenario_order':np.array_equal(scenario,saved['scenario_id']),
                             'feature_values_bitwise':np.array_equal(X,saved['X']),
                             'float32_labels_bitwise':np.array_equal(y,saved['y_log_tstt_ratio']),
                             'base_weights_bitwise':np.array_equal(base_weight,saved['sample_weight'])}
            X_diff_max=float(np.max(np.abs(X-saved['X'])))
            X_saved_info={'shape':list(saved['X'].shape),'dtype':str(saved['X'].dtype),'strides':list(saved['X'].strides)}
        for key,ok in identity_checks.items():check('input_'+key,bool(ok),bool(ok),True)
        check('input_3178_by_120',X.shape==(3178,120),list(X.shape),[3178,120])
        archive=pd.read_csv(archived_path)
        archive=archive[archive['split']=='train'].reset_index(drop=True)
        check('archive_ID_unique',not archive['state_id'].duplicated().any(),int(archive['state_id'].nunique()),3178)
        check('archive_ID_order',np.array_equal(ids,archive['state_id'].astype(str).to_numpy()),'raw/NPZ/archive order','exact same')
        check('archive_float32_label_mapping',np.array_equal(y,archive['true_y_log_ratio'].to_numpy(dtype=np.float32)),True,True)
        if any(c['status']=='FAIL' for c in checks):raise RuntimeError('CRITICAL_INPUT_OR_SOURCE_IDENTITY_MISMATCH; no inference started')
        bootstrap={r['member_id']:r for r in load(train/'bootstrap_scenarios_v2.json')['members']}
        def arrsha(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
        def description(a):
            return {'shape':list(a.shape),'dtype':str(a.dtype),'strides':list(a.strides),
                    'C_contiguous':bool(a.flags.c_contiguous),'F_contiguous':bool(a.flags.f_contiguous),
                    'byte_sha256_C_order':arrsha(a)}
        dump(dest/'input_matrix_identity.json',{'checks':identity_checks,'fresh_vs_saved_feature_max_abs_difference':X_diff_max,
             'fresh_X':description(X),'saved_X':X_saved_info,'labels':description(y),'base_weight':description(base_weight),
             'state_ID_order_sha256':hashlib.sha256('\n'.join(ids).encode()).hexdigest(),
             'preprocessor_sha256':sha(preprocessor_path),'source_transform':transform_location})
        def compare(a,b):
            d=a-b
            return {'bitwise_equal':bool(np.array_equal(a,b)), 'different_elements':int(np.count_nonzero(a!=b)),
                    'max_absolute_difference':float(np.max(np.abs(d))), 'mean_absolute_difference':float(np.mean(np.abs(d))),
                    'signed_difference_min':float(d.min()),'signed_difference_max':float(d.max())}
        def run_predict(mid,model,path,subset,inputs_array,indices):
            before={k:arrsha(v.detach().cpu().numpy()) for k,v in model.state_dict().items()}
            result=m.predict(model,inputs_array)  # exact original implementation, default batch_size=4096
            after={k:arrsha(v.detach().cpu().numpy()) for k,v in model.state_dict().items()}
            if before!=after:raise RuntimeError('CRITICAL_MODEL_WEIGHT_MUTATED_DURING_INFERENCE')
            inference_calls.append({'member_id':mid,'path':path,'subset':subset,'input':description(inputs_array),
                                    'state_ID_order_sha256':hashlib.sha256('\n'.join(ids[indices]).encode()).hexdigest(),
                                    'nominal_batch_size':4096,'actual_batch_rows':[len(inputs_array)],
                                    'output':description(result),'model_weights_unchanged':before==after,
                                    'source_predict':predict_location})
            return result
        for mid in MEMBERS:
            original=load(train/f'summaries/{mid}_summary.json')
            model,checkpoint=m.load_model(train/f'models/{mid}.pt')
            model.eval()
            model_identity=(checkpoint['member_id']==mid and checkpoint['best_epoch']==original['best_epoch']
                            and checkpoint['preprocessor_sha256']==sha(preprocessor_path)
                            and all(torch.equal(v,model.state_dict()[k]) for k,v in checkpoint['state_dict'].items())
                            and sha(train/f'models/{mid}.pt')==original['model_hash_sha256'])
            check(mid+'_model_checkpoint_identity',model_identity,model_identity,True)
            if not model_identity:raise RuntimeError('CRITICAL_CHECKPOINT_OR_MODEL_IDENTITY_MISMATCH')
            b=bootstrap[mid];mult={int(k):int(v) for k,v in b['scenario_multiplicity'].items()}
            inbag_mask=np.asarray([int(s) in mult for s in scenario],dtype=bool)
            oob_mask=np.asarray([int(s) in set(b['oob_scenario_ids']) for s in scenario],dtype=bool)
            if not np.all(inbag_mask^oob_mask):raise RuntimeError('CRITICAL_MEMBER_PARTITION_MISMATCH')
            X_in=X[inbag_mask];X_oob=X[oob_mask]
            in_indices=np.flatnonzero(inbag_mask);oob_indices=np.flatnonzero(oob_mask)
            a_in=run_predict(mid,model,'A_original_train_member_subset','inbag',X_in,in_indices)
            a_oob=run_predict(mid,model,'A_original_train_member_subset','OOB',X_oob,oob_indices)
            b_full=run_predict(mid,model,'B_original_archive_full_matrix','full_train',X,np.arange(len(X)))
            archived_full=archive[mid+'_y'].to_numpy(dtype=np.float64)
            summary_g1=audits[mid]
            for subset,mask,indices,a_pred in [('inbag',inbag_mask,in_indices,a_in),('OOB',oob_mask,oob_indices,a_oob)]:
                true=y[mask]
                weight=(base_weight[mask]*np.asarray([mult[int(s)] for s in scenario[mask]],dtype=np.float32)
                        if subset=='inbag' else m.scenario_balanced_weights(scenario[mask]))
                b_pred=b_full[mask];archive_pred=archived_full[mask]
                target=original['best_train_weighted_huber' if subset=='inbag' else 'best_oob_weighted_huber']
                lossA=m.weighted_huber_np(a_pred,true,weight)
                lossB=m.weighted_huber_np(b_pred,true,weight)
                loss_archive=m.weighted_huber_np(archive_pred,true,weight)
                ab=compare(a_pred,b_pred);ba=compare(b_pred,archive_pred);aa=compare(a_pred,archive_pred)
                metric='best_inbag_weighted_Huber' if subset=='inbag' else 'best_OOB_weighted_Huber'
                g1row=next(r for r in discrepancies if r['member_id']==mid and r['metric']==metric)
                current={'member_id':mid,'subset':subset,'n':len(indices),'input_dtype':str(X.dtype),'prediction_dtype':str(a_pred.dtype),
                         'nominal_batch_size':4096,'A_input_shape':list(X[mask].shape),'B_input_shape':list(X.shape),
                         'A_minus_B_max_abs_prediction':ab['max_absolute_difference'],'A_B_different_prediction_count':ab['different_elements'],
                         'B_minus_archive_max_abs_prediction':ba['max_absolute_difference'],'B_archive_different_prediction_count':ba['different_elements'],
                         'A_minus_archive_max_abs_prediction':aa['max_absolute_difference'],
                         'A_loss_float64':lossA,'B_loss_float64':lossB,'archive_loss_float64':loss_archive,'summary_loss_float64':target,
                         'A_minus_summary_loss':lossA-target,'B_minus_summary_loss':lossB-target,'archive_minus_summary_loss':loss_archive-target,
                         'B_minus_A_loss':lossB-lossA,'G1_reported_difference':float(g1row['difference']),
                         'A_matches_summary_1e_12':math.isclose(lossA,target,abs_tol=TOL,rel_tol=TOL),
                         'B_matches_archived_predictions_bitwise':ba['bitwise_equal'],
                         'archive_loss_matches_G1_1e_12':math.isclose(loss_archive,float(g1row['recomputed_from_archived_predictions']),abs_tol=TOL,rel_tol=TOL),
                         'delta_path_matches_G1_delta_1e_12':math.isclose(lossB-lossA,float(g1row['difference']),abs_tol=TOL,rel_tol=TOL),
                         'input_order':'raw CSV -> frozen NPZ exact order; boolean mask preserves order',
                         'checkpoint_sha256':sha(train/f'models/{mid}.pt'),'best_epoch':checkpoint['best_epoch'],
                         'original_stop_epoch':int(summary_g1['stop_epoch'])}
                comparisons.append(current)
                for label,value,dtype,reference in [('A_subset_predict_float64_Huber',lossA,'float64 prediction / float32 y,w','frozen summary'),
                                                     ('B_full_predict_then_subset_float64_Huber',lossB,'float64 prediction / float32 y,w','archived full matrix prediction'),
                                                     ('existing_archived_prediction_float64_Huber',loss_archive,'float64 archived prediction / float32 y,w','original G1 discrepancy'),
                                                     ('existing_frozen_summary_final_loss',target,'float64 predict-based Huber','original checkpoint metadata')]:
                    ledger.append({'member_id':mid,'subset':subset,'path':label,'loss':value,'calculation_dtype':dtype,
                                   'reference':reference,'difference_from_summary':value-target,'comparison_tolerance':TOL,
                                   'source':huber_np_location if 'Huber' in label else str(train/f'summaries/{mid}_summary.json')})
                # Float32 monitoring ledger kept separate; no float64 equality criterion.
                if subset=='OOB':
                    history_loss=float(summary_g1['best_OOB_loss_history_float32'])
                    monitorA=float(m.weighted_huber_torch(torch.from_numpy(a_pred.astype(np.float32)),torch.from_numpy(true),torch.from_numpy(weight)))
                    monitorB=float(m.weighted_huber_torch(torch.from_numpy(b_pred.astype(np.float32)),torch.from_numpy(true),torch.from_numpy(weight)))
                    for label,value in [('existing_history_OOB_float32_monitor',history_loss),('new_A_prediction_float32_monitor_Huber',monitorA),('new_B_prediction_float32_monitor_Huber',monitorB)]:
                        ledger.append({'member_id':mid,'subset':subset,'path':label,'loss':value,'calculation_dtype':'Torch float32',
                                       'reference':'history float32 monitor; NOT float64 summary equality',
                                       'difference_from_history_float32':value-history_loss,
                                       'source':huber_torch_location if label.startswith('new') else str(train/f'histories/{mid}_training_history.csv')})
                for j,global_index in enumerate(indices):
                    if a_pred[j]!=b_pred[j] or b_pred[j]!=archive_pred[j]:
                        diff_rows.append({'member_id':mid,'subset':subset,'global_row_zero_based':int(global_index),
                                          'state_id':str(ids[global_index]),'scenario_id':int(scenario[global_index]),
                                          'A_prediction':float(a_pred[j]),'B_prediction':float(b_pred[j]),'archived_prediction':float(archive_pred[j]),
                                          'A_minus_B':float(a_pred[j]-b_pred[j]),'B_minus_archive':float(b_pred[j]-archive_pred[j]),
                                          'float32_label':float(true[j]),'float32_weight':float(weight[j])})
                for field in ['A_matches_summary_1e_12','B_matches_archived_predictions_bitwise','archive_loss_matches_G1_1e_12','delta_path_matches_G1_delta_1e_12']:
                    check(mid+'_'+subset+'_'+field,current[field],current[field],True,'reconciliation')
            log('member_finished',member=mid,forward_calls=3)
        # Preserve a small numerical trace for exactly the selected 3 models.
        table(dest/'three_member_inference_comparison.csv',comparisons)
        table(dest/'Huber_reconciliation_by_path.csv',ledger)
        table(dest/'prediction_difference_rows.csv',diff_rows,['member_id','subset','global_row_zero_based','state_id','scenario_id','A_prediction','B_prediction','archived_prediction','A_minus_B','B_minus_archive','float32_label','float32_weight'])
        dump(dest/'inference_call_ledger.json',inference_calls)
        table(dest/'frozen_function_locations.csv',source_locations)
    except Exception as e:
        fatal=str(e)
        (dest/'diagnostic_exception.txt').write_text(traceback.format_exc(),encoding='utf-8')
        log('stopped',reason=fatal)

    # No full G1 audit is re-executed. Seal all existing G1 outputs and used sources.
    protected_post=[]
    for p,h in protected_before.items():
        actual=sha(p)
        protected_post.append({'path':str(p),'sha256_before':h,'sha256_after':actual,'unchanged':actual==h})
    check('G1_reports_data_and_audit_programs_unchanged',all(r['unchanged'] for r in protected_post),sum(r['unchanged'] for r in protected_post),len(protected_post))
    for p,r in inputs.items():r['sha256_after']=sha(p);r['unchanged']=r['sha256_after']==r['sha256_before']
    check('all_used_frozen_inputs_unchanged',all(r['unchanged'] for r in inputs.values()),sum(r['unchanged'] for r in inputs.values()),len(inputs))
    table(dest/'source_SHA256_checks.csv',list(inputs.values()))
    table(dest/'G1_existing_outputs_immutability.csv',protected_post)
    table(dest/'G1_R_automatic_checks.csv',checks)
    intact=not fatal and all(c['status']=='PASS' for c in checks if c['kind']=='integrity')
    explained=intact and len(comparisons)==6 and all(c['status']=='PASS' for c in checks if c['kind']=='reconciliation')
    status='EVIDENCE_SUPPORTS_CLOSURE_FOR_THREE_SELECTED_MEMBERS' if explained else ('STOP_IDENTITY_OR_INTEGRITY_PROBLEM' if not intact else 'OPEN_NUMERIC_CAUSE_NOT_FULLY_REPRODUCED')
    issues=[{'id':'G1_STRICT_HUBER_RECONCILIATION','status':'RECOMMEND_AUTHOR_REVIEW_CLOSURE_SELECTED_THREE_ONLY' if explained else 'OPEN',
             'evidence':'A/B source-exact inference and six subset comparisons' if explained else 'see failed reconciliation checks and actual environment',
             'scope':'member_05/member_10/member_06 only; no 7-member extension; G1 status unchanged'},
            {'id':'G1_OFFICIAL_STATUS','status':'UNCHANGED_FAIL_NUMERIC_RECONCILIATION_PENDING','evidence':str(g1/'G1_validation.json')},
            {'id':'G1_RUNTIME_ACCESS_AND_SCHEDULER','status':'OPEN_UNVERIFIED_INHERITED','evidence':str(g1/'G1_缺失证据与限制.md')},
            {'id':'G0_SUBMISSION_PROVENANCE','status':'OPEN_INHERITED','evidence':str(g0/'version_conflicts.csv')},
            {'id':'HISTORICAL_CPU_AND_NUMERICAL_LIBRARIES','status':'NOT_INDEPENDENTLY_RECORDED',
             'evidence':'current environment fully logged; Torch version compared to each checkpoint; exact old CPU/BLAS not claimed'}]
    if fatal:issues.insert(0,{'id':'DIAGNOSTIC_STOP','status':'STOP','evidence':fatal})
    table(dest/'G1_R_open_issues_updated.csv',issues)
    validation={'stage':'G1-R','status':status,'original_G1_status':load(g1/'G1_validation.json')['status'],
                'G1_status_modified':False,'three_member_selection':list(MEMBERS),'source_integrity_pass':intact,
                'numerical_cause_reproduced_for_selected_three':explained,'fatal_stop':fatal,
                'strict_abs_tolerance':TOL,'strict_rel_tolerance':TOL,'tolerance_changed':False,
                'inference_predict_calls':len(inference_calls),'forward_batches':sum(len(r['actual_batch_rows']) for r in inference_calls),
                'new_model_training':0,'UE_solves':0,'new_flood_fields':0,'optimization_runs':0,'full_G1_rerun':False,
                'checks':checks,'runtime_environment':env,'open_issues':issues,
                'must_stop_after_G1_R':True,'elapsed_seconds':round(time.perf_counter()-start,3),
                'script':str(Path(__file__).resolve()),'script_sha256':sha(Path(__file__))}
    dump(dest/'G1_R_validation.json',validation)
    report=['# G1-R 三成员数值差异复核报告','',f'诊断状态：**{status}**。原G1状态仍为 **{validation["original_G1_status"]}**，未修改。','',
            '本轮仅处理member_05、member_10和member_06，没有重跑完整G1。核对G0来源SHA、G1交付封存SHA及三个checkpoint；所有源文件、原G1报告、G0/G1审计程序均保留。G1-R的开放问题另存，不覆盖原清单。','',
            '## 1. 路径和运行环境','',
            f'实际环境：Python {env.get("python","")}；PyTorch {env.get("torch","")}；NumPy {env.get("numpy","")}；pandas {env.get("pandas","")}。CPU：{env.get("CPU","")}。Torch线程={env.get("torch_num_threads","")}，CPU推断，按原训练设置启用deterministic algorithms。完整CPU/BLAS配置见runtime_environment.json。','',
            '只调用原冻结训练模块的load_raw、transform、load_model、predict及Huber函数；模块用非main名称导入，不执行main/train_member/fit_preprocessor。预处理使用原preprocessor及其中的baseline_flow、betweenness，没有重新拟合。新变换矩阵、标签、权重和行序与原NPZ作精确检查后才推断；若身份检查不通过即停止。','',
            'A：原train_member布尔切片得到In-bag/OOB子矩阵，分别调用原predict。B：对原完整3178×120训练矩阵调用原predict，再按同一布尔mask分组。两路径名义batch size均4096，因此都只有一个有效batch，差异是实际矩阵行数（及原切片产生的内存布局），不是手动更改batch size。shape/dtype/strides/输入输出字节哈希和排序哈希见inference_call_ledger.json。','',
            f'总predict调用数={len(inference_calls)}；不包含训练或搜索。没有改变线程数寻找更有利结果，没有换模型、权重或成员。','',
            '## 2. 逐成员/子集的数值证据','',
            '|成员|子集|A与B不同预测数|预测最大差|A减summary loss|B减summary loss|归档减summary loss|B与归档逐位一致|',
            '|---|---|---:|---:|---:|---:|---:|---|']
    for r in comparisons:
        report.append(f'|{r["member_id"]}|{r["subset"]}|{r["A_B_different_prediction_count"]}|{r["A_minus_B_max_abs_prediction"]:.16g}|{r["A_minus_summary_loss"]:.16g}|{r["B_minus_summary_loss"]:.16g}|{r["archive_minus_summary_loss"]:.16g}|{r["B_matches_archived_predictions_bitwise"]}|')
    report+=['', '原1e-12绝对/相对容差原样保留。A是否复现summary、B是否逐位复现归档预测、B−A的loss差是否复现原G1登记差异，均单独判定，不把两条路径强制要求得到相同结果。差异行按原state_id和原矩阵索引定位，完整数值见three_member_inference_comparison.csv及prediction_difference_rows.csv。','',
             '## 3. 三种损失分账','',
             'history原OOB监控损失使用Torch float32；summary最终损失使用原predict输出转float64后的weighted_huber_np。新A/B诊断分别记录float64 loss和以其原始float32预测重新计算的Torch监控loss。这些账目在Huber_reconciliation_by_path.csv分别列出，不要求float32监控和float64 summary逐位相同。','',
             '## 4. 身份、顺序和问题判断','']
    if explained:
        report+=['六个子集比较均满足：A路径在原1e-12门槛内复现summary；B路径逐位复现归档完整预测；B−A的loss差在原门槛内复现G1差异。相同checkpoint、相同特征/标签/权重和对应state_id下，仅采用原代码的两条既有矩阵推断路径，就可以复现差异。故这三个成员的微差有可重现计算路径证据，已不只是猜测。','',
                 '这证明的是当前记录环境下原两条推断路径的数值差异，不宣称已反汇编确定具体BLAS微内核，也不宣称恢复原电脑全部硬件环境。原早停best/stop epoch、checkpoint元数据均与既有G1结果一致，无重新选择。','',
                 '**建议：作者可据此评估关闭“三成员微差源于未明数值路径”的审计问题。**本轮只推断三个指定成员，不能声称另外七名成员已完成同样推断；原G1 FAIL状态、报告与所有原数值保持原样，是否更新正式验收由作者决定。']
    else:
        report+=['现有诊断没有满足全部数值归因条件，问题保持OPEN；未提高原1e-12容差，未修改原研究结果或G1状态。已通过及未通过的身份、行序、数据/标签和推断路径检查分别保存在G1_R_automatic_checks.csv。','',
                 '不能将本次运行环境的差异或预测未匹配直接称为原模型训练错误；只有证据明确的身份/数据问题才按实质性问题停机报告。未取得的历史CPU/数值库环境仍列限制。']
    if fatal:report+=['',f'立即停止原因：{fatal}。详见diagnostic_exception.txt。']
    report+=['', '## 5. 来源、开放问题及停止点','',
             'source_SHA256_checks.csv列使用来源的前后SHA及G0/G1预期SHA。G1_existing_outputs_immutability.csv核对原G1全部已有输出及原审计程序未改变。frozen_function_locations.csv给出所调用原函数行号和源码SHA。','',
             'G1_R_open_issues_updated.csv保留数值问题、运行时访问/scheduler证据缺口及G0来源问题，不删除原未核实项。**本轮完成后停止；G2/G3/G4均未启动。**','']
    (dest/'G1_R_数值差异复核报告.md').write_text('\n'.join(report),encoding='utf-8')
    issue_md=['# G1-R 更新的开放问题清单','',f'G1-R：{status}；原G1状态保持不变。','']
    for r in issues:issue_md.extend([f'## {r["id"]}', '',f'状态：{r["status"]}', '',r.get('evidence',''),'',r.get('scope',''),''])
    (dest/'G1_R_开放问题清单.md').write_text('\n'.join(issue_md),encoding='utf-8')
    log('finished',status=status,inference_predict_calls=len(inference_calls),original_G1_untouched=True)
    index=['# G1-R 文件索引','',f'状态：{status}。原G1 FAIL状态未修改。','']
    for p in sorted(dest.iterdir()):
        if p.is_file() and p.name not in ('G1_R_文件索引.md','G1_R_output_SHA256.csv'):index.append('- '+link(p))
    index+=['','- '+link(Path(__file__).resolve(),'限定范围诊断程序'),'']
    (dest/'G1_R_文件索引.md').write_text('\n'.join(index),encoding='utf-8')
    output=[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(dest.iterdir()) if p.is_file() and p.name!='G1_R_output_SHA256.csv']
    output.append({'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__)),'bytes':Path(__file__).stat().st_size})
    table(dest/'G1_R_output_SHA256.csv',output)
    return 0 if explained else 2


if __name__=='__main__':raise SystemExit(main())
