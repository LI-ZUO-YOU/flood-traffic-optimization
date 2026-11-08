from common import *
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
SKILL=Path('C:/Users/Wuzeqian.PC-20220914MSMS/.codex/skills/nature-figure/scripts');sys.path.insert(0,str(SKILL))
from audit_panel_alignment import require_matplotlib_panel_alignment
mpl.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':8,'axes.labelsize':8,'xtick.labelsize':7.2,'ytick.labelsize':7.2,'legend.fontsize':7.2,'svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65})
def export(fig,name):
 fig.canvas.draw();require_matplotlib_panel_alignment(fig,json_out=OUT/f'audit/{name}_alignment.json',tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
 fig.savefig(OUT/f'figures/{name}.pdf');fig.savefig(OUT/f'figures/{name}.svg');fig.savefig(OUT/f'figures/{name}.png',dpi=600);plt.close(fig)
def main():
 init();f=read(OUT/'Table_R2C3_all10_depth_DP.csv');r=read(OUT/'Table_R2C3_threshold_invariance.csv');glob=read(OUT/'Table_R2C3_threshold_global_intersection.csv').iloc[0]
 dump(OUT/'audit/figure_contract.json',dict(backend='Python/matplotlib; reused established preference',archetype='quantitative grid',figure_depth=dict(question='How much does the same-set conditional optimal order change under both prescribed depth reductions?',evidence='All10 paired scenarios, complete-order Kendall tau; stars mark first-road changes; no exclusions',source='Table_R2C3_all10_depth_DP.csv',uncertainty='None: descriptive paired deterministic DP, ten existing floods not twenty independent samples'),figure_threshold=dict(question='What are the exact left-open right-closed invariant-mask intervals?',evidence='Per-scenario analytic extrema and global intersection; closed marker and open marker explicitly distinct',source='Table_R2C3_threshold_invariance.csv and Table_R2C3_threshold_global_intersection.csv',new_UE=0),formats=['PDF','SVG','600dpi PNG'],minimum_glyph_pt=7.2))
 A=np.array([[f[(f.scenario_id==sid)&(f.rho_depth==rho)].Kendall_tau.iloc[0] for rho in [.9,.95]] for sid in range(1001,1011)]);stars=np.array([[bool(f[(f.scenario_id==sid)&(f.rho_depth==rho)].first_road_changed.iloc[0]) for rho in [.9,.95]] for sid in range(1001,1011)])
 cmap=LinearSegmentedColormap.from_list('tau',['#e1ecf0','#28758a'])
 fig,ax=plt.subplots(figsize=(100/25.4,115/25.4));fig.subplots_adjust(left=.20,right=.78,bottom=.20,top=.95)
 im=ax.imshow(A,cmap=cmap,vmin=-1,vmax=1,interpolation='nearest',aspect='auto')
 for i in range(10):
  for j in range(2):ax.text(j,i,f'{A[i,j]:.3f}'+(' *' if stars[i,j] else ''),ha='center',va='center',fontsize=8,color='white' if A[i,j]>.2 else '#242424')
 ax.set_yticks(range(10),range(1001,1011));ax.set_ylabel('Original flood scenario');ax.set_xticks([0,1],['0.90','0.95']);ax.set_xlabel('Water-depth multiplier',labelpad=7);ax.tick_params(length=0,pad=5)
 cb=fig.colorbar(im,ax=ax,fraction=.07,pad=.08);cb.set_label('Full-order Kendall τ',labelpad=7);cb.set_ticks([-1,0,1]);cb.ax.tick_params(labelsize=7.2)
 fig.text(.5,.045,'* First reopening road changes',ha='center',fontsize=7.2)
 export(fig,'Figure_R2C3_extension_depth_order')
 fig,ax=plt.subplots(figsize=(180/25.4,100/25.4));fig.subplots_adjust(left=.105,right=.985,top=.95,bottom=.24)
 ax.axvspan(float(glob.h_open_max_global_m),float(glob.h_closed_min_global_m),color='#eeeeee',zorder=0)
 for i,row in enumerate(r.itertuples()):
  ax.plot([row.h_open_max_m,row.h_closed_min_m],[i,i],color='#387c8f',lw=1.4,zorder=2)
  ax.scatter([row.h_open_max_m],[i],s=28,facecolors='white',edgecolors='#387c8f',linewidths=1.1,zorder=3)
  ax.scatter([row.h_closed_min_m],[i],s=28,color='#387c8f',zorder=3)
 ax.axvline(.30,color='#333333',ls='--',lw=1,zorder=1)
 ax.set_yticks(range(10),r.scenario_id.astype(int));ax.invert_yaxis();ax.set_ylabel('Original flood scenario');ax.set_xlabel('Closure threshold (m)',labelpad=7)
 xmin=float(r.h_open_max_m.min())-.012;xmax=float(r.h_closed_min_m.max())+.012;ax.set_xlim(xmin,xmax);ax.set_xticks(np.arange(np.floor(xmin*100)/100,np.ceil(xmax*100)/100+.001,.02));ax.tick_params(axis='y',length=0);ax.grid(axis='x',color='#ffffff',lw=.6);ax.set_axisbelow(True)
 handles=[Line2D([],[],marker='o',ls='',markerfacecolor='white',markeredgecolor='#387c8f',label='Open lower endpoint'),Line2D([],[],marker='o',ls='',color='#387c8f',label='Closed upper endpoint'),Line2D([],[],color='#333333',ls='--',label='Original 0.30 m'),Patch(facecolor='#eeeeee',label='Common invariant interval')]
 fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.55,.018),ncol=2,frameon=False)
 export(fig,'Figure_R2C3_extension_threshold_interval')
 (OUT/'figures/Figure_captions_EN.md').write_text('''# Supplement figure captions, final numbering pending

**All-scenario depth-order sensitivity.** Complete-order Kendall τ against the original high-precision conditional DP optimum for the same ten-road recovery set. Each of the ten frozen floods appears under both depth reductions. Asterisks mark a changed first reopening road. Unchanged orders remain visible as τ=1. The20 perturbations are paired conditions of the same10 floods, not20 independent flood samples. No significance tests are performed. Full orders, near-tie diagnostics and original-DP transfer regret are supplied in the source CSV. The optima are offline conditional exact DP of RG≤1e−9 numerical UE costs, not new budgeted-search runs.

**Closure-threshold invariant-mask intervals.** For each frozen38-road depth vector the exact interval is max_open_depth<h_c≤min_closed_depth. Open circles exclude the lower endpoint; filled circles include the upper endpoint. The shaded band is the intersection across all ten scenarios and the dashed line marks the original0.30m. Endpoints and one-floating-step boundary checks were recomputed from local frozen inputs. All1024 recovered-subset active/FFT/effective-capacity/BPR inputs were compared inside the interval without UE. The interval preserves the original closure mask; it is not a generic connected-network interval or an empirically calibrated safety margin. The broad separation follows from the synthetic generator selecting connected closures before assigning separated closed/open depth ranges.
''',encoding='utf-8')
if __name__=='__main__':main()
