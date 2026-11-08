from common import *
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
SKILL=Path(r'C:\Users\Wuzeqian.PC-20220914MSMS\.codex\skills\nature-figure\scripts')
sys.path.insert(0,str(SKILL))
from audit_panel_alignment import require_matplotlib_panel_alignment
plt.rcParams.update({'font.family':'Arial','font.size':8,'axes.labelsize':9,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,
    'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65})
LABEL={'proposed':'Proposed','greedy_ils':'UE-Greedy-ILS','sa_restart':'SA-restart','ue_bibeam':'UE bidirectional beam','enum_serial':'Full enumeration (serial)','enum_parallel4':'Full enumeration (4 workers)'}
def save(fig,name):
    directory=OUT/'figures';directory.mkdir(exist_ok=True)
    fig.canvas.draw();require_matplotlib_panel_alignment(fig,json_out=str(directory/(name+'.alignment.json')),overlay_svg=str(directory/(name+'.alignment.svg')),strict=True)
    fig.savefig(directory/(name+'.pdf'));fig.savefig(directory/(name+'.svg'));fig.savefig(directory/(name+'.png'),dpi=600)
    fig.savefig(directory/(name+'.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'});plt.close(fig)
def main():
    d=frame(OUT/'S2_fresh_timing.csv');old=frame(ROOT/'analysis/all_run_results.csv');t=old[old.phase=='time_cap']
    samples=[]
    for r in d.itertuples(index=False):samples.append({'method':'enum_'+r.mode,'scenario_id':r.scenario_id,'online_seconds':r.end_to_end_seconds,'regret_pct':r.relative_regret_pct,'queries':1024,'seed_runs':1,'batch':'new measurement'})
    for (method,sid),g in t.groupby(['method','scenario_id']):
        samples.append({'method':method,'scenario_id':sid,'online_seconds':g.fresh_end_to_end_seconds.mean(),'regret_pct':g.relative_regret_pct.mean(),'queries':g.queries.mean(),'seed_runs':len(g),'batch':'original fresh time-cap group'})
    samples=pd.DataFrame(samples);samples.to_csv(OUT/'S2_online_comparison_by_scenario.csv',index=False)
    summary=samples.groupby('method',as_index=False).agg(scenarios=('scenario_id','nunique'),mean_online_seconds=('online_seconds','mean'),median_online_seconds=('online_seconds','median'),P90_online_seconds=('online_seconds',lambda x:np.quantile(x,.9)),mean_scenario_regret_pct=('regret_pct','mean'),P90_scenario_regret_pct=('regret_pct',lambda x:np.quantile(x,.9)),mean_unique_queries=('queries','mean'))
    summary['label']=summary.method.map(LABEL);summary.to_csv(OUT/'S2_online_comparison.csv',index=False)
    m0=t[t.method=='proposed'].copy();m0['candidate_without_inference_seconds']=m0.candidate_seconds-m0.surrogate_inference_seconds
    m0['other_online_seconds']=m0.fresh_end_to_end_seconds-m0.candidate_seconds-m0.physical_UE_seconds
    assert m0.other_online_seconds.min()>-1e-5
    m0[['scenario_id','candidate_without_inference_seconds','surrogate_inference_seconds','candidate_seconds','physical_UE_seconds','other_online_seconds','fresh_end_to_end_seconds']].to_csv(OUT/'S2_Proposed_components.csv',index=False)
    offline=json.loads((OUT/'S2_offline_cost/offline_cost_summary.json').read_text())
    table=summary.set_index('method');amort=[]
    for comparator in ['enum_serial','enum_parallel4','greedy_ils','sa_restart','ue_bibeam']:
        delta=float(table.loc[comparator,'mean_online_seconds']-table.loc['proposed','mean_online_seconds'])
        for costname,cost in [('current_UE_only_lower_bound',offline['current_sequential_UE_dataset_wall_seconds']),('hybrid_current_UE_and_archived_training',offline['hybrid_current_UE_plus_archived_training_seconds'])]:
            amort.append({'comparator':comparator,'offline_cost_scope':costname,'offline_seconds':cost,'mean_comparator_minus_Proposed_seconds':delta,
                'finite_time_crossover':delta>0,'crossover_scenarios':math.ceil(cost/delta) if delta>0 else None,
                'scope':'arithmetic mean-cost crossover only; decision quality differs; prior baselines use prescribed time caps; archived training hardware not established'})
    pd.DataFrame(amort).to_csv(OUT/'S2_amortization.csv',index=False)
    # S1: raw scenario summaries, with identical full seed-range uncertainty.
    runs=frame(OUT/'S1_regret_decomposition_runs.csv');oldq=old[old.phase=='query_cap'];ids=list(range(3001,3031))
    order=[('pool_best_regret_pct','Pool oracle best','#777777','v'),('screened_best_regret_pct','Screened oracle best','#E69F00','s'),
           ('pre_ls_regret_pct','Before first LS','#CC79A7','^'),('final_regret_pct','Final Proposed','#0072B2','o'),('greedy_ils','Greedy-ILS','#009E73','D')]
    fig,ax=plt.subplots(figsize=(183/25.4,125/25.4));fig.subplots_adjust(left=.13,right=.98,bottom=.23,top=.81)
    for j,(column,label,color,marker) in enumerate(order):
        arrays=[(oldq[(oldq.method=='greedy_ils')&(oldq.scenario_id==sid)].relative_regret_pct.to_numpy() if column=='greedy_ils' else runs[runs.scenario_id==sid][column].to_numpy()) for sid in ids]
        center=np.array([a.mean() for a in arrays]);low=np.array([a.min() for a in arrays]);high=np.array([a.max() for a in arrays])
        error=np.array([center-low,high-center]);assert error.min()>-1e-10
        # Constant seed values can produce a one-ulp negative range after averaging.
        error=np.maximum(0.,error)
        ax.errorbar(np.arange(30)+(j-2)*.12,center,yerr=error,fmt=marker,color=color,markersize=2.6,
            linewidth=.6,elinewidth=.55,capsize=1.2,label=label,alpha=.85)
    ax.set_yscale('symlog',linthresh=.001,linscale=.7);ax.set_yticks([0,.001,.01,.1,1,10,100]);ax.set_yticklabels(['0','0.001','0.01','0.1','1','10','100'])
    ax.set_ylim(-.00015,max(float(runs[['pool_best_regret_pct','screened_best_regret_pct','pre_ls_regret_pct','final_regret_pct']].max().max())*1.4,1))
    ax.set_xticks(range(30),ids,rotation=90,ha='center',rotation_mode='anchor');ax.tick_params(axis='x',pad=14)
    ax.set_xlim(-.8,29.8);ax.set_xlabel('Scenario (all ten search seeds)',labelpad=10);ax.set_ylabel('Oracle regret (%)')
    fig.legend(*ax.get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.54,.99),ncol=3,frameon=False)
    save(fig,'S1_regret_stages')
    # S2: both enumeration execution modes are separate, not silently pooled.
    order2=['enum_serial','enum_parallel4','proposed','greedy_ils','sa_restart','ue_bibeam']
    arrays=[samples[samples.method==m].online_seconds.to_numpy() for m in order2]
    colors=['#777777','#AAAAAA','#0072B2','#009E73','#D55E00','#6B51A3']
    fig,ax=plt.subplots(figsize=(183/25.4,105/25.4));fig.subplots_adjust(left=.13,right=.98,bottom=.25,top=.96)
    bp=ax.boxplot(arrays,positions=range(6),widths=.45,patch_artist=True,showfliers=False,whis=(10,90),medianprops={'color':'black','linewidth':1})
    for i,(values,b,color) in enumerate(zip(arrays,bp['boxes'],colors)):
        b.set(facecolor=color,edgecolor=color,alpha=.35);ax.scatter(i+np.linspace(-.17,.17,len(values)),values,s=8,color=color,alpha=.6,edgecolors='none')
    ax.set_xticks(range(6),['Enumeration\nserial','Enumeration\n4 workers','Proposed','Greedy-ILS','SA-restart','Bidirectional\nbeam'])
    ax.set_ylabel('Fresh online time per scenario (s)');ax.set_ylim(0,max(a.max() for a in arrays)*1.12)
    save(fig,'S2_online_cost')
    print('S2 comparison/amortization and both figure export bundles complete.',flush=True)
if __name__=='__main__':main()
