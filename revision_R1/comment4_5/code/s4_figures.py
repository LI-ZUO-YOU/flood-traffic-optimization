from s4_common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import subprocess
QA=Path(r'C:/Users/Wuzeqian.PC-20220914MSMS/.codex/skills/nature-figure/scripts')
sys.path.insert(0,str(QA))
from audit_panel_alignment import require_matplotlib_panel_alignment

plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':7,'axes.labelsize':7,'axes.titlesize':8,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7,'svg.fonttype':'none','pdf.fonttype':42,'axes.linewidth':.6,'xtick.major.width':.6,'ytick.major.width':.6,'lines.linewidth':1.1,'savefig.dpi':300})
FIG=S4/'05_figures';BLUE='#0072B2';ORANGE='#D55E00';GREEN='#009E73';PURPLE='#CC79A7';GRAY='#777777';COLORS=[BLUE,ORANGE,GREEN]
LABEL={v:v.split('_')[0] for v in METHODS};LABEL['Greedy-ILS']='Greedy-ILS'

def clean(ax):
 ax.spines[['top','right']].set_visible(False);ax.tick_params(length=3,pad=3)

def title(ax,letter,text):
 ax.set_title(text,loc='left',pad=14);ax.text(-.16,1.10,letter,transform=ax.transAxes,fontweight='bold',fontsize=9,ha='left',va='bottom')

def save(fig,name,axes,letters):
 fig.canvas.draw()
 require_matplotlib_panel_alignment(fig,axes=axes,panel_ids=letters,json_out=FIG/(name+'_alignment.json'),overlay_svg=FIG/(name+'_alignment_overlay.svg'))
 for ext in ['pdf','svg']:fig.savefig(FIG/(name+'.'+ext),facecolor='white')
 fig.savefig(FIG/(name+'.png'),dpi=600,facecolor='white')
 plt.close(fig)

def mechanism():
 stage=frame(S4/'02_case5102/5102_stage_firstroad_counts.csv');trace=frame(S4/'02_case5102/5102_incumbent_trace.csv');runs=frame(S4/'02_case5102/5102_run_path_summary.csv')
 fig,axs=plt.subplots(2,2,figsize=(183/25.4,145/25.4));fig.subplots_adjust(left=.11,right=.97,bottom=.14,top=.91,wspace=.48,hspace=.65);a,b,c,d=axs.flat
 names=['pool','Primary60','Reserve','C_completed','D_completed','final'];z=np.array([[stage[(stage.variant_id=='F0_FULL')&(stage.seed_index==rep)&(stage.first_road==18)&(stage.stage==n)].iloc[0]['count'] for n in names] for rep in range(3)])
 assert (z>=0).all() and np.all(1+z>0) # Strictly positive arguments1+count, including zero counts.
 a.imshow(np.log1p(z),aspect='auto',cmap='Blues',vmin=0,vmax=np.log1p(3000))
 for i in range(3):
  for j in range(6):a.text(j,i,str(int(z[i,j])),ha='center',va='center',color='white' if z[i,j]>400 else 'black',fontsize=7)
 a.set_xticks(range(6),['Pool','Primary','Reserve','C','LS','Final'],rotation=35,ha='right',rotation_mode='anchor');a.set_yticks(range(3),['Seed 0','Seed 1','Seed 2']);a.tick_params(length=0);title(a,'a','F0 sequences starting with road 18')
 for rep,col in enumerate(COLORS):
  t=trace[(trace.variant_id=='F0_FULL')&(trace.seed_index==rep)].sort_values('ordinal');b.step(np.r_[t.completion_budget,256],np.r_[t.regret_pct,t.regret_pct.iloc[-1]],where='post',color=col,label=f'F0 seed{rep}')
 for v,col,style in [('F1_NO_RESERVE',PURPLE,'--'),('Greedy-ILS',GRAY,':')]:
  t=trace[(trace.variant_id==v)&(trace.seed_index==0)].sort_values('ordinal');b.step(np.r_[t.completion_budget,256],np.r_[t.regret_pct,t.regret_pct.iloc[-1]],where='post',color=col,ls=style,label=LABEL[v]+' seed0')
 b.set(xlim=(38,260),ylim=(-3,95),xlabel='Unique UE states used',ylabel='Incumbent regret (%)');title(b,'b','Observed trajectories in 5102');clean(b)
 variants=['F0_FULL','F1_NO_RESERVE','F3_NO_DISAG','F6_SINGLE_MLP','F7_RIDGE','F9_NO_SURROGATE','Greedy-ILS']
 for i,v in enumerate(variants):
  rr=runs[runs.variant_id==v];before=rr.first_LS_before_regret_pct.mean();after=rr.first_LS_after_regret_pct.mean();final=rr.final_regret_pct.mean();c.plot([final,before],[i,i],color='#BBBBBB',zorder=1)
  c.errorbar(final,i,xerr=[[max(0,final-rr.final_regret_pct.min())],[max(0,rr.final_regret_pct.max()-final)]],fmt='none',ecolor=ORANGE,capsize=2,lw=.8,zorder=2)
  c.scatter([before],[i],marker='o',s=23,facecolor='white',edgecolor=BLUE,zorder=3);c.scatter([after],[i],marker='^',s=23,color=PURPLE,zorder=3);c.scatter([final],[i],marker='D',s=21,color=ORANGE,zorder=4)
 c.set_yticks(range(7),[LABEL[v] for v in variants]);c.set(xlim=(-3,95),ylim=(6.6,-.6),xlabel='Regret (%), mean of three seeds');title(c,'c','Quality before first LS to final');clean(c)
 for rep,col in enumerate(COLORS):
  t=trace[(trace.variant_id=='F0_FULL')&(trace.seed_index==rep)].sort_values('ordinal');d.step(np.r_[t.completion_budget,256],np.r_[t.position18,t.position18.iloc[-1]],where='post',color=col,label=f'Seed{rep}')
 d.set(xlim=(38,260),ylim=(10.5,.5),xlabel='Unique UE states used',ylabel='Incumbent position of road 18');d.set_yticks([1,3,5,7,9]);title(d,'d','Road 18 in the F0 incumbent');clean(d)
 fig.legend(handles=[Line2D([0],[0],color=col,label=f'F0 seed{rep}') for rep,col in enumerate(COLORS)]+[Line2D([0],[0],color=PURPLE,ls='--',label='F1 seed0'),Line2D([0],[0],color=GRAY,ls=':',label='Greedy-ILS seed0')],loc='lower center',bbox_to_anchor=(.5,.046),ncol=5,frameon=False,handlelength=1.7,columnspacing=1)
 fig.legend(handles=[Line2D([0],[0],marker='o',color='none',markeredgecolor=BLUE,markerfacecolor='white',label='Before first LS'),Line2D([0],[0],marker='^',color='none',markerfacecolor=PURPLE,label='After first LS'),Line2D([0],[0],marker='D',color='none',markerfacecolor=ORANGE,label='Final (seed range)')],loc='lower center',bbox_to_anchor=(.5,.005),ncol=3,frameon=False)
 save(fig,'Fig1_5102_mechanism',list(axs.flat),list('abcd'))

def robustness():
 sc=frame(S4/'01_statistics/scenario_seed_statistics.csv');lo=frame(S4/'01_statistics/LOSO_all10_omissions.csv');su=frame(S4/'01_statistics/full10_descriptive_summary.csv').set_index('variant_id');vs=METHODS[1:]
 fig,axs=plt.subplots(1,2,figsize=(183/25.4,100/25.4));fig.subplots_adjust(left=.13,right=.97,bottom=.22,top=.86,wspace=.46)
 for ax in axs:ax.axvline(0,color='#CCCCCC',lw=.7,zorder=0);clean(ax);ax.set_yticks(range(10),[LABEL[v] for v in vs]);ax.set_ylim(9.6,-.6)
 for i,v in enumerate(vs):
  a=sc[sc.variant_id==v];x=a.mean_delta_vs_F0_pp.to_numpy();j=np.linspace(-.14,.14,10);axs[0].scatter(x,i+j,s=14,color='#999999',alpha=.7,zorder=2);t=a[a.scenario_id==5102];axs[0].scatter(t.mean_delta_vs_F0_pp,[i+j[list(a.scenario_id).index(5102)]],s=25,color=ORANGE,zorder=3)
  t=lo[lo.variant_id==v];axs[1].scatter(t.LOSO9_mean_delta_pp,i+j,s=14,color='#999999',alpha=.7,zorder=2);t=t[t.omitted_scenario_for_sensitivity_only==5102];axs[1].scatter(t.LOSO9_mean_delta_pp,[i+j[1]],s=25,color=ORANGE,zorder=3)
  for ax in axs:ax.scatter([su.loc[v,'mean_delta_vs_F0_pp']],[i],s=28,marker='D',color='black',zorder=4)
 axs[0].set_xlabel('Variant minus F0 regret (percentage points)');axs[1].set_xlabel('Mean paired difference (percentage points)');title(axs[0],'a','All ten paired scenario differences');title(axs[1],'b','All ten leave-one-out sensitivities')
 fig.legend(handles=[Line2D([0],[0],marker='o',color='none',markerfacecolor='#999999',markeredgecolor='none',label='Scenario or omission'),Line2D([0],[0],marker='o',color='none',markerfacecolor=ORANGE,markeredgecolor='none',label='5102 or omission of5102'),Line2D([0],[0],marker='D',color='none',markerfacecolor='black',label='Full10 mean')],loc='lower center',bbox_to_anchor=(.5,.02),ncol=3,frameon=False,handletextpad=.4,columnspacing=1)
 save(fig,'Fig2_full10_LOSO',list(axs),list('ab'))

def prediction():
 er=frame(S4/'04_prediction_diagnostics/common_state_errors_by_scenario.csv');pool=frame(S4/'04_prediction_diagnostics/common_pool_metrics_scenario_means.csv')
 fig,axs=plt.subplots(1,2,figsize=(183/25.4,83/25.4));fig.subplots_adjust(left=.14,right=.97,bottom=.28,top=.82,wspace=.48)
 for i,name in enumerate(MODELS):
  for ax,g,col in [(axs[0],er[(er.model==name)&(er.scale=='log_ratio')],'R2'),(axs[1],pool[pool.model==name],'Spearman_candidate_J')]:
   g=g.sort_values('scenario_id');j=np.linspace(-.14,.14,10);ax.scatter(g[col],i+j,s=15,color=BLUE,alpha=.65);case=g[g.scenario_id==5102];ax.scatter(case[col],[i+j[1]],s=28,color=ORANGE,zorder=4);ax.scatter([g[col].mean()],[i],s=25,marker='D',color='black',zorder=5)
 for ax in axs:ax.set_yticks(range(4),MODELS);ax.set_ylim(3.6,-.6);clean(ax)
 axs[0].set_xlabel('R² on log(TSTT / TSTT0)');axs[1].set_xlabel('Spearman correlation of candidate J');title(axs[0],'a','Common 1024-state prediction');title(axs[1],'b','Common frozen F0 candidate pools')
 fig.legend(handles=[Line2D([0],[0],marker='o',color='none',markerfacecolor=BLUE,markeredgecolor='none',label='Scenario'),Line2D([0],[0],marker='o',color='none',markerfacecolor=ORANGE,markeredgecolor='none',label='5102'),Line2D([0],[0],marker='D',color='none',markerfacecolor='black',label='Mean of ten scenarios')],loc='lower center',bbox_to_anchor=(.5,.045),ncol=3,frameon=False)
 save(fig,'Fig3_frozen_predictors',list(axs),list('ab'))

def timing():
 tm=frame(S4/'03_phases_costs/Table_time_decomposition.csv').set_index('variant_id').reindex(METHODS);sc=frame(S4/'03_phases_costs/time_components_scenario_means.csv')
 fig,ax=plt.subplots(figsize=(183/25.4,104/25.4));fig.subplots_adjust(left=.15,right=.97,bottom=.24,top=.90);left=np.zeros(11)
 for col,name,color in [('candidate_prepare_seconds','Candidate preparation',BLUE),('UE_network_call_seconds','Live UE calls',ORANGE),('LS_non_UE_seconds','LS management',GREEN),('search_other_bookkeeping_seconds','Other search management',PURPLE)]:
  a=tm[col].to_numpy();ax.barh(range(11),a,left=left,height=.56,label=name,color=color);left+=a
 for i,v in enumerate(METHODS):
  t=sc[sc.variant_id==v];ax.scatter(t.fresh_online_seconds,i+np.linspace(-.18,.18,10),s=8,color='#333333',alpha=.55,zorder=4)
 ax.set_yticks(range(11),[LABEL[v] for v in METHODS]);ax.set_ylim(10.7,-.7);ax.set_xlim(0,float(sc.fresh_online_seconds.max())*1.05);ax.set_xlabel('Fresh online time (s), preparation plus live UE and search');ax.set_title('Measured online cost, all ten scenarios',loc='left',pad=12);clean(ax)
 ax.legend(loc='upper center',bbox_to_anchor=(.5,-.19),ncol=2,frameon=False,columnspacing=1.4,handlelength=1.5)
 save(fig,'Fig4_online_time',[ax],['a'])

def audit():
 reports=[]
 for name in ['Fig1_5102_mechanism','Fig2_full10_LOSO','Fig3_frozen_predictors','Fig4_online_time']:
  for kind,args in [('text',['audit_pdf_text.py',str(FIG/(name+'.pdf')),'--min-pt','5','--json']),('collisions',['audit_figure_collisions.py',str(FIG/(name+'.pdf')),'--json-out',str(FIG/(name+'_collisions.json')),'--overlay-pdf',str(FIG/(name+'_collisions_overlay.pdf')),'--json'])]:
   r=subprocess.run([sys.executable,str(QA/args[0]),*args[1:]],capture_output=True,text=True,encoding='utf-8');(FIG/(name+'_'+kind+'_log.json')).write_text(r.stdout or r.stderr,encoding='utf-8');reports.append({'figure':name,'audit':kind,'returncode':r.returncode})
 r=subprocess.run([sys.executable,str(QA/'validate_figure.py'),str(Path(__file__)),'--json'],capture_output=True,text=True,encoding='utf-8');(FIG/'source_preflight.json').write_text(r.stdout or r.stderr,encoding='utf-8');reports.append({'figure':'all','audit':'source','returncode':r.returncode});dump(FIG/'audit_exit_codes.json',reports);print(json.dumps(reports),flush=True)

if __name__=='__main__':
 pin();mechanism();robustness();prediction();timing();audit()
