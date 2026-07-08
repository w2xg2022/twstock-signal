# -*- coding: utf-8 -*-
"""一次性: 用VM快取價格回填 2026-05-02 起每週六的歷史推薦(我們+猴子)
我們: 多頭排列 → beta120∈[0,1] → alpha120 top5
猴子: 全市場隨機5檔(以當週日期為種子,可重現) — 致敬 Malkiel《漫步華爾街》"""
import numpy as np, pandas as pd, os, datetime as dt, random
CACHE="/home/woody/stock-research/cache_full/prices"; IDXC="/home/woody/stock-research/cache_pe"
ROOT="/home/woody/twstock-signal"; TOPN=5
idxs={"TWSE":pd.read_csv(f"{IDXC}/idx_TAIEX.csv"),"OTC":pd.read_csv(f"{IDXC}/idx_TPEx.csv")}
lst=pd.read_csv(f"{ROOT}/../twstock-alphabeta/data/stock_list.csv",dtype={"code":str})
info={r.code:(r.name,r.market) for r in lst.itertuples()}
S={}
for r in lst.itertuples():
    fp=f"{CACHE}/{r.code}.csv"
    if not os.path.exists(fp): continue
    g=pd.read_csv(fp)
    if len(g)<300: continue
    g=g.merge(idxs[r.market],on="date",how="left");g["idx"]=g["idx"].ffill()
    if g["idx"].isna().all(): continue
    C=g["Close"].values.astype(float);IX=g["idx"].values.astype(float);D=g["date"].values.astype(str)
    c=pd.Series(C);ix=pd.Series(IX);s=c.pct_change();m=ix.pct_change()
    m5=c.rolling(5).mean().values;m10=c.rolling(10).mean().values;m20=c.rolling(20).mean().values
    v1=(m5>m10)&(m10>m20)&(np.r_[False,m20[1:]>m20[:-1]])&(C>m5)
    b120=(s.rolling(120).cov(m)/m.rolling(120).var()).values
    a120=((s.rolling(120).mean()-pd.Series(b120)*m.rolling(120).mean())*252).values
    d240h=(C/c.rolling(240).max().values-1)
    S[r.code]=dict(name=info[r.code][0],mk=r.market,C=C,dt=D,v1=v1,a120=a120,b120=b120,d240h=d240h,n=len(C))
last=max(max(d["dt"]) for d in S.values())
print(f"載入{len(S)}檔, 資料至{last}")
os.makedirs(f"{ROOT}/data/picks",exist_ok=True); os.makedirs(f"{ROOT}/data/monkey",exist_ok=True)
d0=dt.date(2026,5,2); n=0
while d0.strftime("%Y-%m-%d")<=last:
    sat=d0.strftime("%Y-%m-%d"); d0+=dt.timedelta(days=7)
    rows=[]; universe=[]; ddate=""
    for code,d in S.items():
        t=np.searchsorted(d["dt"],sat+"~")-1
        if t<240 or t>=d["n"] or d["dt"][t]>sat: continue
        ddate=max(ddate,d["dt"][t]); universe.append(code)
        if not d["v1"][t] or not np.isfinite(d["a120"][t]) or not np.isfinite(d["b120"][t]): continue
        if not (0<=d["b120"][t]<1): continue
        rows.append(dict(code=code,name=d["name"],market=d["mk"],close=round(float(d["C"][t]),2),
            alpha120=round(float(d["a120"][t]),4),beta120=round(float(d["b120"][t]),3),d240h=round(float(d["d240h"][t]),4)))
    if not rows or len(universe)<20: continue
    D=pd.DataFrame(rows).sort_values("alpha120",ascending=False).reset_index(drop=True)
    D["rank"]=D.index+1; D.insert(0,"pick_date",ddate)
    D.to_csv(f"{ROOT}/data/picks/{ddate}.csv",index=False,encoding="utf-8-sig")
    # 猴子: 以日期為種子隨機5檔(全市場)
    rng=random.Random(int(ddate.replace("-",""))); mk_codes=rng.sample(universe,TOPN)
    M=pd.DataFrame([dict(pick_date=ddate,code=c,name=S[c]["name"],market=S[c]["mk"],close=round(float(S[c]["C"][np.searchsorted(S[c]["dt"],ddate)]),2)) for c in mk_codes])
    M.to_csv(f"{ROOT}/data/monkey/{ddate}.csv",index=False,encoding="utf-8-sig"); n+=1
print(f"回填 {n} 週 (我們+猴子)")
