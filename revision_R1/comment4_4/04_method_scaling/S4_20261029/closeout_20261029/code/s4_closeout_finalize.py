from pathlib import Path
import sys,os,json,math,itertools,shutil,zipfile
BASE=Path(r'E:\jcr2区意见\返稿\revision_4_4_scaling\04_method_scaling\S4_20261029')
sys.path.insert(0,str(BASE/'code'))
from s4_common import *
CLOSE=BASE/'closeout_20261029'
NAMES={'proposed':'Proposed','greedy_ils':'Greedy-ILS','ue_bibeam':'UE-BiBeam','sa_original':'SA'}
ORDER=list(NAMES)

def md(df, digits=6):
    def cell(v):
        if v is None or (isinstance(v,float) and math.isnan(v)):return '—'
        if isinstance(v,(float,np.floating)):return f'{v:.{digits}g}'
        return str(v).replace('|',' / ').replace('\n',' ')
    return '| '+' | '.join(map(str,df.columns))+' |\n| '+' | '.join(['---']*len(df.columns))+' |\n'+'\n'.join('| '+' | '.join(cell(v) for v in row)+' |' for row in df.itertuples(index=False,name=None))+'\n'

def write(p,s):p.write_text(s,encoding='utf-8')
def relation(a,b):
    eps=KAPPA*max(1.,abs(float(a)),abs(float(b)))
    return ('tie' if abs(a-b)<=eps else 'win' if a<b else 'loss'),eps

def main():
    assert js(CLOSE/'reference_completion_finished.json')['status']=='PASS'
    verify_s4();originals=js(CLOSE/'original_inputs_sha256.json')['sha256'];assert all(sha(p)==h for p,h in originals.items())
    ref=frame(BASE/'analysis/S4_exact_reference_by_m.csv');supp=[]
    for sid in [4401,4406]:
        r=js(CLOSE/f'reference/scenario_{sid}/completion.json');assert r['status']=='PASS'
        mask=(ref.scenario_id==sid)&(ref.m==14)
        ref.loc[mask,'has_full_conditional_reference']=True;ref.loc[mask,'reference_source']='supplemental reference completion'
        ref.loc[mask,'exact_objective']=r['exact_objective'];ref.loc[mask,'target_hex']=r['exact_objective_hex'];ref.loc[mask,'sequence']=seq_string(r['sequence']);ref.loc[mask,'states']=16384
        ref.loc[mask,'epsilon_abs']=epsilon(r['exact_objective']);ref.loc[mask,'DP_exactness_scope']=r['DP_scope'];ref.loc[mask,'UE_target']=1e-9;ref.loc[mask,'reason']='post-freeze reference-only completion; original capped timings preserved'
        supp.append({k:v for k,v in r.items() if not isinstance(v,list)})
    assert ref.has_full_conditional_reference.all() and len(ref)==18
    csv(CLOSE/'analysis/all_18_references_with_provenance.csv',ref);csv(CLOSE/'analysis/supplemental_reference_costs.csv',supp)
    d=frame(BASE/'analysis/S4_scale_method_runs.csv');audit=[]
    for idx,r in d.iterrows():
        rr=ref[(ref.scenario_id==r.scenario_id)&(ref.m==r.m)].iloc[0]
        d.loc[idx,'reference_source_final']=rr.reference_source
        d.loc[idx,'has_full_reference_final']=True
        d.loc[idx,'reference_objective_final']=rr.exact_objective
        if r.status!='PASS':continue
        raw=100*(r.objective-rr.exact_objective)/rr.exact_objective
        assert r.objective>=rr.exact_objective-epsilon(rr.exact_objective)
        d.loc[idx,'signed_regret_pct_final']=raw;d.loc[idx,'conditional_regret_pct_final']=max(0.,raw)
        d.loc[idx,'empirical_hit_final']=abs(r.objective-rr.exact_objective)<=epsilon(rr.exact_objective)
        if r.m==14:
            if r.scenario_id in [4401,4406]:table=frame(CLOSE/f'reference/scenario_{int(r.scenario_id)}/all_states_completed.csv.gz')
            else:table=frame(BASE/f'enum_4core/scenario_{int(r.scenario_id)}/m_14/all_states.csv.gz')
            costs=dict(zip(table.subset_mask.astype(int),table.loss));ph,roads,_,_=physical(int(r.scenario_id),14);roads=list(roads);mask=0;vals=[]
            for road in map(int,r.sequence.split('|')):vals.append(costs[mask]);mask|=1<<roads.index(road)
            j=float(np.mean(vals));assert j.hex()==float(r.objective).hex()
            audit.append({'scenario_id':r.scenario_id,'method':r.method,'replicate':r.replicate,'stored_objective':r.objective,'posthoc_full_table_objective':j,'bitwise_equal':True,'new_optimizer_runs':0})
    csv(CLOSE/'audit/m14_posthoc_sequence_rescoring.csv',audit);csv(CLOSE/'analysis/all_180_runs_posthoc_scored.csv',d)
    scenarios=[]
    for (sid,m,method),g in d.groupby(['scenario_id','m','method'],sort=True):
        ok=g[g.status=='PASS'];planned=1 if method=='ue_bibeam' else 3
        scenarios.append({'scenario_id':int(sid),'m':int(m),'method':method,'planned_repeats':planned,'completed_repeats':len(ok),'complete_seed_set':len(ok)==planned,'available_indices':'|'.join(map(str,ok.replicate.astype(int))),'objective_available_mean':ok.objective.mean(),'regret_available_mean_pct':ok.conditional_regret_pct_final.mean(),'online_available_mean_s':ok.online_wall.mean(),'UE_available_mean':ok.UE_queries.mean(),'RSS_available_mean_MiB':ok.peak_online_RSS_MiB.mean(),'reference_source':ref[(ref.scenario_id==sid)&(ref.m==m)].iloc[0].reference_source})
    s=pd.DataFrame(scenarios);csv(CLOSE/'analysis/scenario_method_means_final.csv',s)
    primary=[];common=[]
    for (m,method),g in s.groupby(['m','method']):
        ok=g[g.complete_seed_set]
        primary.append({'m':m,'method':NAMES[method],'complete_scenarios':len(ok),'full_references_at_size':6,'mean_regret_pct':ok.regret_available_mean_pct.mean(),'median_scenario_regret_pct':ok.regret_available_mean_pct.median(),'max_scenario_mean_regret_pct':ok.regret_available_mean_pct.max(),'mean_online_s':ok.online_available_mean_s.mean(),'mean_UE_queries':ok.UE_available_mean.mean(),'mean_sampled_RSS_MiB':ok.RSS_available_mean_MiB.mean(),'scope':'complete planned seed sets only; m14 quality includes supplemental reference completion'})
        good=s[(s.m==m)&s.complete_seed_set].groupby('scenario_id').size();ids=list(good[good==4].index)
        cg=ok[ok.scenario_id.isin(ids)]
        common.append({'m':m,'method':NAMES[method],'common_complete_scenarios':len(cg),'scenario_ids':'|'.join(map(str,ids)),'mean_regret_pct':cg.regret_available_mean_pct.mean(),'mean_online_s':cg.online_available_mean_s.mean()})
    primary=pd.DataFrame(primary);common=pd.DataFrame(common)
    csv(CLOSE/'analysis/Table_4_4_main_final.csv',primary);csv(CLOSE/'analysis/Table_4_4_common_scenarios.csv',common)
    raw=[];pair=[];seedpair=[]
    for sid in range(4401,4407):
        case=s[(s.scenario_id==sid)&(s.m==14)].set_index('method');r={'scenario_id':sid,'full_DP_J':float(ref[(ref.scenario_id==sid)&(ref.m==14)].iloc[0].exact_objective),'reference_source':case.loc['proposed','reference_source']}
        for method in ORDER:r[NAMES[method]+'_J']=case.loc[method,'objective_available_mean'];r[NAMES[method]+'_n']=int(case.loc[method,'completed_repeats'])
        rank=sorted(ORDER,key=lambda x:case.loc[x,'objective_available_mean']);groups=[]
        for met in rank:
            if groups and relation(case.loc[met,'objective_available_mean'],case.loc[groups[-1][0],'objective_available_mean'])[0]=='tie':groups[-1].append(met)
            else:groups.append([met])
        r['available_mean_order_empirical_ties']=' < '.join(' = '.join(NAMES[x] for x in grp) for grp in groups);r['complete_planned_seed_sets_all_methods']=bool(case.complete_seed_set.all());raw.append(r)
        for a,b in itertools.combinations(ORDER,2):
            ja=float(case.loc[a,'objective_available_mean']);jb=float(case.loc[b,'objective_available_mean']);out,eps=relation(ja,jb)
            pair.append({'scenario_id':sid,'m':14,'method_A':a,'method_B':b,'A_J':ja,'B_J':jb,'A_minus_B':ja-jb,'A_completed_repeats':int(case.loc[a,'completed_repeats']),'B_completed_repeats':int(case.loc[b,'completed_repeats']),'both_complete_seed_sets':bool(case.loc[a,'complete_seed_set'] and case.loc[b,'complete_seed_set']),'strict_raw_sign_A_minus_B':int(np.sign(ja-jb)),'empirical_symmetric_epsilon':eps,'A_outcome':out,'DP_reference_required_for_comparison':False})
    raw=pd.DataFrame(raw);pair=pd.DataFrame(pair);csv(CLOSE/'analysis/m14_raw_objective_scenario_comparisons.csv',raw);csv(CLOSE/'analysis/m14_all_pairwise_raw_comparisons.csv',pair)
    for rep in [0,2]:
        pg=d[(d.scenario_id==4406)&(d.m==14)&(d.method=='proposed')&(d.replicate==rep)].iloc[0];gg=d[(d.scenario_id==4406)&(d.m==14)&(d.method=='greedy_ils')&(d.replicate==rep)].iloc[0]
        out,eps=relation(pg.objective,gg.objective);seedpair.append({'scenario_id':4406,'replicate':rep,'Proposed_J':pg.objective,'Greedy_ILS_J':gg.objective,'Proposed_outcome':out,'epsilon':eps,'scope':'all shared completed seed indices; diagnostic only, not a replacement primary sample'})
    csv(CLOSE/'analysis/4406_shared_completed_indices_diagnostic.csv',seedpair)
    wtl=[]
    for m in [10,12,14]:
        for comp in ORDER[1:]:
            items=[];avail=[]
            for sid in range(4401,4407):
                case=s[(s.scenario_id==sid)&(s.m==m)].set_index('method');p=case.loc['proposed'];c=case.loc[comp];out,_=relation(p.objective_available_mean,c.objective_available_mean);avail.append(out)
                if p.complete_seed_set and c.complete_seed_set:items.append((out,p.regret_available_mean_pct-c.regret_available_mean_pct,p.online_available_mean_s-c.online_available_mean_s))
            wtl.append({'m':m,'comparator':NAMES[comp],'primary_complete_pairs':len(items),'wins':sum(i[0]=='win' for i in items),'ties':sum(i[0]=='tie' for i in items),'losses':sum(i[0]=='loss' for i in items),'mean_paired_regret_difference_pp':float(np.mean([i[1] for i in items])),'mean_paired_online_difference_s':float(np.mean([i[2] for i in items])),'available_mean_scenarios':6,'available_wins':avail.count('win'),'available_ties':avail.count('tie'),'available_losses':avail.count('loss'),'incomplete_available_means_are_secondary_only':True})
    wtl=pd.DataFrame(wtl);csv(CLOSE/'analysis/Proposed_WTL_final.csv',wtl)
    # All original reference and timing datasets retained as explicitly historical views.
    for name in ['Table_4_4_S4_main_results.csv','S4_exact_reference_by_m.csv','S4_enumeration_costs.csv','S4_enumeration_Proposed_cost_summary.csv','S4_win_tie_loss_by_m.csv','S4_optimization_execution_status.csv','S4_enum_serial_execution_status.csv','S4_enum_4core_execution_status.csv']:
        shutil.copy2(BASE/'analysis'/name,CLOSE/'audit'/('ORIGINAL_CAPPED_'+name))
    for name in ['S1_complexity_table.csv','Table_4_4_first_batch_summary.csv']:
        shutil.copy2(SCALE/'05_analysis'/name,CLOSE/'analysis'/name)
    # Censoring, interruption and equality explanations remain distinct.
    interrupted=js(CLOSE/'audit/unfinished_task_evidence.json');eq=frame(CLOSE/'audit/greedy_beam_equality.csv');inv=frame(CLOSE/'audit/reference_state_inventory_before.csv');cost=pd.DataFrame(supp)
    missing=pd.DataFrame([
        {'item':'4401 m14 complete numerical reference','original_status':'missing under 128.819619278 s cap','final_status':'supplemental reference completion; 16384 states','remaining_missing':False,'treatment':'original timing remains censored; new reference is posthoc only'},
        {'item':'4406 m14 complete numerical reference','original_status':'missing under 128.819619278 s cap','final_status':'supplemental reference completion; 16384 states','remaining_missing':False,'treatment':'original timing remains censored; new reference is posthoc only'},
        {'item':'4406 m14 Greedy-ILS replicate index 1','original_status':'concurrency guard interrupted after ready','final_status':'not rerun; final output and timing missing','remaining_missing':True,'treatment':'exclude from 3-seed primary mean; available indices 0 and 2 descriptive only'},
        {'item':'identity of external Python process triggering guard','original_status':'not logged','final_status':'unknown','remaining_missing':True,'treatment':'cannot attribute interruption to a named program/user or infer prior effect'},
        {'item':'fresh complete m14 serial enumeration times, all 6','original_status':'0/6 complete','final_status':'still 0/6 complete in original benchmark','remaining_missing':True,'treatment':'supplemental cached completion cannot replace fresh timings'},
        {'item':'fresh complete m14 four-core enumeration times, 4401 and 4406','original_status':'4/6 complete','final_status':'still 4/6 complete in original benchmark','remaining_missing':True,'treatment':'retain right censoring and lower-bound comparisons'}])
    csv(CLOSE/'analysis/missing_data_status.csv',missing)
    primaryview=primary[['m','method','complete_scenarios','mean_regret_pct','mean_online_s','mean_UE_queries']]
    rawview=raw[['scenario_id','full_DP_J','Proposed_J','Greedy-ILS_J','UE-BiBeam_J','SA_J','Greedy-ILS_n','available_mean_order_empirical_ties']]
    costview=cost[['scenario_id','reused_states','new_UE_states','supplemental_solve_wall_seconds','new_UE_kernel_seconds','DP_wall_seconds','exact_objective']]
    wtview=wtl[['m','comparator','primary_complete_pairs','wins','ties','losses','mean_paired_regret_difference_pp']]
    old=frame(BASE/'analysis/Table_4_4_S4_main_results.csv');old14=old[old.m==14]
    new14=primary[primary.m==14].set_index('method');wt14=wtl[wtl.m==14]
    prep=frame(SCALE/'05_analysis/Table_4_4_first_batch_summary.csv')
    complexity=(SCALE/'05_analysis/S1_complexity_proof.md').read_text(encoding='utf-8')
    pwt='；'.join(f"对{r.comparator}为{r.wins}/{r.ties}/{r.losses}（n={r.primary_complete_pairs}）" for r in wt14.itertuples())
    report=f'''# Reviewer 1 第4.4条最终中文验收报告

生成时间：{now()}。本报告整合S0—S3复杂度/组件核验与第二批S4最终收尾。结果范围为探索性规模压力测试，不做显著性检验，不宣称代理相对于UE-only强基线具有整体优势。

## 1. 验收结论与分母

原S4优化仍为179/180完成，m=14为59/60完成。此次新增优化运行0次、训练0次；没有改变算法、权重、参数、4401—4406情景或种子。原始文件哈希复核通过。补齐4401和4406的m=14参照后，完整数值参照由16/18增至18/18，m=14由4/6增至6/6。两张补表均标记 **supplemental reference completion**。这是新增参照覆盖，不是补跑优化或完成原始枚举计时。

Greedy-ILS在4406仍只有固定索引0和2两次完成输出，缺失索引1没有填补。主汇总要求随机方法全部3个预定种子完成，因此m=14 Greedy-ILS主汇总n=5，其余方法n=6；共同完整情景表统一使用4401—4405，避免不同分母直接排名。4406的2次Greedy-ILS仅列于已观测结果与共享索引诊断。

## 2. 逐情景原始目标值与胜负（无需DP）

目标J越小越好：J为恢复前至第m−1次恢复后的m个状态成本C的均值，C=TSTT/7480225.3449211195−1，最终全恢复状态权重为0。随机方法先平均该情景已有的固定种子，Beam仅1次确定性运行。4406 Greedy-ILS均值仅2/3，表中单列n。每个已完成的m=14序列已用自身原始journal和完整参照表分别重算，59/59与保存目标逐位一致。新参照未参与任何搜索。

{md(rawview)}

胜负只比较同一情景、同一恢复集合的J。数值平局采用预先沿用的κ={KAPPA:.17g}，对称阈值κ·max(1,|Ja|,|Jb|)；同时在CSV保留未舍入差值、严格正负号和阈值。该经验阈值不是UE误差定理；表中显示精度不用于判胜。`m14_all_pairwise_raw_comparisons.csv`包含全部36对情景比较和完整种子标识。无需完整DP即可确定上述观测目标顺序，但这不构成全局最优证明。

m=14 Proposed主配对胜/平/负：{pwt}。对4406的Greedy-ILS，已完成索引0和2分别与相同索引Proposed作诊断，见`4406_shared_completed_indices_diagnostic.csv`；不把这些观测补成主分析的第三个种子。

## 3. Greedy-ILS与UE-BiBeam原平均regret相同的原因

原m=14质量表只有4402—4405四个完整参照，二者均值都是0.168337424514763%。逐原始文件核查：这4个情景中，12次Greedy-ILS与对应Beam的最终序列完全相同、J的float.hex完全相同，且均等于共同的贪心初始解；在固定预算内均未改善该初始解。两者的UE查询journal哈希不同，查询phase不同，源码分派分别为局部搜索/扰动与双向beam；没有发现方法别名或误读同一输出。

原四情景中，二者均有3个数值等价最优情景、1个相同的0.673349698059052% regret情景，故同分母平均恰好相同。4401中三个Greedy-ILS运行都从J=256.3273146370184改善到256.08110217302135，Beam保留256.3273146370184，改善0.24621246399703978；因此不能将原四情景汇总相同推广到全部六情景。4406两次已完成Greedy-ILS与Beam同序列同目标，但缺失第三次，主分母仍不同。完整逐次证据见`audit/greedy_beam_equality.csv`。

## 4. 唯一未完成优化：日志与可知边界

原目录：`{interrupted['path']}`。

`ready.json`记录正式计时开始于{interrupted['ready']['started_at']}，worker PID32492；`monitor.json`记录CONCURRENT_PYTHON_TASK、exit_code15，ready后13.390859599690884秒中止，尚未到128.81961927800955秒上限。已保存154个有效物理状态，最后mask6278、RG=5.09783282745189e-10。`worker.log`为0字节；没有UE_failure.json，也没有timing.json、result.json或最终逻辑账本。因此154不是完整算法查询数或可用最终优化成绩，不能推定完成目标、补记0 regret或采用最后一个状态代替序列目标。

驱动器将状态泛称SCALING_FAILURE，但具体原因是并发保护中止，不能归为算法规模失败或UE收敛失败。日志没有记录外部Python进程PID/命令行，无法进一步识别来源。另有4405/m10/Proposed/index1的一次ready前启动中止，现场已在原日志归档，未产生实验UE或目标，随后同任务同种子在完整参照前继续并完成；它不是本项正式计时中的唯一缺失。此次不重跑任何优化。

## 5. 缺失状态、复用依据与补充成本

{md(inv)}

每张m=14完整表需要2^14=16,384状态。只复用同一情景、同一m=14道路位序的serial、四核chunk及优化物理journal（含中止任务已完成的有效状态）。不跨m或跨情景借用状态。每份日志先校验mask唯一、converged和RG≤1e-9，重叠TSTT/loss逐位核对后去重。四核journal可能含截止后才完成而未返还给算法的行；这些可用于离线参照，但不能让原超时任务变成完成。来源、哈希、重复数量见`audit/reused_source_inventory.csv`和各表的source_paths。

计算前冻结reference_only_protocol.json。只对缺失mask升序求解：一个计算进程、CPU0、计算线程1，两个情景顺序执行，沿用原UE求解器、cold flow start、target=1e-9和原max_iter。预热只用开发情景246，未训练代理、未运行任何优化器。所有新状态RG合格，完整表两套DP实现目标float.hex一致，终态零权重、m项均值口径不变。

{md(costview)}

上表wall只指新增缺失UE状态的串行补算窗口（含轻量日志等开销），kernel是新增UE求解器内核累计时间，DP与预热单列于完整cost CSV；完整表导出在solve窗口之外，未单独计时。历史日志所有副本的solver_seconds之和只表示已发生的UE内核工作，不是可复用状态的唯一工作量、完整枚举墙钟或多核墙钟。重复历史工作、缓存复用、新补算与原fresh枚举绝不拼接为一个新的枚举基准时间。内存为每次求解后观测RSS最大值，不是连续采样峰值保证。

## 6. 最终质量与原始时间表

{md(primaryview)}

regret=100·(J−J_DP)/J_DP，有限数值表条件精确；小于机器舍入的负值按原规则截为0，同时保留signed列。先平均固定技术种子，再平均情景；技术重复不是独立样本。表中m=14新质量均值使用补充参照，主种子分母规则不变。共同情景表另列所有方法相同n=5；不得直接用不同n的Greedy-ILS/其他方法总均值宣称优劣。

{md(common[common.m==14])}

{md(wtview)}

初始限定计时质量快照完整保留在`audit/ORIGINAL_CAPPED_Table_4_4_S4_main_results.csv`，其中m=14仍为4/6。最终新增参照版是另一张表，不覆盖原4/6记录。全部原timing/monitor文件逐文件哈希不变。

原fresh serial枚举仍完成9/18，m=14为0/6；原fresh情景内四核枚举仍完成16/18，m=14为4/6。补充表完成不等于原计时完成。m=14 Proposed原平均在线19.9962898944秒；原serial完整枚举平均耗时仅有下界128.819619278秒，对应节时下界84.47729468%；四核平均完成耗时下界101.850469876秒，对应节时下界80.36701262%。这些只是在固定实现、当前网络与资源政策下相对完整枚举的描述性下界，不支持相对UE-only优化器的整体速度或质量优势。Greedy-ILS时间主均值缺4406，比较时间时仅用共同5情景，配对差值见WTL表；其余时间原口径完整保留。

## 7. 第4.4条复杂度与组件验证的完整交代

全排列m!不是UE调用量。完整数值表2^m状态；单次DP时间O(m·2^m)、空间O(2^m)。K=10模型成员的全量预测O(K·2^m·C_NN)，预测矩阵为8K·2^m字节，特征构建还有O(120·2^m)及Python临时对象；89次DP及多份policy带来显著准备成本。候选数N=30,000仍含O(N·m·K)生成/目标缓存、O(N log N)排序及Kendall方向O(N·m²)时间/空间。固定UE预算B=256不意味着恒定端到端成本或多项式可扩展性。

原全四路有序前缀P(m,4)=m(m−1)(m−2)(m−3)。m>10为S4前已冻结的size-adapted Proposed：固定16k来源与循环均衡抽样，非本次修改，m12/m14前缀访问覆盖约44.93%/22.20%；不能称为原全覆盖算法无改动扩展。原m10回归已通过，54次新Proposed候选顺序/代理矩阵都与先前S3逐位复现。

{md(prep)}

组件表每规模6情景×3技术重复，准备时间包含推理、DP和筛选；RSS含解释器/模型等，非纯矩阵。m16仅为断连的特征计算夹具，无UE求解/决策质量，其时间和内存不能当作真实洪水恢复结果。24节点38物理道路保持全连通要求至多关闭15条，m≤15只是必要界；在此网无法给出物理有效m16的S4验证。

## 8. 范围、缺失与交付状态

这是单一固定Sioux Falls网络上6个扩展强灾输入的探索性规模压力测试，14闭路、嵌套m10/12/14；训练分布主要m10。固定B对应25%/6.25%/1.5625%状态，目标长度、严重程度和前缀覆盖也变化，不能解释为纯m因果效应。没有显著性声明、置信区间或总体优势声明，也不据此推翻4.1/4.3对强UE-only基线的既有证据。选择性子集、受限宽度搜索仍属未来扩展。

完整参照现已补齐，但4406 Greedy-ILS第2次最终输出、触发中止外部进程身份及原超时完整枚举耗时仍缺失，见`缺失数据说明.md`。本轮完成的是数值验收、正文替换文字/表格与R1.4.4英文回复草稿；原Word全文未编辑，正式页行号、表号及clean/marked稿整合仍待作者排版。数值压缩包仅CSV/CSV.GZ，报告、代码、模型不再打包。
'''
    write(CLOSE/'4.4_完整中文验收报告.md',report)
    missingtext=f'''# 4.4最终缺失数据与补充参照说明

原始计时与补充参照属于不同证据层。原始128.81961927800955秒任务上限及其结果没有改写。

{md(missing)}

原质量快照m=14为4/6完整参照；现4401、4406通过 **supplemental reference completion** 补成6/6，全部规模共18/18。补算状态数分别854和7067，原有效复用状态15530和9317。新表只用于已封存优化序列的事后regret计算。最终有限表DP精确不代表无限精度UE最优。

优化仍179/180完成。4406/m14/Greedy-ILS/rep_01在ready后13.3908595997秒因CONCURRENT_PYTHON_TASK退出15；154行有效物理状态不构成最终优化结果。无最终结果/时间，不补零、不插值、不替换种子、不补跑。主统计要求3个预定技术种子齐全，因此该方法m14主分母5，其余6；共同表统一5。4406两次已观测输出单独列n=2、索引0/2，作为描述性附录。

日志路径：`{interrupted['path']}`；具体证据摘录在`audit/unfinished_task_evidence.json`。未记录外部进程身份，无法追溯其具体来源。原serial m14完整耗时0/6、四核m14完整耗时4/6的删失保持不变。补算wall包含缓存复用的流程背景，不得填入原fresh枚举计时空格或用作新速度比。
'''
    write(CLOSE/'缺失数据说明.md',missingtext)
    # Minimal synchronized manuscript insertion; original comment copied from already verified draft.
    results_para='Mean conditional regrets (%) for Proposed, Greedy-ILS, UE-BiBeam and SA were respectively '
    chunks=[]
    for m in [10,12,14]:
        part=primary[primary.m==m].set_index('method')
        vals=[format(part.loc[NAMES[x],'mean_regret_pct'],'.4f') for x in ORDER]
        chunks.append(', '.join(vals)+f' at m={m}')
    results_para+='; '.join(chunks)+'. All method means use six scenarios except Greedy-ILS at m=14, which uses the five scenarios with all three planned seeds completed. Different-denominator means should not be directly ranked; a common-five-scenario table is provided.'
    scope_para='The full-state surrogate and subset-DP architecture retains exponential dependence on recovery-set size. The size-adapted extension fixes candidate quotas but reduces four-road-prefix coverage to about 45% and 22% at m=12 and m=14; it does not eliminate full-state construction. These six extended-severity inputs on one fixed network constitute an exploratory scaling stress test, with no significance claims or overall superiority claim over strong UE-only baselines. On the connected 24-node, 38-road network, m≤15 is a necessary topological bound; m=16 is a component-only feature fixture, not a valid UE recovery experiment. Selective subset evaluation and bounded-width search remain future work.'
    provenance_para='All 180 planned optimizations were attempted and their outputs frozen before reference evaluation; 179 completed. One m=14 Greedy-ILS repetition was interrupted by a concurrency guard after measurement started and was not rerun. Original capped enumeration produced 16/18 full tables. Subsequent supplemental reference completion reused validated states and solved only 854 and 7,067 missing states for scenarios 4401 and 4406 at m=14, respectively, yielding 18/18 finite numerical reference tables. This post-freeze reference-only calculation did not modify or rerun any optimizer and does not replace the original censored 128.82-s enumeration timings. Regret is conditional on the recorded RG-converged numerical table, not an infinite-precision UE certificate.'
    methods_para='For m restoration candidates, a full reference requires 2^m distinct UE states and one subset DP takes O(m·2^m) time and O(2^m) space. The implementation performs 89 proxy DP computations and retains multiple policies; full prediction and feature construction also scale with 2^m. Candidate screening includes O(N·m²) Kendall-orientation storage and computation. A fixed UE-query budget therefore does not imply constant end-to-end runtime or polynomial scalability. The original ordered four-road prefix coverage is P(m,4)=m(m−1)(m−2)(m−3); the m>10 extension uses the size-adapted sampling rule frozen before S4. All comparisons use fixed scenarios and seeds, with technical seeds averaged within scenario.'
    manuscript=f'''# 第4.4条正文替换文字与表格（最终数值版）

状态：draft_with_placeholders。英文可供整合，最终章节/表号/页行号AUTHOR_INPUT_NEEDED；原Word尚未改动。保持正文精简，逐状态与中断证据放补充材料。

## Methods insertion

{methods_para}

## Results insertion

{results_para}

{provenance_para}

## Scope insertion

{scope_para}

## Main manuscript table: frozen algorithm runs, final reference coverage

{md(primaryview)}

Table note: Lower regret is better. Three planned fixed seeds per stochastic method and one deterministic UE-BiBeam run per scenario; only complete planned seed sets enter the primary mean. At m=14 Greedy-ILS has n=5, the other methods n=6. All m=14 quality values include two separately labelled supplemental reference completions. Time and query values are unchanged original optimizer measurements. No statistical inference is claimed. Proposed at m>10 denotes the previously frozen size-adapted extension.

## Common-denominator sensitivity table (m=14, 4401–4405)

{md(common[common.m==14])}

## Supplementary observed objective table (same scenario and recovery set)

{md(rawview)}

Table note: Greedy-ILS in scenario4406 is an available-two-seed diagnostic only; the missing third seed is not imputed. The objective ordering does not require a DP reference. Empirical equivalence uses κ·max(1,|Ja|,|Jb|); unrounded gaps are supplied in CSV.

## 中文核对

{pwt}。只说明本组观测，不能宣称代理相对UE-only有整体优势。原m14两种强基线平均regret相同是原4个完整参照情景上相同贪心序列所致；4401中二者不同，补齐参照后不能沿用旧的相同均值概括。原计时删失不随补参照改变。数据生成与规模适配均在原S4前冻结，本轮没有修改算法。
'''
    write(CLOSE/'manuscript/4.4_正文表格与英文替换段落.md',manuscript)
    original=(BASE/'manuscript/Reviewer1_Comment4.4_回复草稿.md').read_text(encoding='utf-8').split('## Original comment\n\n')[1].split('\n## Response')[0]
    wenglish='; '.join(f"{r.wins}/{r.ties}/{r.losses} against {r.comparator} (n={r.primary_complete_pairs})" for r in wt14.itertuples())
    costenglish='; '.join(f"scenario {int(r.scenario_id)}: {int(r.reused_states):,} reused states, {int(r.new_UE_states):,} new solves, {r.supplemental_solve_wall_seconds:.2f} s supplemental solve-window wall time" for r in cost.itertuples())
    reply=f'''# Reviewer 1, Comment 4.4 — final numerical response draft

Readiness: draft_with_placeholders. Evidence and proposed replacement text are complete for this comment. Final manuscript/SI table numbers and page/line locations are AUTHOR_INPUT_NEEDED; the Word manuscript and tracked revision have not been integrated in this task.

## Original comment

{original}

## Response

We agree that the full-state architecture has an exponential scaling bottleneck. We now make the implemented time and memory dependence explicit and report a bounded, exploratory scaling stress test, rather than claim scalability to much larger recovery sets.

{methods_para}

The component experiment included six fixed inputs and three technical repetitions per size. Mean preparation times at m=8,10,12,14 were 6.14, 6.21, 7.98 and 12.88 s, and mean sampled process RSS was approximately 385, 390, 405 and 433 MiB. A separate m=16 feature fixture required 36.59 s and 784 MiB but is not a physically valid connected recovery experiment and has no UE quality result. At m=14 the proxy DP component alone averaged 6.00 s. These observations support the retained bottleneck, not removal of exponential complexity.

{provenance_para}

For transparency, the supplemental calculation costs are reported separately: {costenglish}. Every reused state belongs to the same scenario and the same m=14 recovery-set bit mapping, all recorded states satisfy RG≤1e-9, and overlapping TSTT and loss values agree bit for bit. Two DP implementations return bitwise-identical optimal objectives. Historical duplicated UE work and new missing-state computation are not combined into a fresh enumeration benchmark. The missing optimizer output remains missing: scenario4406, m=14, Greedy-ILS seed index1; monitor.json records CONCURRENT_PYTHON_TASK and exit code15 at 13.39 s after ready, with 154 converged physical state rows but no final result or authoritative completed online timing. The triggering external process identity was not logged; this cannot be attributed to UE non-convergence or the 128.82-s cap.

{results_para}

The previously identical m=14 Greedy-ILS and UE-BiBeam mean regret (0.1683374%) was calculated over the same four reference-complete scenarios, 4402–4405. In each, their final sequences and raw objectives were identical to the common greedy initialization; their query journals and search phases differ. This was therefore neither a denominator mismatch nor reuse of the same method output. In scenario4401, all three Greedy-ILS runs improve J from 256.3273146370184 to 256.08110217302135 while UE-BiBeam retains the initial sequence, so equality on the original four scenarios cannot be generalized. All 59 completed m=14 sequence objectives were independently rescored without rerunning the algorithms and agree bit for bit with stored objectives.

Scenario-wise raw objectives also permit direct comparisons without a complete DP reference. Using the carried-over empirical equivalence threshold κ·max(1,|Ja|,|Jb|), the final m=14 Proposed win/tie/loss counts on complete planned seed sets are {wenglish}. The available two-seed Greedy-ILS output in scenario4406 is shown separately, with its missing seed explicitly indicated. These descriptive comparisons do not support an overall advantage of surrogate guidance over the strong UE-only baselines.

The original m=14 fresh serial enumeration remains 0/6 complete and the within-scenario four-core enumeration remains 4/6 complete under the frozen cap. Against Proposed's original mean online time of 20.00 s, these censored measurements imply time-saving lower bounds of 84.48% and 80.37%, respectively; they are not measured complete enumeration times or comparisons with the UE-only optimizers. Supplemental cached completion has not been inserted into either timing series.

Proposed manuscript additions are synchronized with the accompanying replacement text:

*{scope_para}*

*{provenance_para}*

Location: Methods complexity paragraph, Results scaling table, and scope/limitations paragraph; final page/line and table/SI identifiers: AUTHOR_INPUT_NEEDED. The experiment uses six scenario units on one network, makes no significance claim, retains unfavorable baseline comparisons and does not overturn the earlier 4.1/4.3 evidence.
'''
    write(CLOSE/'manuscript/Reviewer1_4.4_英文审稿回复草稿.md',reply)
    # Numeric-only archive: all closeout CSVs, plus original raw m14 optimizer journals/ledgers/traces.
    for source in [Path(__file__),Path(__file__).with_name('s4_closeout_audit.py'),Path(__file__).with_name('s4_reference_completion.py')]:shutil.copy2(source,CLOSE/'code'/source.name)
    files=[(p,p.relative_to(CLOSE).as_posix()) for p in CLOSE.rglob('*') if p.is_file() and (p.name.endswith('.csv') or p.name.endswith('.csv.gz'))]
    for p in (BASE/'optimization').rglob('*'):
        if p.is_file() and 'm_14' in p.parts and (p.name.endswith('.csv') or p.name.endswith('.csv.gz')):files.append((p,'original_m14_optimizer/'+p.relative_to(BASE/'optimization').as_posix()))
    index=CLOSE/'analysis/numerical_files_index.csv';files=[(p,a) for p,a in files if p!=index]
    csv(index,[{'archive_path':a,'source_path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p,a in files]);files.append((index,'analysis/numerical_files_index.csv'))
    archive=CLOSE/'4.4最终数值结果_含补充参照_20261029.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p,a in sorted(files,key=lambda x:x[1]):z.write(p,a)
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None and len(z.namelist())==len(files) and all(n.endswith(('.csv','.csv.gz')) for n in z.namelist())
    assert all(sha(p)==h for p,h in originals.items());verify_s4()
    qa={'status':'PASS','at':now(),'original_files_verified_unchanged':len(originals),'original_optimizer_completed':179,'new_optimizer_runs':0,'new_training_runs':0,'m14_completed_sequence_rescoring_bitwise_pass':len(audit),'full_references_final':18,'m14_references_final':6,'primary_m14_Greedy_ILS_scenarios':5,'supplemental_new_states':sum(r['new_UE_states'] for r in supp),'numeric_zip':str(archive),'numeric_zip_entries':len(files),'numeric_zip_bytes':archive.stat().st_size,'numeric_zip_sha256':sha(archive),'zip_crc':'PASS','original_capped_timings_unchanged':True,'manuscript_readiness':'draft_with_placeholders; Word integration and final locations pending'}
    dump(CLOSE/'delivery_QA.json',qa)
    write(CLOSE/'README_最终结果入口.md',f'''# 4.4最终结果入口

先读[完整中文验收报告](4.4_完整中文验收报告.md)，再看[正文表格与替换段落](manuscript/4.4_正文表格与英文替换段落.md)、[英文审稿回复](manuscript/Reviewer1_4.4_英文审稿回复草稿.md)和[缺失数据说明](缺失数据说明.md)。

完整参照18/18；优化179/180，缺失优化不补跑。m14主Greedy-ILS n=5，其余n=6；共同5情景表用于统一分母。两张参照标记supplemental reference completion，不改原128.82秒计时。

数字包：`{archive.name}`，{len(files)}个CSV/CSV.GZ文件，{archive.stat().st_size:,}字节，CRC核验通过。包内只含数值数据，不含模型/代码/稿件。完整逐次优化源文件保留在原S4目录，哈希不变。
''')
    dump(CLOSE/'manifest.json',{'at':now(),'sha256':{str(p.relative_to(CLOSE)):sha(p) for p in CLOSE.rglob('*') if p.is_file() and p.name not in ['manifest.json','finalize_stdout.log']}})
    print(json.dumps({'QA':qa,'m14_primary':new14.reset_index().to_dict('records'),'m14_WTL':wt14.to_dict('records'),'raw_comparison':raw.to_dict('records'),'supplemental_costs':supp},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
