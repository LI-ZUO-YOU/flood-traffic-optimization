"""Independent compiled BFW solver for the unchanged static separable BPR UE.

Numerical direction follows the conjugate-direction FW formulation of
Mitradjieva & Lindberg (2013). BFW equations were checked against the official
AequilibraE documentation. No AequilibraE implementation is redistributed.
Every state starts cold; convergence uses an independently recomputed AON gap.
"""
from pathlib import Path
import time
import numpy as np
import pandas as pd
from numba import njit

LEGACY_BASELINE = 7480225.3449211195

@njit(cache=True)
def aon(cost,tail,head,active,adj,degree,od):
    n=od.shape[0];m=len(cost);flow=np.zeros(m);sp=0.0
    for origin in range(n):
        dist=np.full(n,1e100);pred=np.full(n,-1);done=np.zeros(n,np.uint8);order=np.zeros(n,np.int64)
        dist[origin]=0.0
        for k in range(n):
            u=-1;best=1e100
            for v in range(n):
                if done[v]==0 and dist[v]<best:best=dist[v];u=v
            if u<0:return flow,np.inf
            done[u]=1;order[k]=u
            for j in range(degree[u]):
                e=adj[u,j]
                if active[e]:
                    v=head[e];d=dist[u]+cost[e]
                    if d<dist[v]-1e-12:dist[v]=d;pred[v]=e
        load=od[origin].copy()
        for v in range(n):sp+=load[v]*dist[v]
        for k in range(n-1,0,-1):
            v=order[k];e=pred[v]
            if e<0:return flow,np.inf
            flow[e]+=load[v];load[tail[e]]+=load[v]
    return flow,sp

@njit(cache=True)
def impedance(x,fft,coef,active):
    c=np.empty(len(x))
    for e in range(len(x)):
        c[e]=fft[e]+coef[e]*x[e]**4 if active[e] else 1e100
    return c

@njit(cache=True)
def solve_bfw(tail,head,active,adj,degree,od,fft,coef,target=1e-7,max_iter=100000,mode=2):
    m=len(tail);x,sp=aon(impedance(np.zeros(m),fft,coef,active),tail,head,active,adj,degree,od)
    sd=x.copy();psd=x.copy();previous_step=1.0;next_kind=0
    for iteration in range(1,max_iter+1):
        cost=impedance(x,fft,coef,active);y,sp=aon(cost,tail,head,active,adj,degree,od)
        tstt=0.0
        for e in range(m):
            if active[e]:tstt+=x[e]*cost[e]
        gap=max(0.0,(tstt-sp)/max(tstt,1e-100))
        if not np.isfinite(tstt) or not np.isfinite(sp):return x,np.nan,np.inf,iteration,False
        if gap<=target:return x,tstt,gap,iteration,True
        if iteration%128==0:next_kind=0
        oldsd=sd.copy();b0=1.0;b1=0.0;b2=0.0
        if mode>0 and next_kind>0 and previous_step<0.999999 and previous_step>1e-14:
            hess=4.0*coef*x**3
            if next_kind==1 or mode==1:
                num=0.0;den=0.0
                for e in range(m):
                    p=sd[e]-x[e];num+=p*(y[e]-x[e])*hess[e];den+=p*(y[e]-sd[e])*hess[e]
                a=max(0.0,min(0.999,num/den)) if abs(den)>1e-100 else 0.0
                b0=1.0-a;b1=a
            else:
                mn=0.0;md=0.0;nn=0.0;nd=0.0
                for e in range(m):
                    u=previous_step*sd[e]+(1-previous_step)*psd[e]-x[e]
                    v=y[e]-x[e];w=sd[e]-x[e]
                    mn+=u*v*hess[e];md+=u*(psd[e]-sd[e])*hess[e]
                    nn+=w*v*hess[e];nd+=w*w*hess[e]
                mu=max(0.0,-mn/md) if abs(md)>1e-100 else 0.0
                nu=max(0.0,-nn/nd+mu*previous_step/(1-previous_step)) if abs(nd)>1e-100 else 0.0
                if np.isfinite(mu+nu):b0=1/(1+mu+nu);b1=nu*b0;b2=mu*b0
        sd=b0*y+b1*oldsd+b2*psd;direction=sd-x
        g0=0.0
        for e in range(m):
            if active[e]:g0+=direction[e]*cost[e]
        reset=False
        if g0>=-1e-12:
            sd=y.copy();direction=sd-x;reset=True
        upper=0.0
        for e in range(m):
            if active[e]:upper+=direction[e]*(fft[e]+coef[e]*sd[e]**4)
        if upper<=0:step=1.0
        else:
            lo=0.0;hi=1.0
            for k in range(42):
                mid=(lo+hi)*0.5;g=0.0
                for e in range(m):
                    if active[e]:g+=direction[e]*(fft[e]+coef[e]*(x[e]+mid*direction[e])**4)
                if g>0:hi=mid
                else:lo=mid
            step=(lo+hi)*0.5
        x+=step*direction
        for e in range(m):
            if abs(x[e])<1e-10:x[e]=0.0
        psd=oldsd;previous_step=step
        next_kind=1 if reset or next_kind==0 or step>=0.999999 else 2
    cost=impedance(x,fft,coef,active);_,sp=aon(cost,tail,head,active,adj,degree,od)
    tstt=0.0
    for e in range(m):
        if active[e]:tstt+=x[e]*cost[e]
    gap=max(0.0,(tstt-sp)/tstt)
    return x,tstt,gap,max_iter,gap<=target

class Network:
    def __init__(self,root):
        p=Path(root)/'data_src/SiouxFalls_flood_benchmark/processed'
        self.links=pd.read_csv(p/'directed_links.csv');rawod=pd.read_csv(p/'od_long.csv')
        self.tail=self.links.from_node.to_numpy(np.int64)-1;self.head=self.links.to_node.to_numpy(np.int64)-1
        self.pid=self.links.physical_link_id.to_numpy(np.int64)-1
        self.cap=self.links.capacity.to_numpy(float);self.dryfft=self.links.free_flow_time.to_numpy(float)
        self.alpha=self.links.bpr_alpha.to_numpy(float)
        beta=self.links.bpr_beta.to_numpy(float)
        assert np.all(beta==4),'This compiled implementation supports the frozen beta=4 network only'
        self.od=np.zeros((24,24))
        for r in rawod.itertuples(index=False):self.od[int(r.origin)-1,int(r.destination)-1]+=float(r.demand)
        self.degree=np.bincount(self.tail,minlength=24).astype(np.int64);self.adj=np.full((24,int(max(self.degree))),-1,np.int64)
        for u in range(24):self.adj[u,:self.degree[u]]=np.flatnonzero(self.tail==u)
    def state_arrays(self,physical,roads,mask):
        physical=physical.sort_values('physical_link_id');closed=physical.is_closed.to_numpy(bool).copy()
        mult=physical.free_flow_time_multiplier.to_numpy(float).copy()
        for i,r in enumerate(roads):
            if mask&(1<<i):closed[r-1]=False;mult[r-1]=1.0
        active=~closed[self.pid];fft=self.dryfft*mult[self.pid];fft[~active]=1.0
        coef=fft*self.alpha/self.cap**4;coef[~active]=0.0
        return active,fft,coef
    def solve(self,physical,roads,mask,target=1e-9,mode=3):
        active,fft,coef=self.state_arrays(physical,roads,mask);start=time.perf_counter()
        if mode==3:
            from path_ue import solve_paths
            x,tstt,gap,it,ok=solve_paths(self.tail,self.head,active,self.adj,self.degree,self.od,fft,coef,target,20000)
        else:
            x,tstt,gap,it,ok=solve_bfw(self.tail,self.head,active,self.adj,self.degree,self.od,fft,coef,target,200000,mode)
        if not ok:raise RuntimeError(f'UE did not converge: mask={mask} target={target} gap={gap} it={it}')
        balance=np.bincount(self.tail,weights=x,minlength=24)-np.bincount(self.head,weights=x,minlength=24)
        expected=self.od.sum(axis=1)-self.od.sum(axis=0)
        if np.max(np.abs(balance-expected))>1e-5:raise RuntimeError('Flow conservation failed')
        return {'subset_mask':int(mask),'tstt':float(tstt),'loss':float(tstt/LEGACY_BASELINE-1),'relative_gap':float(gap),'iterations':int(it),'converged':True,'solver_seconds':time.perf_counter()-start,'flow_balance_max_abs':float(max(abs(balance-expected))),'solver':'path_column_generation_pairwise' if mode==3 else 'compiled_BFW','tolerance':target}
