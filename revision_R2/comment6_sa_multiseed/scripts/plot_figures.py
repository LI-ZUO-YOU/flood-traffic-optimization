from common import *
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
SKILL=Path('C:/Users/Wuzeqian.PC-20220914MSMS/.codex/skills/nature-figure/scripts');sys.path.insert(0,str(SKILL))
from audit_panel_alignment import require_matplotlib_panel_alignment
mpl.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':8,'axes.labelsize':8,'xtick.labelsize':7.2,'ytick.labelsize':7.2,'legend.fontsize':7.2,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65})
def export(fig,name):
 fig.canvas.draw();require_matplotlib_panel_alignment(fig,json_out=OUT/f'audit/{name}_alignment.json',tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
 fig.savefig(OUT/f'figures/{name}.pdf');fig.savefig(OUT/f'figures/{name}.svg');fig.savefig(OUT/f'figures/{name}.png',dpi=600);plt.close(fig)
def main():
 f=read(OUT/'raw/SA_all100_runs.csv');P=read(OUT/'audit/Proposed_frozen_B256_highprecision.csv').set_index('scenario_id');data=[f[f.scenario_id.eq(sid)].sort_values('replicate').regret_pct.to_numpy() for sid in range(1001,1011)]
 dump(OUT/'audit/figure_contract.json',dict(backend='Python/matplotlib established preference',archetype='quantitative grid',figure1=dict(question='How variable is original SA across the prespecified seeds in each original scenario?',evidence='All 100 seed points, numerical single-seed HP rerun, old lowprecision seed and frozen Proposed path, no favorable selection',unit='10 scenarios with 10 technical seed repeats; Proposed one frozen path',source='SA_all100_runs.csv; Proposed_frozen_B256_highprecision.csv; original result JSON'),figure2=dict(question='How much of the independent B256 cap was actually used and what outcomes accompany it?',evidence='All 100 actual charged-query/regret points, original seed identified; no fitted relationship or causal claim',source='SA_all100_runs.csv'),formats=['PDF','SVG','600dpi PNG'],font_floor_pt=7.2))
 fig,ax=plt.subplots(figsize=(180/25.4,107/25.4));fig.subplots_adjust(left=.10,right=.985,top=.95,bottom=.30)
 boxes=ax.boxplot(data,positions=np.arange(10),widths=.46,showfliers=False,patch_artist=True,medianprops=dict(color='#24576a',linewidth=1),boxprops=dict(edgecolor='#86a7b3',linewidth=.7),whiskerprops=dict(color='#86a7b3',linewidth=.7),capprops=dict(color='#86a7b3',linewidth=.7))
 for box in boxes['boxes']:box.set_facecolor('#e0ebef')
 offsets=np.linspace(-.21,.21,10)
 for x,sid in enumerate(range(1001,1011)):
  sub=f[f.scenario_id.eq(sid)].sort_values('replicate');ax.scatter(x+offsets,sub.regret_pct,s=12,color='#286f8e',alpha=.75,zorder=3)
  rep0=sub[sub.replicate.eq(0)].iloc[0];ax.scatter([x+offsets[0]],[rep0.regret_pct],s=42,facecolors='none',edgecolors='#b9682b',linewidths=1.2,zorder=5)
  old=js(SA_ARCHIVE/f'final_once_only/scenario_{sid}/result.json')['relative_regret_pct'];ax.scatter([x-.34],[old],s=26,marker='^',color='#888888',zorder=4)
  ax.scatter([x+.33],[P.loc[sid,'regret_pct']],s=30,marker='x',color='#222222',linewidths=1.1,zorder=4)
 ax.set_xticks(range(10),range(1001,1011));ax.set_xlabel('Original flood scenario',labelpad=7);ax.set_ylabel('Conditional regret (%)');ax.set_xlim(-.6,9.6);ax.set_ylim(-.12,max(f.regret_pct.max(),P.regret_pct.max())*1.12);ax.axhline(0,color='#cccccc',lw=.6,zorder=0);ax.grid(axis='y',color='#eeeeee',lw=.5);ax.set_axisbelow(True)
 handles=[Line2D([],[],marker='o',ls='',markersize=4,color='#286f8e',label='SA seeds, high precision'),Line2D([],[],marker='o',ls='',markerfacecolor='none',markeredgecolor='#b9682b',label='Original seed, HP rerun'),Line2D([],[],marker='^',ls='',color='#888888',label='Original seed, old precision'),Line2D([],[],marker='x',ls='',color='#222222',label='Proposed frozen B256, HP')]
 fig.legend(handles=handles,ncol=2,loc='lower center',bbox_to_anchor=(.55,.045),frameon=False,columnspacing=2)
 export(fig,'Figure_R2C6_SA_seed_stability')
 fig,ax=plt.subplots(figsize=(150/25.4,100/25.4));fig.subplots_adjust(left=.12,right=.98,top=.95,bottom=.24)
 ax.scatter(f.queries_charged,f.regret_pct,s=23,color='#286f8e',alpha=.55,edgecolors='none')
 r0=f[f.replicate.eq(0)];ax.scatter(r0.queries_charged,r0.regret_pct,s=55,facecolors='none',edgecolors='#b9682b',linewidths=1.1)
 ax.axvline(256,color='#555555',ls='--',lw=.8);ax.axhline(0,color='#cccccc',lw=.6);ax.set_xlim(float(f.queries_charged.min())-5,261);ax.set_ylim(-.12,float(f.regret_pct.max())*1.12);ax.set_xticks([200,220,240,256]);ax.set_xlabel('Charged unique UE-state queries per run',labelpad=7);ax.set_ylabel('Conditional regret (%)');ax.grid(axis='y',color='#eeeeee',lw=.5);ax.set_axisbelow(True)
 fig.legend(handles=[handles[0],handles[1],Line2D([],[],ls='--',color='#555555',label='Independent cap B = 256')],ncol=1,loc='lower center',bbox_to_anchor=(.55,.015),frameon=False)
 export(fig,'Figure_R2C6_budget_and_regret')
 (OUT/'figures/Figure_captions_EN.md').write_text('''# Figure captions, final numbers pending master integration

**SA seed stability on the ten original flood scenarios.** All 100 prespecified high-precision SA runs are plotted, ten per scenario. Boxes show seed median and interquartile range with 1.5 IQR whiskers; all observations, including outliers, appear as individual points. Horizontal offsets identify seed repeats and do not change values. Orange rings mark replicate 0 rerun on the high-precision oracle; gray triangles retain the historical low-precision result at the same original seed and are not included in the high-precision boxes. Crosses show one frozen original Proposed B256 path re-evaluated on the same high-precision costs. SA was rerun with high-precision feedback, whereas Proposed was not rerun; this asymmetry is retained. There are ten flood-scenario units, not 100 independent floods. Regret uses the original conditional high-precision reference; numerical hits use the frozen rule |J−J*|≤1e-9 max(1,|J*|). Tiny signed float differences remain in raw CSV. No significance tests or best-of-ten B256 claim are made.

**Actual logical budget use and regret.** All 100 independent SA runs under the same B256 cap, with original-seed high-precision runs highlighted. Coincident markers are retained with transparency; coordinates are not jittered. 27 runs naturally stopped below 256 queries after 1000 proposals without a newly queried state, and no run was filled artificially. The relation is descriptive and is not evidence that lower budget use causes worse outcomes. Queries are method-specific unique restored-subset requests to a sealed numerical oracle, not newly executed traffic assignment. Search timings exclude offline high-precision table generation and are not real online-UE timings.
''',encoding='utf-8')
if __name__=='__main__':main()
