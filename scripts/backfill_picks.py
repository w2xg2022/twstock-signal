# -*- coding: utf-8 -*-
"""一次性: 回填 2026-03-07 起每週六歷史推薦(我們+猴子)
我們: 多頭排列 → beta120∈[0,1] → 收盤離MA20<10% → alpha120 排序 → 前5
去重: 20交易日內(=持有期)已推薦過的股票不再選,由下一名遞補；猴子同理(重抽)
猴子: 全市場隨機5檔(以當週日期為種子) — 致敬 Malkiel《漫步華爾街》"""
import numpy as np, pandas as pd, os, datetime as dt, random
CACHE="/home/woody/stock-research/cache_full/prices"; IDXC="/home/woody/stock-research/cache_pe"
ROOT="/home/woody/twstock-signal"; TOPN=5; EXT=0.10; HOLD=20; VOL_MIN=1000; SKIP=7  # VOL_MIN:近20日日均量下限(張); SKIP:跳過前幾名(取8-12,平台中央)
D_RANK_START=SKIP+1
idxs={"TWSE":pd.read_csv(f"{IDXC}/idx_TAIEX.csv"),"OTC":pd.read_csv(f"{IDXC}/idx_TPEx.csv")}
tdates=idxs["TWSE"]["date"].values.astype(str)  # 交易日曆
MA_REG=60  # regime季線
regidx={mk:(g["date"].values.astype(str),g["idx"].values.astype(float),pd.Series(g["idx"].values.astype(float)).rolling(MA_REG).mean().values) for mk,g in idxs.items()}
def regime_ok(mk,ddate):
    dd,v,ma=regidx[mk]; ii=np.searchsorted(dd,ddate,"right")-1
    return bool(ii>=MA_REG and np.isfinite(ma[ii]) and v[ii]>=ma[ii])
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
    ext=C/m20-1; d240h=(C/c.rolling(240).max().values-1)
    V=g["Volume"].values.astype(float); vol20=pd.Series(V).rolling(20).mean().values  # 近20日日均量(股)
    S[r.code]=dict(name=info[r.code][0],mk=r.market,C=C,dt=D,v1=v1,a120=a120,b120=b120,ext=ext,d240h=d240h,vol20=vol20,n=len(C))
last=max(max(d["dt"]) for d in S.values())
print(f"載入{len(S)}檔, 資料至{last}")
os.makedirs(f"{ROOT}/data/picks",exist_ok=True); os.makedirs(f"{ROOT}/data/monkey",exist_ok=True)
# 依時間順序(舊→新)處理，維護持有中集合
sats=[]; d0=dt.date(2026,3,7)
while d0.strftime("%Y-%m-%d")<=last: sats.append(d0.strftime("%Y-%m-%d")); d0+=dt.timedelta(days=7)
held_our={}; held_mk={}; n=0  # code -> 決策日交易索引
for sat in sats:
    cand=[]; universe=[]; ddate=""; tcur=None
    for code,d in S.items():
        t=np.searchsorted(d["dt"],sat+"~")-1
        if t<240 or t>=d["n"] or d["dt"][t]>sat: continue
        ddate=max(ddate,d["dt"][t]); universe.append(code)
        if not d["v1"][t] or not np.isfinite(d["a120"][t]) or not np.isfinite(d["b120"][t]) or not np.isfinite(d["ext"][t]): continue
        if not np.isfinite(d["vol20"][t]) or d["vol20"][t]/1000<=VOL_MIN: continue  # 流動性:近20日日均量>1000張
        if not (0<=d["b120"][t]<1) or d["ext"][t]>EXT: continue
        cand.append((code,d))
    if not ddate or len(universe)<20: continue
    tcur=int(np.searchsorted(tdates,ddate))
    held_our={c:tt for c,tt in held_our.items() if tcur-tt<HOLD}
    held_mk={c:tt for c,tt in held_mk.items() if tcur-tt<HOLD}
    cand.sort(key=lambda x:-x[1]["a120"][np.searchsorted(x[1]["dt"],ddate)])
    # 我們: 跳過持有中後，取 rank SKIP+1 .. SKIP+TOPN (8-12名，平台中央，與6-10報酬等價但OOS更均衡)
    elig=[(code,d) for code,d in cand if code not in held_our]
    our=[]
    for code,d in elig[SKIP:SKIP+TOPN]:
        tt=np.searchsorted(d["dt"],ddate)
        our.append(dict(code=code,name=d["name"],market=d["mk"],close=round(float(d["C"][tt]),2),
            alpha120=round(float(d["a120"][tt]),4),beta120=round(float(d["b120"][tt]),3),d240h=round(float(d["d240h"][tt]),4)))
        held_our[code]=tcur
    if not our: continue
    D=pd.DataFrame(our); D["rank"]=range(D_RANK_START,D_RANK_START+len(D))
    D["regime"]=D["market"].map(lambda m:int(regime_ok(m,ddate))); D.insert(0,"pick_date",ddate)
    D.to_csv(f"{ROOT}/data/picks/{ddate}.csv",index=False,encoding="utf-8-sig")
    # 猴子: 隨機5(排除持有中的猴子)
    rng=random.Random(int(ddate.replace("-","")))
    pool=[c for c in universe if c not in held_mk]; rng.shuffle(pool); mk=pool[:TOPN]
    for c in mk: held_mk[c]=tcur
    M=pd.DataFrame([dict(pick_date=ddate,code=c,name=S[c]["name"],market=S[c]["mk"],
        close=round(float(S[c]["C"][np.searchsorted(S[c]["dt"],ddate)]),2)) for c in mk])
    M.to_csv(f"{ROOT}/data/monkey/{ddate}.csv",index=False,encoding="utf-8-sig"); n+=1
print(f"回填 {n} 週 (延伸<{EXT*100:.0f}% + 去重{HOLD}交易日)")
