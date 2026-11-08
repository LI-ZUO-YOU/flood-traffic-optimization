from load_frozen_results import *
import sys,subprocess
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
QA=Path(r'C:/Users/Wuzeqian.PC-20220914MSMS/.codex/skills/nature-figure/scripts')
sys.path.insert(0,str(QA))
from audit_panel_alignment import require_matplotlib_panel_alignment

def render(out):
 out=Path(out);require_gate(out,'G1');folder=out/'05_figures';name='Fig_legacy_P90_sensitivity';data=frame(out/'01_legacy10/legacy10_P90_order_statistics.csv')
 dump(folder/'figure_contract.json',{'claim':'A ten-scenario linearP90 is determined only by ranks9 and10, and small precision changes do not add independent observations','archetype':'quantitative grid','panel_a':'all10 sorted scenario observations for each method at both existing precisions; nearly overlapping old/new values retained','panel_b':'rank9 and10 weighted contributions, for both methods and both precisions','data':'legacy10_P90_order_statistics.csv,40 rows; no discarded methods/seeds or selected favorable scenarios','unit':'historical scenario, n10; one existing method path per scenario; no seed CI','backend':'Python matplotlib, established workflow','width_mm':183,'export':'editablePDF/SVG,600dpiPNG','QA':'source, rendered alignment1.5pt, font floor5pt, collision and visual review'})
 csv(folder/'legacy_P90_figure_source.csv',data)
 plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':7,'axes.labelsize':7,'axes.titlesize':8,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7,'svg.fonttype':'none','pdf.fonttype':42,'axes.linewidth':.6,'axes.spines.top':False,'axes.spines.right':False})
 fig,axs=plt.subplots(1,2,figsize=(183/25.4,88/25.4));fig.subplots_adjust(left=.09,right=.97,bottom=.25,top=.84,wspace=.60);a,b=axs
 colors={'Proposed_B256':'#0072B2','SA_original_fixed_seed':'#D55E00'};labels={'Proposed_B256':'Proposed','SA_original_fixed_seed':'SA'}
 for method in LEGACY_METHODS:
  for tier in PRECISIONS:
   g=data[(data.method==method)&(data.precision_tier==tier)].sort_values('rank_ascending');old=tier=='old_FW_5e-4'
   a.plot(g.rank_ascending,g.regret_pct,color=colors[method],ls='--' if old else '-',lw=.9,marker='o',markersize=4.5 if old else 2.5,markerfacecolor='white' if old else colors[method],markeredgewidth=.8,label=labels[method]+(' old FW' if old else ' high precision'))
 a.set(xlim=(.5,10.5),ylim=(-.10,3.8),xlabel='Ascending scenario rank (n = 10)',ylabel='Regret (%)');a.set_xticks([1,3,5,7,9,10]);a.set_title('Sorted historical observations',loc='left',pad=15);a.text(-.15,1.10,'a',transform=a.transAxes,fontweight='bold',fontsize=9)
 barrows=[]
 for method in LEGACY_METHODS:
  for tier in PRECISIONS:
   g=data[(data.method==method)&(data.precision_tier==tier)].sort_values('rank_ascending');r9=g[g.rank_ascending==9].iloc[0];r10=g[g.rank_ascending==10].iloc[0];barrows.append((method,tier,r9,r10))
 for i,(method,tier,r9,r10) in enumerate(barrows):
  low=r9.P90_component_pp;high=r10.P90_component_pp;b.barh(i,low,height=.55,color=colors[method],alpha=.40);b.barh(i,high,left=low,height=.55,color=colors[method],edgecolor='white',linewidth=.3)
  b.text(low+high+.018,i,f'{low+high:.6f}',va='center',ha='left',fontsize=7)
 b.set_yticks(range(4),[labels[m]+(' old FW' if t=='old_FW_5e-4' else ' high precision') for m,t,_,_ in barrows]);b.set(ylim=(3.6,-.6),xlim=(0,1.01),xlabel='P90 contribution (percentage points)');b.set_title('P90 uses only the largest two',loc='left',pad=15);b.text(-.15,1.10,'b',transform=b.transAxes,fontweight='bold',fontsize=9)
 a.tick_params(length=3,pad=3);b.tick_params(length=3,pad=3)
 fig.legend(*a.get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.5,.075),ncol=4,frameon=False,handlelength=2,columnspacing=1.1)
 fig.legend(handles=[Patch(facecolor='#999999',alpha=.4,label='0.9 × rank 9'),Patch(facecolor='#777777',edgecolor='white',label='0.1 × rank 10')],loc='lower center',bbox_to_anchor=(.5,.007),ncol=2,frameon=False)
 fig.canvas.draw();require_matplotlib_panel_alignment(fig,axes=list(axs),panel_ids=['a','b'],json_out=folder/(name+'_alignment.json'),overlay_svg=folder/(name+'_alignment_overlay.svg'),strict=True)
 fig.savefig(folder/(name+'.pdf'));fig.savefig(folder/(name+'.svg'));fig.savefig(folder/(name+'.png'),dpi=600,facecolor='white');plt.close(fig)
 results=[]
 calls=[('source',[str(QA/'validate_figure.py'),str(Path(__file__)),'--json']),('PDF_text',[str(QA/'audit_pdf_text.py'),str(folder/(name+'.pdf')),'--min-pt','5','--json']),('collision',[str(QA/'audit_figure_collisions.py'),str(folder/(name+'.pdf')),'--json-out',str(folder/(name+'_collisions.json')),'--overlay-pdf',str(folder/(name+'_collisions_overlay.pdf')),'--json'])]
 for kind,args in calls:
  r=subprocess.run([sys.executable,*args],capture_output=True,text=True,encoding='utf-8');(folder/(name+'_'+kind+'_log.json')).write_text(r.stdout or r.stderr,encoding='utf-8');results.append({'check':kind,'returncode':r.returncode});assert r.returncode==0,(kind,r.stdout,r.stderr)
 dump(folder/'figure_QA_automatic.json',{'status':'PASS','checks':results,'visual_review':'pending direct image inspection'})
 print('Historical P90 figure rendered and automatic QA PASS',flush=True)
