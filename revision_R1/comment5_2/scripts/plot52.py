"""Figures from completed, validated demand-sensitivity CSVs only."""
from pathlib import Path
import os, sys, json
OUT=Path(__file__).resolve().parents[1]
os.environ['MPLCONFIGDIR']=str(OUT/'runtime_cache/matplotlib')
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
# Reuse the already available Python 3.11 scientific environment; the desktop
# bundled Python 3.12 does not contain matplotlib. The plotting backend remains Python.
sys.path.insert(0,'E:/jcr2区意见/返稿/4.1专项返修_20261026/runtime_deps')
sys.path.insert(0,'C:/Users/Wuzeqian.PC-20220914MSMS/.codex/skills/nature-figure/scripts')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from audit_panel_alignment import require_matplotlib_panel_alignment

matplotlib.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':8,'axes.labelsize':8,'axes.titlesize':8.5,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':8,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7,'xtick.major.width':.6,'ytick.major.width':.6,'legend.frameon':False,'svg.fonttype':'none','pdf.fonttype':42,'savefig.dpi':600,'figure.facecolor':'white'})
COLORS={1.:'#315F88',.75:'#D28B39',.5:'#3E8A80'}
RHO=[1.,.75,.5]
REP=[1006,1003,1008]
stage=pd.read_csv(OUT/'stage_metrics_all10.csv',float_precision='round_trip')
policy=pd.read_csv(OUT/'demand_dp_policy_comparison.csv',float_precision='round_trip')
assert len(stage)==660 and len(policy)==18
assert set(stage.scenario_id)==set(range(1001,1011))
assert (stage.att_hours>0).all()

def letter(ax,text):
 ax.text(-.13,1.035,text,transform=ax.transAxes,fontweight='bold',fontsize=9,ha='left',va='bottom')

def save(fig,name):
 fig.canvas.draw()
 require_matplotlib_panel_alignment(fig,json_out=OUT/'figures'/f'{name}.alignment.json',overlay_svg=OUT/'figures'/f'{name}.alignment.svg',tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
 fig.savefig(OUT/'figures'/f'{name}.pdf')
 fig.savefig(OUT/'figures'/f'{name}.svg')
 fig.savefig(OUT/'figures'/f'{name}.png',dpi=600)
 plt.close(fig)

handles=[Line2D([0],[0],color=COLORS[r],marker='o',markersize=3,linewidth=1.3,label=f'{r:.0%} OD') for r in RHO]
fig,axes=plt.subplots(1,3,figsize=(7.2,2.75),sharex=True,sharey=True)
fig.subplots_adjust(left=.095,right=.98,bottom=.20,top=.79,wspace=.28)
for j,(sid,ax) in enumerate(zip(REP,axes)):
 for rho in RHO:
  g=stage[(stage.scenario_id==sid)&(stage.method=='full_method')&(stage.rho==rho)].sort_values('stage')
  assert len(g)==11
  ax.plot(g.stage,g.att_hours,color=COLORS[rho],marker='o',markersize=2.8,lw=1.3)
  ax.plot([10],[g.att_hours.iloc[-1]],color=COLORS[rho],marker='o',mfc='white',mec=COLORS[rho],markersize=4,lw=0)
 ax.set_yscale('log');ax.set_ylim(.1,400);ax.set_xlim(-.2,10.3);ax.set_xticks([0,1,3,5,7,9,10]);ax.set_yticks([.1,1,10,100],labels=['0.1','1','10','100'])
 ax.set_xlabel('Restoration stage');ax.set_title(f'Rank {[1,5,10][j]}, scenario {sid}',pad=8)
 letter(ax,'abc'[j])
axes[0].set_ylabel('Average trip time (h)\nLogarithmic scale')
fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.54,.995),ncol=3,columnspacing=2)
save(fig,'Figure_R1_5_2_trajectory')

fig,axes=plt.subplots(2,3,figsize=(7.2,4.7),sharex=True,sharey='row')
fig.subplots_adjust(left=.095,right=.98,bottom=.12,top=.87,wspace=.28,hspace=.52)
for j,sid in enumerate(REP):
 for rho in RHO:
  g=stage[(stage.scenario_id==sid)&(stage.method=='full_method')&(stage.rho==rho)].sort_values('stage')
  share=np.array([sum(v['contribution_veh_h'] for v in json.loads(a))/t*100 for a,t in zip(g.top_5_links_by_tstt_contribution,g.diagnostic_tstt_raw*.01)])
  assert np.isfinite(share).all() and (share>=0).all() and (share<=100.000001).all()
  axes[0,j].plot(g.stage,g.max_vc,color=COLORS[rho],marker='o',markersize=2.5,lw=1.2)
  axes[1,j].plot(g.stage,share,color=COLORS[rho],marker='o',markersize=2.5,lw=1.2)
 axes[0,j].set_title(f'Scenario {sid}',pad=8)
 for i in range(2):
  axes[i,j].set_xlim(-.2,10.3);axes[i,j].set_xticks([0,1,3,5,7,9,10]);letter(axes[i,j],'abcdef'[i*3+j])
 axes[0,j].set_ylim(0,16);axes[1,j].set_ylim(0,100);axes[1,j].set_xlabel('Restoration stage')
axes[0,0].set_ylabel('Maximum flow / capacity')
axes[1,0].set_ylabel('Top-five-arc TSTT share (%)')
fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.54,.995),ncol=3,columnspacing=2)
save(fig,'Figure_R1_5_2_bottleneck')

fig,axes=plt.subplots(1,2,figsize=(7.2,2.85),sharey=True)
fig.subplots_adjust(left=.095,right=.98,bottom=.24,top=.78,wspace=.27)
method_styles=[('full_method','Frozen full method','#315F88','o',-.075),('exact_DP_original_rho1','Frozen original DP','#B67E3D','s',.075)]
maxgap=float(policy[policy.method!='exact_DP_demand_specific'].delta_mean_trip_minutes.max())
for j,(rho,ax) in enumerate(zip([.75,.5],axes)):
 for method,label,color,marker,offset in method_styles:
  g=policy[(policy.rho==rho)&(policy.method==method)].set_index('scenario_id').loc[REP]
  ax.plot(np.arange(3)+offset,g.delta_mean_trip_minutes,marker=marker,linestyle='none',markersize=5,color=color,label=label)
 ax.axhline(0,color='.65',lw=.7,zorder=0);ax.set_xticks(range(3),labels=[str(s) for s in REP]);ax.set_xlim(-.4,2.4);ax.set_ylim(-.1,maxgap*1.17)
 ax.set_xlabel('Prespecified representative scenario');ax.set_title(f'{rho:.0%} OD',pad=8);letter(ax,'ab'[j])
axes[0].set_ylabel('Mean trip-time gap\n(minutes vs new DP)')
fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.54,.995),ncol=2,columnspacing=2)
save(fig,'Figure_R1_5_2_demand_policy')

captions='''# English figure captions

**Figure R1 5.2 trajectory. Absolute trip-time trajectories under exogenous demand reduction.** Panels a, b and c show scenarios 1006, 1003 and 1008, selected before the demand experiments as ranks 1, 5 and 10 in the original full-demand conditional optimum. All original full-method restoration sequences are fixed. Curves show 100%, 75% and 50% of the original OD matrix, with unchanged capacities, BPR parameters, flood depths and restoration scope. ATT is TSTT × 0.01 divided by total OD demand; the vertical axis is logarithmic in hours. All eleven states are shown. Open markers at stage 10 denote completion of the selected interventions, with zero objective weight, rather than complete network recovery. These are deterministic static-model outcomes for three prespecified cases, not observed travel times; no confidence intervals or significance tests are implied. Source data are stage_metrics_all10.csv.

**Figure R1 5.2 bottleneck. Open-arc bottleneck intensity and concentration of travel-time contributions.** Columns show the same three prespecified cases. Panels a to c show maximum flow-to-capacity ratio among open directed arcs; panels d to f show the fraction of total TSTT contributed by the five directed arcs with largest flow × congested travel time at each state. The identities of those arcs may change across stages and demand levels; the ranked records and complete open-arc diagnostics are provided in raw/top5_bottleneck_links.csv, bottleneck_links.csv and raw/all_new_UE_open_arc_flows.csv.gz. Closed arcs are excluded. The frozen full-method sequences are used throughout. Demand multipliers are hypothetical external changes, not calibrated elastic demand. All eleven states are shown without smoothing or omitted extremes. These deterministic model diagnostics do not identify a causal physical flood mechanism.

**Figure R1 5.2 demand policy. Absolute cost of transferring frozen sequences to reduced demand.** Panels a and b show 75% and 50% OD demand. For each of three prespecified scenarios, circles and squares compare the frozen full-method and original full-demand DP sequences with a new demand-conditional DP reference. The vertical axis is the difference in ten-stage mean trip time, computed as (J_method − Jstar_rho) × TSTT0_raw(rho) × 0.01 × 60 / (rho × 360600). Each reference uses the complete 1,024-state table with RG ≤ 1e-9. Zero denotes the new conditional optimum. This is post-hoc fixed-path transfer sensitivity, not a new confirmatory evaluation or a demand-calibrated surrogate policy. No independent sample enlargement or inferential tests are implied. Source data are demand_dp_policy_comparison.csv.
'''
(OUT/'figures/Figure_captions_EN.md').write_text(captions,encoding='utf-8')
print('Created three figures, each PDF/SVG/PNG; all rendered panel alignment gates passed.')
