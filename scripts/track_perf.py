# -*- coding: utf-8 -*-
"""樣本外對戰成績單：每週個股明細 + 每週彙總（不做累積壓縮）
每檔：進場=推薦隔日(H+L)/2 → 追蹤到最新交易日；
  收盤報酬% = 最新收盤/進場 − 1；最高報酬% = 進場後區間最高價/進場 − 1
分「我們 / 猴子」，對照同期大盤(加權指數)。輸出 data/performance.json
週狀態：距今交易日 < 20 = 預測中；>= 20 = 已結束。"""
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

def main():
    ours = load("picks", TOPN); monk = load("monkey")
    if not ours: print("尚無推薦"); return
    slist = lib.load_stock_list().set_index("code")
    allcodes = set()
    for d in list(ours.values()) + list(monk.values()): allcodes |= set(d["code"].astype(str))
    prices = lib.fetch_prices([slist.loc[c, "ticker"] for c in allcodes if c in slist.index])
    taiex = lib.fetch_index("TAIEX")
    tdates = taiex["date"].values.astype(str); tidx = taiex["idx"].values.astype(float); latest = tdates[-1]

    def pick_detail(code, name, market, pick_date):
        if code not in slist.index: return None
        df = prices.get(slist.loc[code, "ticker"])
        if df is None: return None
        dts = df["date"].values.astype(str)
        j = np.searchsorted(dts, str(pick_date), "right")
        if j >= len(df): return None
        H = df["High"].values.astype(float); L = df["Low"].values.astype(float); C = df["Close"].values.astype(float)
        e = (H[j] + L[j]) / 2
        if e <= 0: return None
        return {"code": code, "name": name, "market": market,
                "close": round(float(C[-1]/e-1)*100, 1), "max": round(float(np.max(H[j:])/e-1)*100, 1)}

    def week_detail(df, pick_date):
        out = []
        for r in df.itertuples():
            d = pick_detail(r.code, r.name, r.market, pick_date)
            if d: out.append(d)
        return out

    weeks = sorted(set(ours) | set(monk), reverse=True)  # 新→舊
    agg = []; detail = []
    for w in weeks:
        j = np.searchsorted(tdates, w, "right")
        if j >= len(tdates): continue
        days = int(len(tdates) - 1 - j)
        mkt = round(float(tidx[-1]/tidx[j]-1)*100, 2) if tidx[j] > 0 else None
        od = week_detail(ours[w], w) if w in ours else []
        md = week_detail(monk[w], w) if w in monk else []
        avg = lambda lst,k: round(float(np.mean([x[k] for x in lst])),2) if lst else None
        agg.append({"date": w, "days": days, "status": "settled" if days >= SETTLE else "running",
                    "our_close": avg(od,"close"), "our_max": avg(od,"max"),
                    "monkey_close": avg(md,"close"), "monkey_max": avg(md,"max"), "market": mkt})
        detail.append({"date": w, "days": days, "status": "settled" if days >= SETTLE else "running",
                       "market": mkt, "our": od, "monkey": md})
    def gavg(key):
        v = [r[key] for r in agg if r[key] is not None]
        return round(float(np.mean(v)),2) if v else None
    summary = {"updated": pd.Timestamp.now("UTC").isoformat(), "latest_date": latest, "n_weeks": len(agg),
               "weeks": agg, "detail": detail,
               "avg": {k: gavg(k) for k in ["our_close","our_max","monkey_close","monkey_max","market"]}}
    json.dump(summary, open(os.path.join(ROOT,"data","performance.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    ns = sum(1 for r in agg if r["status"]=="settled")
    print(f"{len(agg)}週 (預測中{len(agg)-ns}/已結束{ns}). 平均收盤 我們{summary['avg']['our_close']}% 猴子{summary['avg']['monkey_close']}% 大盤{summary['avg']['market']}%", flush=True)

if __name__ == "__main__":
    main()
