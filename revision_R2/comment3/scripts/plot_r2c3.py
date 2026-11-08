from common import *
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
SKILL=Path('C:/Users/Wuzeqian.PC-20220914MSMS/.codex/skills/nature-figure/scripts');sys.path.insert(0,str(SKILL))
from audit_panel_alignment import require_matplotlib_panel_alignment
mpl.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':8,'axes.labelsize':8,'xtick.labelsize':7.2,'ytick.labelsize':7.2,'legend.fontsize':7.2,'svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65,'savefig.dpi':600})
def export(fig,name):
 fig.canvas.draw();require_matplotlib_panel_alignment(fig,json_out=OUT/f'audit/{name}_alignment.json',tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
 fig.savefig(OUT/f'figures/{name}.pdf')
 fig.savefig(OUT/f'figures/{name}.svg')
 fig.savefig(OUT/f'figures/{name}.png',dpi=600)
 plt.close(fig)
def main():
 data=js(OUT/'raw/analysis_all_conditions.json');lookup={r['variant_id']:r for r in data}
 contract={'backend':'Python/matplotlib','archetype':'quantitative grid','width_mm':180,'min_font_pt':7.2,'statistics':'10 original flood scenarios for topology; 3 prospectively fixed representatives for DP; variants are paired conditions, not independent samples; no inference tests','figure1':{'question':'Which fixed input perturbations leave the connected fixed-demand decision domain?','claim':'Disconnected conditions have no finite UE optimum; numbers are closure counts, not UE outcomes.','panels':'single all-conditions heatmap','data':'Table_R2C3_all10_feasibility.csv'},'figure2':{'question':'How do conditional costs and admissible order comparisons change?','claim':'Input sensitivity can change costs and order; changed portfolios require shared-road comparisons.','panels':'top row mean-stage ATT by representative; bottom row full or shared-road Kendall with distinct markers','data':'Table_R2C3_conditional_DP.csv and all-condition metadata'}}
 dump(OUT/'audit/figure_contract.json',contract)
 conditions=[('depth',v) for v in [.9,.95,1.,1.05,1.1]]+[('threshold',v) for v in [.28,.3,.32]]+[('correlation',v) for v in ['original',3.,6.]]
 A=np.zeros((10,11));N=np.zeros((10,11),int)
 for i,sid in enumerate(range(1001,1011)):
  for j,(factor,level) in enumerate(conditions):
   r=lookup[f'{sid}_{factor}_{level}'];A[i,j]=r['validity_status']!='VALID';N[i,j]=r['closed_count']
 fig,ax=plt.subplots(figsize=(180/25.4,106/25.4));fig.subplots_adjust(left=.10,right=.98,top=.96,bottom=.25)
 ax.imshow(A,cmap=ListedColormap(['#d7e8e6','#f4c6b5']),vmin=0,vmax=1,aspect='auto',interpolation='nearest')
 for i in range(10):
  for j in range(11):ax.text(j,i,str(N[i,j])+(' ×' if A[i,j] else ''),ha='center',va='center',fontsize=8,color='#242424')
 ax.set_yticks(range(10),range(1001,1011));ax.set_ylabel('Original flood scenario')
 labels=['Depth\n0.90','Depth\n0.95','Depth\n1.00','Depth\n1.05','Depth\n1.10','τ (m)\n0.28','τ (m)\n0.30','τ (m)\n0.32','λ (km)\nOriginal','λ (km)\n3.0','λ (km)\n6.0']
 ax.set_xticks(range(11),labels);ax.tick_params(axis='both',length=0,pad=5)
 for x in [4.5,7.5]:ax.axvline(x,color='white',lw=3)
 ax.legend(handles=[Patch(facecolor='#d7e8e6',label='All 528 OD reachable, ≥10 closed roads'),Patch(facecolor='#f4c6b5',label='× OD unreachable; no finite UE optimum')],loc='upper center',bbox_to_anchor=(.5,-.20),ncol=1,frameon=False)
 export(fig,'Figure_R2C3_feasibility')
 fig,axes=plt.subplots(2,3,figsize=(180/25.4,132/25.4),gridspec_kw={'height_ratios':[1,1]});fig.subplots_adjust(left=.105,right=.985,bottom=.17,top=.91,wspace=.33,hspace=.35)
 tags=['depth_0.95','depth_1.0','depth_1.05','correlation_3.0','correlation_6.0'];labels=['h −5%','Base','h +5%','λ 3','λ 6']
 for col,sid in enumerate([1006,1003,1008]):
  ax=axes[0,col];tauax=axes[1,col];base=lookup[f'{sid}_depth_1.0'];ax.axhline(base['mean_stage_ATT_min'],color='#777777',lw=.8,ls='--',zorder=1)
  values=[lookup[f'{sid}_{t}'] for t in tags];maxval=max(r['mean_stage_ATT_min'] or 0 for r in values);ax.set_ylim(0,maxval*1.22)
  for x,r in enumerate(values):
   if r['J_star'] is None:
    ax.text(x,-.10,'OD unreachable',transform=ax.get_xaxis_transform(),color='#9d492e',ha='center',va='top',fontsize=7.2);continue
   same=r['portfolio_comparability']=='SAME_E';color='#286f8e' if same else '#b76d24';marker='o' if same else 'D'
   ax.scatter(x,r['mean_stage_ATT_min'],s=28,marker=marker,color=color,zorder=3)
   tau=r['complete_Kendall_tau'] if same else r['common_subsequence_Kendall_tau']
   tauax.scatter(x,tau,s=28,marker=marker,color=color,zorder=3)
  ax.set_title(f'Scenario {sid}',fontsize=8.5,pad=10);ax.set_xticks(range(5),['']*5);ax.tick_params(axis='x',length=0)
  tauax.axhline(1,color='#777777',lw=.8,ls='--',zorder=1);tauax.set_ylim(-1.15,1.15);tauax.set_yticks([-1,0,1]);tauax.set_xticks(range(5),labels);tauax.tick_params(axis='x',length=0,pad=5)
  for a in [ax,tauax]:a.set_xlim(-.55,4.55);a.grid(axis='y',color='#eeeeee',lw=.5);a.set_axisbelow(True)
  ax.set_ylabel('Mean-stage ATT (min)');tauax.set_ylabel('Kendall τ')
  ax.text(-.16,1.04,chr(97+col),transform=ax.transAxes,fontweight='bold',fontsize=9);tauax.text(-.16,1.04,chr(100+col),transform=tauax.transAxes,fontweight='bold',fontsize=9)
 fig.legend(handles=[Line2D([],[],marker='o',ls='',color='#286f8e',label='Same recovery set: full-order τ'),Line2D([],[],marker='D',ls='',color='#b76d24',label='Changed set: shared-road τ only')],loc='lower center',bbox_to_anchor=(.54,.025),ncol=1,frameon=False)
 export(fig,'Figure_R2C3_sequence_sensitivity')
 (OUT/'figures/Figure_captions_EN.md').write_text('''# Figure captions

**Figure R2C3 feasibility.** All ten frozen floods under one-factor changes. Each cell reports the number of initially closed physical roads. A cross indicates one or more unreachable positive-demand OD pairs and no finite fixed-demand UE objective. Depth ±10% is topology preaudit only. Correlation endpoints use paired original random factors and the original connectivity-constrained generator, so their connected outputs do not estimate disconnection probabilities. Repeated baseline columns are intentional. Conditions are not independent flood samples.

**Figure R2C3 sequence sensitivity.** The three fixed representative floods. Top panels show model-implied mean stage travel time per trip, not elapsed restoration time. Dashed lines mark original values. Bottom panels distinguish complete-order Kendall τ for unchanged recovery sets (circles, 45 comparable road pairs) from Kendall τ of shared-road subsequences for changed sets (diamonds, pair counts in the CSV). Missing points for scenario1008 at +5% indicate unreachable OD, not zero cost or zero similarity. The original connectivity constraint remains active in correlation-field generation. All optima are offline conditional exact subset-DP solutions of numerical RG≤1e−9 UE tables, with S0–S9 weighted and S10 excluded. No new optimizer or surrogate was run; no significance inference is made from three representatives.
''',encoding='utf-8')
if __name__=='__main__':main()
