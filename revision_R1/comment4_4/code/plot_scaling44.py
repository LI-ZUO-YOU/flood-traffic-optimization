from common44 import *
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.transforms import ScaledTranslation
SKILL=Path(r'C:\Users\Wuzeqian.PC-20220914MSMS\.codex\skills\nature-figure')
sys.path.insert(0,str(SKILL/'scripts'))
from audit_panel_alignment import require_matplotlib_panel_alignment

# Original figure from the measured CSVs. Six paired feature inputs; repeats are technical, not independent scenarios.
def main():
 d=frame(OUT/'03_component_scaling/S3_component_profile_raw.csv');s=frame(OUT/'05_analysis/S3_scenario_means.csv');limits=js(OUT/'00_lock/calibrated_resource_limits.json')
 figdir=OUT/'05_analysis/figures';figdir.mkdir(exist_ok=True)
 contract={'question':'How does full-state surrogate candidate preparation grow with recovery-set size?','claim':'Measured time and process memory expose the full-subset architecture cost; m16 is a nonphysical feature fixture, and no decision-quality conclusion follows.',
 'archetype':'quantitative grid','backend':'python','size_mm':[178,78],'panel_a_role':'time resource burden with fixed 30k candidates','panel_b_role':'process memory burden including interpreter/model baseline','replication':'6 paired feature inputs; 3 fresh technical repetitions each, all retained','summary':'mean of 6 per-scenario means, whiskers min/max of those 6 means; raw scenario means shown','no_significance_tests':True,'exclusions':'none; incomplete preparations shown as censored, memory then a lower bound','m16':'Disconnected feature fixture only. No traffic assignment or quality claim.','source_data':[str(OUT/'03_component_scaling/S3_component_profile_raw.csv'),str(OUT/'05_analysis/S3_scenario_means.csv')]}
 dump(figdir/'figure_contract.json',contract)
 mpl.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':7,'axes.labelsize':8,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7,'svg.fonttype':'none','pdf.fonttype':42,'savefig.dpi':600})
 fig,axes=plt.subplots(1,2,figsize=(178/25.4,78/25.4));fig.subplots_adjust(left=.085,right=.985,bottom=.29,top=.88,wspace=.34)
 colors=['#2F647F','#735B87'];source=[]
 for ax,label,metric,color in zip(axes,['a','b'],['candidate_wall_mean','sampled_peak_RSS_mean_MiB'],colors):
  ax.text(0,1,label,transform=ax.transAxes+ScaledTranslation(-20/72,8/72,fig.dpi_scale_trans),fontweight='bold',fontsize=9,ha='left',va='bottom')
  for sid,g in s[s.m<=14].groupby('scenario_id'):
   g=g.sort_values('m');ax.plot(g.m,g[metric],color=color,alpha=.18,linewidth=.6,zorder=1)
  for m in [8,10,12,14,16]:
   g=s[s.m==m];valid=g[g.completed_repeats==3];vals=valid[metric].to_numpy(float)
   assert np.isfinite(vals).all(),'A completed scenario has a missing metric'
   if len(vals):
    avg=float(vals.mean());lo=float(vals.min());hi=float(vals.max());marker='s' if m==16 else 'o'
    ax.errorbar([m],[avg],yerr=[[avg-lo],[hi-avg]],fmt=marker,color=color,markerfacecolor='white' if m==16 else color,markersize=4,capsize=2,elinewidth=1,zorder=3)
    ax.scatter(np.full(len(vals),m),vals,s=7,color=color,alpha=.45,zorder=2)
    source.append({'panel':label,'m':m,'mean':avg,'min':lo,'max':hi,'n_scenario_means':len(vals),'physical_fixture':m==16})
   failures=int((d[d.m==m].status!='PASS').sum())
   if failures and metric=='candidate_wall_mean':ax.scatter([m],[limits['max_preprocessing_seconds']],marker='^',facecolors='none',edgecolors='#AD4F45',s=35,zorder=4)
  ax.set_xticks([8,10,12,14,16]);ax.set_xlim(7.5,16.5);ax.set_xlabel('log2(subset count), m');ax.tick_params(direction='out',length=3,width=.7)
 axes[0].set_ylabel('Candidate preparation (s)');axes[0].set_ylim(bottom=0)
 axes[1].set_ylabel('Sampled peak process RSS (MiB)');axes[1].set_ylim(bottom=0)
 # Figure-level explanation outside data rectangles. No in-plot masks or redundant labels.
 handles=[mpl.lines.Line2D([],[],marker='o',color='#555555',linestyle='none',markersize=4,label='Connected flood inputs (m ≤ 14)'),mpl.lines.Line2D([],[],marker='s',color='#555555',markerfacecolor='white',linestyle='none',markersize=4,label='Feature fixture only (m = 16)')]
 fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.025),ncol=2,columnspacing=2,frameon=False)
 fig.canvas.draw()
 require_matplotlib_panel_alignment(fig,json_out=str(figdir/'Fig_4_4_component_scaling.alignment.json'),overlay_svg=str(figdir/'Fig_4_4_component_scaling.alignment.svg'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,require_panel_labels=True,strict=True)
 fig.savefig(figdir/'Fig_4_4_component_scaling.pdf')
 fig.savefig(figdir/'Fig_4_4_component_scaling.svg')
 fig.savefig(figdir/'Fig_4_4_component_scaling.png',dpi=300)
 fig.savefig(figdir/'Fig_4_4_component_scaling.tiff',dpi=600)
 plt.close(fig);csv(figdir/'Fig_4_4_component_scaling_source_data.csv',source)
 (figdir/'Fig_4_4_legend.md').write_text('''**Figure draft. Full-subset candidate preparation as the recovery set grows.** a, Warm-code candidate preparation time, including full-state surrogate prediction, 89 subset-DP policies, 30,000-candidate construction and screening. b, Sampled peak RSS of the compute process during preparation and export, including the interpreter and frozen model baseline. Each size has six paired feature inputs with three fresh technical repetitions. Symbols show the mean of six scenario means; whiskers give their minimum and maximum. Faint lines/points retain scenario means. Filled circles use connected extended-severity flood inputs. Open squares at m=16 are disconnected computational feature fixtures and provide no recovery-decision evidence. No UE solver was called in these measurements. If a resource stop occurs, its time is right-censored and its memory is a lower bound. Technical repeats are not independent flood scenarios; no significance tests were performed.
''',encoding='utf-8')
if __name__=='__main__':main()
