"""Scientific figures from the completed, frozen revision analysis only."""
from pathlib import Path
import json, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=Path(r'C:\Users\Wuzeqian.PC-20220914MSMS\.codex\skills\nature-figure\scripts')
sys.path.insert(0,str(SCRIPTS))
from audit_panel_alignment import require_matplotlib_panel_alignment

ORDER=['proposed','sa_original','sa_restart','greedy_ls','greedy_ils','random_ls','ue_beam','ue_bibeam']
LABELS=['Proposed','Original SA','SA-restart','Greedy-LS','Greedy-ILS','Random + LS','Forward beam','Bidirectional beam']
COLORS=['#0072B2','#999999','#D55E00','#777777','#009E73','#CC79A7','#E69F00','#6B51A3']
MARKERS=['o','v','s','P','^','X','d','D']
COLOR=dict(zip(ORDER,COLORS));LABEL=dict(zip(ORDER,LABELS))
PRIMARY=['proposed','sa_restart','greedy_ils','ue_bibeam']
plt.rcParams.update({'font.family':'Arial','font.size':8,'axes.labelsize':9,'xtick.labelsize':8,'ytick.labelsize':8,
    'legend.fontsize':8,'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','axes.linewidth':.65,
    'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':600})
OUT=ROOT/'figures';OUT.mkdir(exist_ok=True)
notes=[]

def setup(height=110,left=.13,bottom=.16,top=.79):
    fig,ax=plt.subplots(figsize=(183/25.4,height/25.4))
    fig.subplots_adjust(left=left,right=.98,bottom=bottom,top=top)
    ax.tick_params(width=.65,length=3)
    return fig,ax

def symlog(ax,axis='y'):
    getattr(ax,'set_'+axis+'scale')('symlog',linthresh=.001,linscale=.7)
    if axis=='y':
        ax.set_yticks([0,.001,.01,.1,1,10,100]);ax.set_yticklabels(['0','0.001','0.01','0.1','1','10','100'])

def save(fig,ax,name,claim):
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,json_out=str(OUT/(name+'.alignment.json')),overlay_svg=str(OUT/(name+'.alignment.svg')),strict=True)
    fig.savefig(OUT/(name+'.pdf'))
    fig.savefig(OUT/(name+'.svg'))
    fig.savefig(OUT/(name+'.png'),dpi=600)
    fig.savefig(OUT/(name+'.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    notes.append({'figure':name,'axes':1,'alignment':'Not applicable: one axes','claim':claim,'font_pt':8,'backend':'Python Matplotlib'})
    plt.close(fig)

def main():
    assert json.loads((ROOT/'analysis/analysis_summary.json').read_text())['status']=='ANALYSIS_COMPLETE'
    data=pd.read_csv(ROOT/'analysis/all_run_results.csv')
    cp=pd.read_csv(ROOT/'analysis/anytime_scenario_means.csv')
    fig,ax=setup(116)
    x=np.arange(3);bounds=[64,128,256]
    for j,m in enumerate(ORDER):
        g=cp[cp.method==m];arrays=[g[g.budget==b].relative_regret_pct.to_numpy() for b in bounds]
        assert all(len(a)==30 for a in arrays)
        med=np.array([np.median(a) for a in arrays]);lo=np.array([np.quantile(a,.25) for a in arrays]);hi=np.array([np.quantile(a,.75) for a in arrays])
        offset=(j-3.5)*.025
        ax.errorbar(x+offset,med,yerr=np.array([med-lo,hi-med]),color=COLOR[m],label=LABEL[m],marker=MARKERS[j],markersize=3,
            linewidth=1.4 if m=='proposed' else .85,capsize=2,alpha=1 if m=='proposed' else .85)
    symlog(ax);ax.set_ylim(-.0001,max(.01,cp.relative_regret_pct.max()*1.5))
    ax.set_xticks(x,bounds);ax.set_xlabel('Unique UE state queries');ax.set_ylabel('Scenario mean regret (%)')
    fig.legend(*ax.get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.52,.98),ncol=4,frameon=False,columnspacing=1.3)
    save(fig,ax,'Figure_R1_anytime','Descriptive anytime medians and IQR across 30 scenario seed means, without budget-specific retuning.')

    q=data[data.phase=='query_cap'];ids=sorted(q.scenario_id.unique())
    fig,ax=setup(120,left=.105,bottom=.23,top=.88)
    for j,m in enumerate(['proposed','sa_restart']):
        a=[q[(q.method==m)&(q.scenario_id==sid)].relative_regret_pct.to_numpy() for sid in ids]
        assert all(len(z)==10 for z in a)
        pos=np.arange(30)+(j-.5)*.36
        bp=ax.boxplot(a,positions=pos,widths=.28,patch_artist=True,manage_ticks=False,showfliers=False,whis=(0,100),
            medianprops={'color':'black','linewidth':.8},whiskerprops={'linewidth':.65},capprops={'linewidth':.65})
        for b in bp['boxes']:b.set(facecolor=COLOR[m],alpha=.3,edgecolor=COLOR[m],linewidth=.7)
        for xx,yy in zip(pos,a):ax.scatter(xx+np.linspace(-.09,.09,10),yy,s=4,color=COLOR[m],alpha=.7,edgecolors='none')
    symlog(ax);top=max(q[q.method.isin(['proposed','sa_restart'])].relative_regret_pct.max()*1.7,.01);ax.set_ylim(-.0001,top)
    ax.set_xlim(-.7,29.7);ax.set_xticks(range(30),ids,rotation=90,ha='center',rotation_mode='anchor')
    ax.tick_params(axis='x',pad=14);ax.set_xlabel('New validation scenario',labelpad=10);ax.set_ylabel('Seed regret (%)')
    fig.legend(handles=[Line2D([],[],color=COLOR[m],marker='o',label=LABEL[m],linewidth=1) for m in ['proposed','sa_restart']],
        loc='upper center',bbox_to_anchor=(.54,.99),ncol=2,frameon=False)
    save(fig,ax,'Figure_R2_seed_variability','Ten seeds per scenario: points, median, IQR and full seed range; all 30 scenarios retained.')

    dif=pd.read_csv(ROOT/'analysis/scenario_paired_differences.csv');effects=pd.read_csv(ROOT/'analysis/Table_R3_primary_paired_comparisons.csv')
    fig,ax=setup(105,left=.25,bottom=.21,top=.93)
    for i,m in enumerate(PRIMARY[1:]):
        vals=dif[dif.comparator==m].sort_values('scenario_id').paired_difference_pp.to_numpy();r=effects[effects.comparator==m].iloc[0]
        ax.scatter(vals,i+np.linspace(-.16,.16,len(vals)),s=13,color=COLOR[m],alpha=.5,edgecolors='none')
        ax.errorbar(r.mean_paired_improvement_pp,i+.26,xerr=[[r.mean_paired_improvement_pp-r.mean_ci_low],[r.mean_ci_high-r.mean_paired_improvement_pp]],
            fmt='D',markersize=4,color='black',capsize=3,linewidth=1.2)
    ax.axvline(0,color='#777777',linestyle='--',linewidth=.8);ax.set_yticks(range(3),[LABEL[m] for m in PRIMARY[1:]])
    ax.set_ylim(2.6,-.5);ax.set_xlabel('Comparator minus Proposed regret (percentage points)')
    save(fig,ax,'Figure_R3_paired_effects','Thirty paired scenario effects; black diamonds are means with 95% paired bootstrap confidence intervals.')

    s=pd.read_csv(ROOT/'analysis/scenario_seed_summaries.csv');t=s[s.phase=='time_cap']
    fig,ax=setup(110,left=.14,bottom=.18,top=.82)
    markers=['o','s','^','D']
    for m,marker in zip(PRIMARY,markers):
        g=t[t.method==m];assert len(g)==30
        ax.scatter(g.mean_queries,g.mean_wall_seconds,color=COLOR[m],label=LABEL[m],marker=marker,s=19,alpha=.65,linewidths=.4)
    ax.set_xlabel('Mean visible unique UE queries per scenario');ax.set_ylabel('Fresh online wall time (s)')
    ax.set_xlim(0,1060);ax.set_xticks([0,256,512,768,1024])
    fig.legend(*ax.get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.54,.98),ncol=2,frameon=False)
    save(fig,ax,'Figure_R4a_queries_and_time','Separate cold state caches under the per-scenario Proposed reference elapsed-time cap; raw scenario mean points.')

    fig,ax=setup(108,left=.14,bottom=.24,top=.93)
    arrays=[t[t.method==m].mean_regret_pct.to_numpy() for m in PRIMARY]
    bp=ax.boxplot(arrays,positions=range(4),widths=.45,patch_artist=True,showfliers=False,whis=(10,90),
        medianprops={'color':'black','linewidth':1},whiskerprops={'linewidth':.8},capprops={'linewidth':.8})
    for i,(m,b,vals) in enumerate(zip(PRIMARY,bp['boxes'],arrays)):
        b.set(facecolor=COLOR[m],alpha=.3,edgecolor=COLOR[m]);ax.scatter(i+np.linspace(-.16,.16,30),vals,s=10,color=COLOR[m],alpha=.6,edgecolors='none')
    symlog(ax);ax.set_ylim(-.0001,max(.01,t.mean_regret_pct.max()*1.5));ax.set_ylabel('Scenario mean regret (%)')
    ax.set_xticks(range(4),['Proposed','SA-restart','Greedy-ILS','Bidirectional\nbeam']);ax.set_xlabel('Independent elapsed-time cap experiment',labelpad=10)
    save(fig,ax,'Figure_R4b_time_capped_quality','Median, IQR and 10th–90th percentile whiskers across 30 scenario means; raw points show every scenario.')
    (OUT/'render_notes.json').write_text(json.dumps(notes,indent=2),encoding='utf-8')
    print('Exported five single-axes figures as editable PDF/SVG and 600 dpi TIFF/PNG.')

if __name__=='__main__':main()
