# -*- coding: utf-8 -*-
"""樣本外對戰成績單：每週個股明細（我們上/猴子下）+ 每週彙總
每檔：買入價=推薦隔日(H+L)/2；當前價=最新收盤；最高價=進場後區間最高；
  報酬%(收盤)=當前/買入−1；報酬%(最高)=最高/買入−1。組內依收盤報酬由高到低。
大盤分 上市(TAIEX)/上櫃(TPEx)。週狀態：距今交易日 <20 預測中；>=20 已結束。
輸出 data/performance.json"""
import os, sys, json, glob
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

TOPN = 5; ROOT = lib.ROOT; SETTLE = 20

def load(dirn, rank_cap=None):
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "data", dirn, "*.csv"))):
        d = pd.read_csv(f, dtype={"code": str})
        if rank_cap and "rank" in d: d = d[d["rank"] <= rank_cap]
        out[os.path.basename(f)[:-4]] = d
    return out

def idx_ret(idxdf, pick_date):
    dts = idxdf["date"].values.astype(str); v = idxdf["idx"].values.astype(float)
    j = np.searchsorted(dts, str(pick_date), "right")
    if j >= len(v) or v[j] <= 0: return None
    return round(float(v[-1]/v[j]-1)*100, 2)

def main():
    ours = load("picks", TOPN); monk = load("monkey")
    if not ours: print("尚無推薦"); return
    slist = lib.load_stock_list().set_index("code")
    allcodes = set()
    for d in list(ours.values()) + list(monk.values()): allcodes |= set(d["code"].astype(str))
    prices = lib.fetch_prices([slist.loc[c, "ticker"] for c in allcodes if c in slist.index])
    taiex = lib.fetch_index("TAIEX"); tpex = lib.fetch_index("TPEx")
    tdates = taiex["date"].values.astype(str); latest = tdates[-1]

    def detail_one(code, name, market, pick_date):
        if code not in slist.index: return None
        df = prices.get(slist.loc[code, "ticker"])
        if df is None: return None
        dts = df["date"].values.astype(str)
        j = np.searchsorted(dts, str(pick_date), "right")
        if j >= len(df): return None
        H = df["High"].values.astype(float); L = df["Low"].values.astype(float); C = df["Close"].values.astype(float)
        e = (H[j] + L[j]) / 2
        if e <= 0: return None
        hi = float(np.max(H[j:])); cur = float(C[-1])
        return {"code": code, "name": name, "market": market,
                "entry": round(e,2), "cur": round(cur,2), "hi": round(hi,2),
                "rc": round((cur/e-1)*100,1), "rm": round((hi/e-1)*100,1)}

    def week_list(df, pick_date):
        out = [d for r in df.itertuples() if (d := detail_one(r.code, r.name, r.market, pick_date))]
        out.sort(key=lambda x: -x["rc"])  # 報酬(收盤)高的在前
        return out

    weeks = sorted(set(ours) | set(monk), reverse=True)
    agg = []; detail = []
    for w in weeks:
        j = np.searchsorted(tdates, w, "right")
        if j >= len(tdates): continue
        days = int(len(tdates) - 1 - j)
        m_tw = idx_ret(taiex, w); m_ot = idx_ret(tpex, w)
        od = week_list(ours[w], w) if w in ours else []
        md = week_list(monk[w], w) if w in monk else []
        avg = lambda lst, k: round(float(np.mean([x[k] for x in lst])), 2) if lst else None
        st = "settled" if days >= SETTLE else "running"
        agg.append({"date": w, "days": days, "status": st,
                    "our_close": avg(od,"rc"), "our_max": avg(od,"rm"),
                    "monkey_close": avg(md,"rc"), "monkey_max": avg(md,"rm"),
                    "market_twse": m_tw, "market_otc": m_ot})
        detail.append({"date": w, "days": days, "status": st, "market_twse": m_tw, "market_otc": m_ot,
                       "our": od, "monkey": md})
    def gavg(key):
        v = [r[key] for r in agg if r[key] is not None]
        return round(float(np.mean(v)),2) if v else None
    summary = {"updated": pd.Timestamp.now("UTC").isoformat(), "latest_date": latest, "n_weeks": len(agg),
               "weeks": agg, "detail": detail,
               "avg": {k: gavg(k) for k in ["our_close","our_max","monkey_close","monkey_max","market_twse","market_otc"]}}
    json.dump(summary, open(os.path.join(ROOT,"data","performance.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    ns = sum(1 for r in agg if r["status"]=="settled")
    print(f"{len(agg)}週 (預測中{len(agg)-ns}/已結束{ns}). 平均收盤 我們{summary['avg']['our_close']}% 猴子{summary['avg']['monkey_close']}% 大盤上市{summary['avg']['market_twse']}%/上櫃{summary['avg']['market_otc']}%", flush=True)

if __name__ == "__main__":
    main()
