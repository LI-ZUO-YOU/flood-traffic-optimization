from batch2_common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import subprocess
QA=Path(r'C:/Users/Wuzeqian.PC-20220914MSMS/.codex/skills/nature-figure/scripts')
sys.path.insert(0,str(QA))
from audit_panel_alignment import require_matplotlib_panel_alignment
FOCUS=['proposed']+COMPARATORS
COLORS={'proposed':'#0072B2','sa_original':'#D55E00','sa_restart':'#777777','greedy_ils':'#009E73','ue_bibeam':'#CC79A7'}
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':7,'axes.labelsize':7,'axes.titlesize':8,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7,'svg.fonttype':'none','pdf.fonttype':42,'axes.linewidth':.6,'axes.spines.top':False,'axes.spines.right':False})

def title(ax,letter,text):
 ax.set_title(text,loc='left',pad=14);ax.text(-.17,1.10,letter,transform=ax.transAxes,fontweight='bold',fontsize=9);ax.tick_params(length=3,pad=3)

def export(fig,axes,name,p):
 folder=p['figures'];fig.canvas.draw();require_matplotlib_panel_alignment(fig,axes=list(axes),panel_ids=['a','b'],json_out=folder/(name+'_alignment.json'),overlay_svg=folder/(name+'_alignment_overlay.svg'),strict=True)
 fig.savefig(folder/(name+'.pdf'));fig.savefig(folder/(name+'.svg'));fig.savefig(folder/(name+'.png'),dpi=600,facecolor='white');plt.close(fig)

def tails(out,p):
 sc=frame(Path(out)/'02_new30/new30_scenario_level.csv');csv(p['figures']/'Fig_new30_tails_source.csv',sc)
 fig,axs=plt.subplots(1,2,figsize=(183/25.4,84/25.4));fig.subplots_adjust(left=.10,right=.97,bottom=.24,top=.83,wspace=.52);a,b=axs
 for i,m in enumerate(FOCUS):
  d=sc[sc.method==m].sort_values('scenario_id');z=np.sort(d.mean_regret_pct.to_numpy());a.step(np.r_[0,z],np.r_[0,np.arange(1,31)/30],where='post',color=COLORS[m],label=LABEL[m],lw=1.2 if m=='proposed' else .9)
  b.scatter(d.mean_regret_pct,i+np.linspace(-.14,.14,30),s=15,facecolors='none',edgecolors=COLORS[m],linewidths=.7,alpha=.8)
  if m=='proposed':
   for sid,marker,dy in [(3026,'D',7),(3029,'^',12)]:
    r=d[d.scenario_id==sid].iloc[0];yy=i+np.linspace(-.14,.14,30)[sid-3001];b.scatter([r.mean_regret_pct],[yy],s=27,color=COLORS[m],marker=marker,zorder=5);b.annotate(str(sid),xy=(r.mean_regret_pct,yy),xytext=(1,dy),textcoords='offset points',ha='center',fontsize=7)
 a.set(xlim=(-.12,6.5),ylim=(-.03,1.04),xlabel='Scenario-mean regret (%)',ylabel='Empirical cumulative proportion');title(a,'a','All 30 scenario means, ECDF')
 b.set_yticks(range(5),[LABEL[m] for m in FOCUS]);b.set(xlim=(-.12,6.65),ylim=(4.65,-.65),xlabel='Scenario-mean regret (%)');title(b,'b','All observations, no exclusions')
 fig.legend(*a.get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.5,.025),ncol=5,frameon=False,handlelength=1.7,columnspacing=1.1)
 export(fig,axs,'Fig_new30_tails',p)

def variance(p):
 v=frame(p['variance']/'variance_components.csv').set_index('method').loc[STOCH];csv(p['figures']/'Fig_scenario_vs_seed_source.csv',v.reset_index())
 fig,axs=plt.subplots(1,2,figsize=(183/25.4,94/25.4));fig.subplots_adjust(left=.16,right=.97,bottom=.25,top=.84,wspace=.58);a,b=axs;x=np.arange(5)
 a.barh(x-.16,v.SD_scenario_means_pp,height=.30,color='#0072B2',label='SD of scenario means');a.barh(x+.16,v.mean_seed_SD_pp,height=.30,color='#999999',label='Mean seed SD')
 b.barh(x,v.between_component_pp2,height=.62,color='#0072B2',label='Corrected between');b.barh(x,v.within_variance_pp2,left=v.between_component_pp2,height=.62,color='#999999',label='Mean within')
 names=[LABEL[m] if m!='random_ls' else 'Random+LS' for m in STOCH]
 for ax in axs:ax.set_yticks(x,names);ax.set_ylim(4.6,-.6)
 a.set_xlabel('SD (percentage points)');b.set_xlabel('Variance (percentage points squared)');title(a,'a','Different sources of variability');title(b,'b','Descriptive variance components')
 a.legend(loc='upper center',bbox_to_anchor=(.5,-.20),frameon=False,handlelength=1.1);b.legend(loc='upper center',bbox_to_anchor=(.5,-.20),frameon=False,handlelength=1.1)
 export(fig,axs,'Fig_scenario_vs_seed',p)

def uncertainty(p):
 df=frame(p['delivery']/'Table_4_6_tail_uncertainty.csv');csv(p['figures']/'Fig_bootstrap_intervals_source.csv',df)
 fig,axs=plt.subplots(1,2,figsize=(183/25.4,82/25.4));fig.subplots_adjust(left=.16,right=.97,bottom=.24,top=.83,wspace=.50)
 for ax,metric,letter,heading in zip(axs,['delta_mean_pp','delta_P90_pp'],['a','b'],['Difference in mean regret','Difference of P90s']):
  ax.axvline(0,color='#AAAAAA',ls='--',lw=.7,zorder=0)
  for i,m in enumerate(COMPARATORS):
   for scheme,offset,color,marker in [('scenario-only',-.13,'#0072B2','o'),('scenario+seed',.13,'#D55E00','s')]:
    r=df[(df.comparator==m)&(df.scheme==scheme)&(df.metric==metric)].iloc[0];y=i+offset;ax.hlines(y,r.percentile95_low,r.percentile95_high,color=color,lw=1.1);ax.vlines([r.percentile95_low,r.percentile95_high],y-.035,y+.035,color=color,lw=.8);ax.scatter([r.estimate_full30],[y],s=19,color=color,marker=marker,zorder=3)
  ax.set_yticks(range(4),[LABEL[m] for m in COMPARATORS]);ax.set_ylim(3.6,-.6);ax.set_xlabel('Proposed minus comparator (percentage points)');title(ax,letter,heading)
 fig.legend(handles=[Line2D([0],[0],color='#0072B2',marker='o',label='Scenario-only'),Line2D([0],[0],color='#D55E00',marker='s',label='Scenario+seed')],loc='lower center',bbox_to_anchor=(.5,.025),ncol=2,frameon=False)
 export(fig,axs,'Fig_bootstrap_intervals',p)

def render(out):
 p=locations(out);assert js(p['audit']/'G2_validation_report.json')['status']=='PASS_S2_S3'
 tails(out,p);variance(p);uncertainty(p);results=[]
 for name in ['Fig_new30_tails','Fig_scenario_vs_seed','Fig_bootstrap_intervals']:
  for kind,args in [('text',[str(QA/'audit_pdf_text.py'),str(p['figures']/(name+'.pdf')),'--min-pt','5','--json']),('collision',[str(QA/'audit_figure_collisions.py'),str(p['figures']/(name+'.pdf')),'--json-out',str(p['figures']/(name+'_collisions.json')),'--overlay-pdf',str(p['figures']/(name+'_collisions_overlay.pdf')),'--json'])]:
   r=subprocess.run([sys.executable,*args],capture_output=True,text=True,encoding='utf-8');(p['figures']/(name+'_'+kind+'_log.json')).write_text(r.stdout or r.stderr,encoding='utf-8');results.append({'figure':name,'audit':kind,'returncode':r.returncode});assert r.returncode==0,(name,kind,r.stdout)
 r=subprocess.run([sys.executable,str(QA/'validate_figure.py'),str(Path(__file__)),'--json'],capture_output=True,text=True,encoding='utf-8');(p['figures']/'source_preflight.json').write_text(r.stdout or r.stderr,encoding='utf-8');assert r.returncode==0,r.stdout
 dump(p['figures']/'automatic_QA.json',{'status':'PASS','checks':results,'source_preflight':'no FAIL; warnings reviewed with final visual check','visual_review':'pending'})
 print('Three S2/S3 figures rendered, automatic QA PASS',flush=True)
