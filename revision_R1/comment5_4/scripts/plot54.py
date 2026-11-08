"""Three scientific figures from frozen CSVs; Python backend only."""
from pathlib import Path
import sys,os
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parents[1]
os.environ['MPLCONFIGDIR']=str(OUT/'runtime_cache/matplotlib')
sys.path.insert(0,'E:/jcr2区意见/返稿/4.1专项返修_20261026/runtime_deps')
sys.path.insert(0,'C:/Users/Wuzeqian.PC-20220914MSMS/.codex/skills/nature-figure/scripts')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from audit_panel_alignment import require_matplotlib_panel_alignment
plt.rcParams.update({'font.family':'Arial','font.size':8,'axes.labelsize':8,'axes.titlesize':9,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7,'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','savefig.dpi':600,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7,'xtick.major.width':.6,'ytick.major.width':.6})
BLUE='#0072B2';ORANGE='#D55E00';GRAY='#888888'
def export(fig,name,multi=False):
    fig.canvas.draw()
    if multi:require_matplotlib_panel_alignment(fig,json_out=OUT/'figures'/f'{name}.alignment.json',overlay_svg=OUT/'figures'/f'{name}.alignment.svg',tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
    fig.savefig(OUT/'figures'/f'{name}.pdf')
    fig.savefig(OUT/'figures'/f'{name}.png',dpi=600)
    fig.savefig(OUT/'figures'/f'{name}.svg')
    plt.close(fig)
def main():
    s=pd.read_csv(OUT/'Table_duration_summary.csv');d=pd.read_csv(OUT/'raw/DP_optimal_sequences_and_crosschecks.csv');original=pd.read_csv(OUT/'Table_original_absolute_regret.csv')
    levels=['uniform','moderate','strong'];labels=['Uniform','Moderate','Strong']
    fig,axs=plt.subplots(1,2,figsize=(7.2,3.8),sharey=True)
    fig.subplots_adjust(left=.095,right=.98,bottom=.19,top=.81,wspace=.20)
    for ax,policy,title,color,letter in zip(axs,['full_method','exact_DP_original_rho1'],['Frozen Full','Original equal-duration DP'],[BLUE,ORANGE],['a','b']):
        for i,level in enumerate(levels):
            g=s[(s.policy==policy)&(s.level==level)].sort_values('scenario_id');x=i+np.linspace(-.15,.15,len(g))
            # All points are scenario-level means; 3-allocation range is not an uncertainty interval.
            ax.vlines(x,g.regret_min,g.regret_max,color=color,alpha=.24,lw=.8,zorder=1)
            ax.scatter(x,g.regret_mean,color=color,s=17,zorder=3,linewidths=0)
            ax.plot([i-.20,i+.20],[g.regret_mean.median()]*2,color='#222222',lw=1.3,zorder=4)
        ax.set_xticks(range(3),labels);ax.set_xlim(-.45,2.45);ax.set_ylim(-8,390);ax.set_yticks([0,100,200,300]);ax.set_title(title,pad=10)
        ax.grid(axis='y',color='#DDDDDD',lw=.5,zorder=0);ax.text(-.10,1.04,letter,transform=ax.transAxes,fontweight='bold',fontsize=9)
    axs[0].set_ylabel('Duration-weighted regret (%)')
    fig.text(.095,.935,'Transfer of frozen recovery orders under heterogeneous durations',fontsize=9)
    fig.text(.095,.885,'10 floods; points: scenario means; lines: allocation ranges; black: median',fontsize=7)
    export(fig,'Figure_R1_5_4_duration_regret',True)
    configs=[('uniform','uniform'),('moderate','depth_rank'),('moderate','permutation_seed_1'),('moderate','permutation_seed_2'),('strong','depth_rank'),('strong','permutation_seed_1'),('strong','permutation_seed_2')]
    matrix=np.zeros((10,7),int);changed=np.zeros_like(matrix)
    for i,sid in enumerate(range(1001,1011)):
        for j,(level,allocation) in enumerate(configs):
            row=d[(d.scenario_id==sid)&d.level.eq(level)&d.allocation.eq(allocation)].iloc[0];matrix[i,j]=int(row.oracle_first_road);changed[i,j]=bool(row.first_road_changed)
    fig,ax=plt.subplots(figsize=(7.2,4.7));fig.subplots_adjust(left=.11,right=.97,bottom=.18,top=.85)
    ax.imshow(changed,cmap=ListedColormap(['#F0F0EA','#0072B2']),vmin=0,vmax=1,aspect='auto',interpolation='nearest')
    for i in range(10):
        for j in range(7):ax.text(j,i,str(matrix[i,j]),ha='center',va='center',fontsize=8,color='white' if changed[i,j] else '#333333',fontweight='bold' if changed[i,j] else 'normal')
    ax.set_xticks(range(7),['Uniform','M: depth','M: perm 1','M: perm 2','S: depth','S: perm 1','S: perm 2']);ax.set_yticks(range(10),list(range(1001,1011)));ax.set_ylabel('Flood scenario');ax.set_xlabel('Duration level and fixed assignment')
    ax.set_xticks(np.arange(-.5,7,1),minor=True);ax.set_yticks(np.arange(-.5,10,1),minor=True);ax.grid(which='minor',color='white',lw=1.5);ax.tick_params(which='minor',bottom=False,left=False)
    for spine in ax.spines.values():spine.set_visible(False)
    fig.text(.11,.95,'First road of the duration-aware offline optimum',fontsize=9)
    fig.legend(handles=[Patch(facecolor='#F0F0EA',label='Unchanged from uniform'),Patch(facecolor=BLUE,label='Changed from uniform')],loc='upper left',bbox_to_anchor=(.10,.92),ncol=2,frameon=False)
    fig.text(.11,.025,'Cell labels: physical road IDs. M: moderate; S: strong. Same 10 floods throughout.',fontsize=7)
    export(fig,'Figure_R1_5_4_policy_change')
    g=original[original.policy.eq('full_method')].sort_values('scenario_id');x=np.arange(10)
    fig,axs=plt.subplots(1,2,figsize=(7.2,3.6));fig.subplots_adjust(left=.10,right=.98,bottom=.24,top=.80,wspace=.36)
    for ax,y,ylabel,title,color,letter in zip(axs,[g.regret_pct,g.delta_ATT_minutes],['Regret (%)','Model-implied trip-time gap (min)'],['Relative gap','Absolute gap'],[BLUE,ORANGE],['a','b']):
        ax.bar(x,y,color=color,width=.65);ax.set_xticks(x,[str(i) for i in range(1001,1011)],rotation=55,ha='right');ax.set_xlim(-.7,9.7);ax.set_ylim(bottom=0);ax.set_ylabel(ylabel);ax.set_xlabel('Flood scenario');ax.set_title(title,pad=10);ax.text(-.10,1.04,letter,transform=ax.transAxes,fontweight='bold',fontsize=9);ax.grid(axis='y',color='#DDDDDD',lw=.5);ax.set_axisbelow(True)
    fig.text(.10,.95,'Equal-duration Full versus the accepted high-precision conditional DP',fontsize=9)
    fig.text(.10,.89,'10 paired floods; average static stage differences, not realized cumulative delay',fontsize=7)
    export(fig,'Figure_R1_5_4_absolute_time',True)
    print('3 figures exported as PDF / 600 dpi PNG / SVG',flush=True)
if __name__=='__main__':main()
