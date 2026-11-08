"""Route column generation with exact pairwise flow equilibration.

This is an independent numerical solver for the same convex Beckmann problem.
Shortest paths introduce columns; feasible OD flow transfers minimize the
Beckmann integral on one pair of routes. A full all-OD relative gap certifies
the stopping criterion. No assumption of monotonic TSTT under road reopening.
"""
import numpy as np
from numba import njit
from ue_solver import aon,impedance

@njit(cache=True)
def all_preds(cost,head,active,adj,degree,n):
    predecessors=np.full((n,n),-1,np.int64)
    for origin in range(n):
        dist=np.full(n,1e100);dist[origin]=0.0;done=np.zeros(n,np.uint8)
        for k in range(n):
            u=-1;best=1e100
            for v in range(n):
                if done[v]==0 and dist[v]<best:u=v;best=dist[v]
            if u<0:return predecessors,False
            done[u]=1
            for j in range(degree[u]):
                e=adj[u,j]
                if active[e]:
                    v=head[e];value=dist[u]+cost[e]
                    if value<dist[v]-1e-12:dist[v]=value;predecessors[origin,v]=e
    return predecessors,True

@njit(cache=True)
def transfer_derivative(x,fft,coef,edges,signs,count,amount):
    g=0.0;h=0.0
    for k in range(count):
        e=edges[k];s=signs[k];v=x[e]+s*amount
        g+=s*(fft[e]+coef[e]*v**4);h+=4*coef[e]*v**3
    return g,h

@njit(cache=True)
def solve_paths(tail,head,active,adj,degree,od,fft,coef,target=1e-8,max_outer=20000):
    n=od.shape[0];m=len(tail);npairs=np.count_nonzero(od);maxpaths=128
    origins=np.empty(npairs,np.int64);destinations=np.empty(npairs,np.int64);demands=np.empty(npairs)
    q=0
    for o in range(n):
        for d in range(n):
            if o!=d and od[o,d]>0:origins[q]=o;destinations[q]=d;demands[q]=od[o,d];q+=1
    order=np.argsort(-demands)
    routes=np.full((npairs,maxpaths,n),-1,np.int64);length=np.zeros((npairs,maxpaths),np.int64)
    pathflow=np.zeros((npairs,maxpaths));counts=np.zeros(npairs,np.int64)
    x=np.zeros(m);cost=impedance(x,fft,coef,active);shifts=0
    for outer in range(max_outer):
        preds,ok=all_preds(cost,head,active,adj,degree,n)
        if not ok:return x,np.nan,np.inf,outer,False
        for q in range(npairs):
            o=origins[q];v=destinations[q];path=np.empty(n,np.int64);ln=0
            while v!=o:
                e=preds[o,v]
                if e<0 or ln>=n:return x,np.nan,np.inf,outer,False
                path[ln]=e;ln+=1;v=tail[e]
            found=False
            for p in range(counts[q]):
                if length[q,p]!=ln:continue
                same=True
                for k in range(ln):
                    if routes[q,p,k]!=path[k]:same=False;break
                if same:found=True;break
            if not found:
                p=counts[q]
                if p>=maxpaths:return x,np.nan,np.inf,outer,False
                counts[q]+=1;length[q,p]=ln
                for k in range(ln):routes[q,p,k]=path[k]
                if outer==0:
                    pathflow[q,p]=demands[q]
                    for k in range(ln):x[path[k]]+=demands[q]
        cost=impedance(x,fft,coef,active)
        for inner in range(5):
            for ix in range(npairs):
                q=order[ix];bestp=-1;bestcost=1e100
                for p in range(counts[q]):
                    value=0.0
                    for k in range(length[q,p]):value+=cost[routes[q,p,k]]
                    if value<bestcost:bestcost=value;bestp=p
                for p in range(counts[q]):
                    amount=pathflow[q,p]
                    if p==bestp or amount<=1e-9:continue
                    value=0.0
                    for k in range(length[q,p]):value+=cost[routes[q,p,k]]
                    if value-bestcost<=max(1e-9,abs(bestcost)*target*.01):continue
                    direction=np.zeros(m,np.int64)
                    for k in range(length[q,bestp]):direction[routes[q,bestp,k]]+=1
                    for k in range(length[q,p]):direction[routes[q,p,k]]-=1
                    edges=np.empty(m,np.int64);signs=np.empty(m,np.int64);cnt=0
                    for e in range(m):
                        if direction[e]!=0:edges[cnt]=e;signs[cnt]=direction[e];cnt+=1
                    g0,h0=transfer_derivative(x,fft,coef,edges,signs,cnt,0.0)
                    if g0>=0:continue
                    g1,_=transfer_derivative(x,fft,coef,edges,signs,cnt,amount)
                    if g1<=0:step=amount
                    else:
                        lo=0.0;hi=amount;step=min(amount,max(0.0,-g0/max(h0,1e-100)))
                        for it in range(22):
                            g,h=transfer_derivative(x,fft,coef,edges,signs,cnt,step)
                            if abs(g)<1e-11*max(1.0,abs(g0)):break
                            if g>0:hi=step
                            else:lo=step
                            new=step-g/max(h,1e-100)
                            step=new if lo<new<hi else .5*(lo+hi)
                    pathflow[q,p]-=step;pathflow[q,bestp]+=step;shifts+=1
                    for k in range(cnt):
                        e=edges[k];x[e]+=signs[k]*step;cost[e]=fft[e]+coef[e]*x[e]**4
                    bestcost=0.0
                    for k in range(length[q,bestp]):bestcost+=cost[routes[q,bestp,k]]
        _,sp=aon(cost,tail,head,active,adj,degree,od);tstt=0.0
        for e in range(m):
            if active[e]:tstt+=x[e]*cost[e]
        gap=max(0.0,(tstt-sp)/tstt)
        if gap<=target:return x,tstt,gap,outer+1,True
    return x,tstt,gap,max_outer,False
