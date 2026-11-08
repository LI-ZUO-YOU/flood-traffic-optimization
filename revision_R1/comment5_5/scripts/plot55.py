from pathlib import Path
import sys,os
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parents[1]
os.environ['MPLCONFIGDIR']=str(OUT/'runtime_cache/matplotlib')
sys.path.insert(0,'E:/jcr2区意见/返稿/4.1专项返修_20261026/runtime_deps');sys.path.insert(0,'C:/Users/Wuzeqian.PC-20220914MSMS/.codex/skills/nature-figure/scripts')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from audit_panel_alignment import require_matplotlib_panel_alignment
plt.rcParams.update({'font.family':'Arial','font.size':8,'axes.labelsize':8,'axes.titlesize':9,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7,'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','savefig.dpi':600,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7})
BLUE='#0072B2';ORANGE='#D55E00';GREEN='#009E73';PURPLE='#882E72'
def export(fig,name):
 fig.canvas.draw();require_matplotlib_panel_alignment(fig,json_out=OUT/'figures'/f'{name}.alignment.json',overlay_svg=OUT/'figures'/f'{name}.alignment.svg',tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
 fig.savefig(OUT/'figures'/f'{name}.pdf');fig.savefig(OUT/'figures'/f'{name}.png',dpi=600);fig.savefig(OUT/'figures'/f'{name}.svg');plt.close(fig)
def finish_axes(ax,title,ylabel,letter):
 ax.set_xticks(range(10),list(map(str,range(1001,1011))),rotation=55,ha='right',rotation_mode='anchor');ax.set_xlim(-.6,9.6);ax.set_xlabel('Flood scenario');ax.set_title(title,pad=10);ax.set_ylabel(ylabel);ax.text(-.10,1.04,letter,transform=ax.transAxes,fontweight='bold',fontsize=9);ax.grid(axis='y',lw=.5,color='#DDDDDD');ax.set_axisbelow(True)
def main():
 rules=pd.read_csv(OUT/'Table_rule_label_results.csv');terminal=pd.read_csv(OUT/'Table_terminal_residual_by_portfolio.csv');cf=pd.read_csv(OUT/'Table_allclosed_counterfactual.csv')
 fig,axs=plt.subplots(1,2,figsize=(7.2,3.9));fig.subplots_adjust(left=.095,right=.98,bottom=.25,top=.76,wspace=.35)
 for ax,metric,title,ylabel,letter in zip(axs,['selection_gain_pct','delta_model_ATT_minutes'],['Cumulative selection gain','Absolute traffic difference'],['Gain versus original (%)','Model-implied trip-time gain (min)'],['a','b']):
  for sid in [1002,1006,1010]:ax.axvspan(sid-1001-.42,sid-1001+.42,color='#EFEFEF',zorder=0)
  ax.axhline(0,color='#555555',lw=.8,zorder=1)
  for label,color,marker,offset in [('A1',BLUE,'o',-.16),('A2',ORANGE,'s',0.),('A3',GREEN,'^',.16)]:
   g=rules[rules.label.eq(label)];ax.scatter(g.scenario_id-1001+offset,g[metric],c=color,marker=marker,s=23,linewidths=.35,edgecolors='white',zorder=3)
  finish_axes(ax,title,ylabel,letter)
 fig.text(.095,.96,'Alternative preselection under conditional full-information UE–DP',fontsize=9)
 fig.legend(handles=[Line2D([],[],color=BLUE,marker='o',ls='',label='Flow-only'),Line2D([],[],color=ORANGE,marker='s',ls='',label='Betweenness-only'),Line2D([],[],color=GREEN,marker='^',ls='',label='Diagnostic swap')],loc='upper left',bbox_to_anchor=(.08,.93),ncol=3,frameon=False)
 fig.text(.095,.045,'Positive = alternative better. Gray bands = no alternative ten-road set. Ten floods, seven with choice.',fontsize=7)
 export(fig,'Figure_R1_5_5_selection_sensitivity')
 fig,axs=plt.subplots(1,2,figsize=(7.2,3.9));fig.subplots_adjust(left=.095,right=.98,bottom=.25,top=.76,wspace=.35)
 for ax,metric,cmetric,title,ylabel,letter in zip(axs,['terminal_ATT_minutes','residual_closed_count'],['ATT_allclosed_minutes',None],['Residual traffic cost','Unrestored closed roads'],['Terminal model-implied ATT (min)','Originally closed roads remaining'],['a','b']):
  for sid in range(1001,1011):
   group=terminal[terminal.scenario_id.eq(sid)];base=group[group.is_original].iloc[0];alternatives=group[~group.is_original].sort_values('portfolio_id')
   ax.scatter(sid-1001-.22,base[metric],color='#333333',marker='o',s=24,zorder=3)
   for j,(_,r) in enumerate(alternatives.iterrows()):ax.scatter(sid-1001-.02+.15*j,r[metric],color=ORANGE,marker='^',s=24,zorder=3)
  ax.scatter(cf.scenario_id-1001+.30,cf[cmetric] if cmetric else np.zeros(len(cf)),color=PURPLE,marker='D',s=21,zorder=3)
  finish_axes(ax,title,ylabel,letter)
  if cmetric is None:ax.set_yticks([0,1,2]);ax.set_ylim(-.12,2.35)
  else:ax.set_ylim(bottom=0)
 fig.text(.095,.96,'Terminal selected-intervention completion is not whole-network recovery',fontsize=9)
 fig.legend(handles=[Line2D([],[],color='#333333',marker='o',ls='',label='Original set'),Line2D([],[],color=ORANGE,marker='^',ls='',label='Distinct alternative'),Line2D([],[],color=PURPLE,marker='D',ls='',label='All initially closed restored')],loc='upper left',bbox_to_anchor=(.08,.93),ncol=3,frameon=False)
 fig.text(.095,.045,'Initially open wet roads retain flood effects. Counterfactual has zero remaining closures, not zero disruption.',fontsize=7)
 export(fig,'Figure_R1_5_5_terminal_residual');print('2 figures exported PDF / PNG600dpi / SVG',flush=True)
if __name__=='__main__':main()
