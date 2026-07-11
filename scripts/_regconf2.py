import numpy as np, pandas as pd, os, time
CACHE='/home/woody/stock-research/cache_full/prices'; IDXC='/home/woody/stock-research/cache_pe'
ROOT='/home/woody/twstock-signal'; EXT=0.10; VOL_MIN=1000; STEP=20; COST=0.6; ATR_N=14; ATR_K=3.5; MAXH=60; LO=6; HI=10; SPLIT='2021-01-01'
T0=time.time(); log=lambda *a:print(*a,'| %.0fs'%(time.time()-T0),flush=True)
reg=pd.read_csv('/home/woody/stock-research/regime_ma60.csv'); rd=reg['date'].values.astype(str)
def build_flags(col):
    a=reg[col].values.astype(float); above=(a>0.5); n=len(above); cb=np.zeros(n,int)
    for i in range(n): cb[i]=0 if above[i] else (cb[i-1]+1 if i>0 else 1)
    return dict(zip(rd,above)), dict(zip(rd,cb))
ab={'TWSE':build_flags('TAIEX_above60'),'OTC':build_flags('TPEx_above60')}; reg_twse_above=ab['TWSE'][0]
idxs={'TWSE':pd.read_csv(f'{IDXC}/idx_TAIEX.csv'),'OTC':pd.read_csv(f'{IDXC}/idx_TPEx.csv')}
tdates=idxs['TWSE']['date'].values.astype(str)
lst=pd.read_csv(f'{ROOT}/../twstock-alphabeta/data/stock_list.csv',dtype={'code':str})
S={}
for r in lst.itertuples():
    fp=f'{CACHE}/{r.code}.csv'
    if not os.path.exists(fp): continue
    g=pd.read_csv(fp)
    if len(g)<300: continue
    g=g.merge(idxs[r.market],on='date',how='left'); g['idx']=g['idx'].ffill()
    if g['idx'].isna().all(): continue
    C=g['Close'].values.astype(float); c=pd.Series(C); ix=pd.Series(g['idx'].values.astype(float)); s=c.pct_change(); mm=ix.pct_change()
    m5=c.rolling(5).mean().values; m10=c.rolling(10).mean().values; m20=c.rolling(20).mean().values; m60=c.rolling(60).mean().values
    m20r=np.r_[False,m20[1:]>m20[:-1]]; aS=(m5>m10)&(m10>m20)&(m20>m60)&(C>m5)&m20r
    b120=(s.rolling(120).cov(mm)/mm.rolling(120).var()); a120=((s.rolling(120).mean()-b120*mm.rolling(120).mean())*252).values
    ext=(C/m20-1)*100; V=g['Volume'].values.astype(float); avg20=pd.Series(V).rolling(20).mean().values/1000
    H=g['High'].values.astype(float); Lo=g['Low'].values.astype(float); pc=np.r_[C[0],C[:-1]]
    tr=np.maximum.reduce([H-Lo,np.abs(H-pc),np.abs(Lo-pc)]); atr=pd.Series(tr).rolling(ATR_N).mean().values
    S[r.code]=dict(mk=r.market,C=C,H=H,L=Lo,atr=atr,dt=g['date'].values.astype(str),aS=aS,a120=a120,b120=b120.values,ext=ext,avg20=avg20,n=len(C))
log('S建完',len(S))
def atr_ret(d,t):
    j=t+1; C,H,L,atr,n=d['C'],d['H'],d['L'],d['atr'],d['n']
    if j>=n: return None
    e=(H[j]+L[j])/2
    if e<=0: return None
    peak=H[j]
    for k in range(0,MAXH+1):
        i=j+k
        if i>=n: return C[n-1]/e-1
        if k>0 and np.isfinite(atr[i]) and C[i]<=peak-ATR_K*atr[i]: return C[i]/e-1
        peak=max(peak,H[i])
    return C[min(j+MAXH,n-1)]/e-1
picks=[]; di=240
while di<len(tdates)-MAXH-2:
    dd=tdates[di]; P=[]
    for code,d in S.items():
        t=np.searchsorted(d['dt'],dd)
        if t>=d['n'] or d['dt'][t]!=dd or t<300 or t+MAXH+1>=d['n']: continue
        if not d['aS'][t] or not np.isfinite(d['a120'][t]) or not np.isfinite(d['b120'][t]) or not np.isfinite(d['ext'][t]) or not np.isfinite(d['avg20'][t]): continue
        if not (d['avg20'][t]>VOL_MIN and 0<=d['b120'][t]<1 and d['ext'][t]<10): continue
        r=atr_ret(d,t)
        if r is None: continue
        P.append((float(d['a120'][t]),d['mk'],r*100-COST))
    if len(P)>=HI:
        band=sorted(P,key=lambda x:-x[0])[LO-1:HI]
        picks.append((dd,bool(reg_twse_above.get(dd,True)),[(mk,rr) for a,mk,rr in band]))
    di+=STEP
log('週數',len(picks))
def deploy(rule,mk,dd):
    if rule=='single': return ab[mk][0].get(dd,True)
    return ab[mk][1].get(dd,0) < int(rule[7:])
def run(rule):
    out=[]
    for dd,up,pk in picks:
        rr=[(rr if deploy(rule,mk,dd) else 0.0) for mk,rr in pk]
        out.append((dd,float(np.mean(rr)),up))
    return out
def agg(o,mask):
    x=np.array([r[1] for r in o])[mask]
    return x.mean() if len(x) else float('nan')
print('市況濾網 早/近兩段確認 (早<2021, 近>=2021)',flush=True)
print('%-10s | 早期全 早期空 | 近期全 近期空 | 全樣本'%'規則',flush=True)
for rule,nm in [('single','單日'),('confirm3','連續3天'),('confirm5','連續5天')]:
    o=run(rule); dts=np.array([r[0] for r in o]); up=np.array([r[2] for r in o]); early=dts<SPLIT
    print('%-10s | %+.2f  %+.2f | %+.2f  %+.2f | %+.2f'%(nm,agg(o,early),agg(o,early&~up),agg(o,~early),agg(o,~early&~up),agg(o,np.ones(len(o),bool))),flush=True)
print('\n早期空頭週數 %d, 近期空頭週數 %d'%(int(np.sum((np.array([r[0] for r in run("single")])<SPLIT)&~np.array([r[2] for r in run("single")]))),int(np.sum((np.array([r[0] for r in run("single")])>=SPLIT)&~np.array([r[2] for r in run("single")])))),flush=True)
log('DONE')
