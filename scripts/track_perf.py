# -*- coding: utf-8 -*-
"""樣本外對戰成績單（每週一列，不做累積壓縮）
每檔：進場=推薦隔日(H+L)/2 → 追蹤到最新交易日；報酬有兩種：
  收盤報酬% = 最新收盤/進場 − 1；最高報酬% = 進場後區間最高價/進場 − 1
每週取 5 檔平均，分「我們 / 猴子」，並對照同期大盤(加權指數)走勢。輸出 data/performance.json"""
import os, sys, json, glob
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

TOPN = 5; ROOT = lib.ROOT

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
    tdates = taiex["date"].values.astype(str); tidx = taiex["idx"].values.astype(float)
    latest = tdates[-1]

    def pick_ret(code, pick_date):
        """回傳 (收盤報酬, 最高報酬, 進場日index_in_taiex)"""
        if code not in slist.index: return None
        df = prices.get(slist.loc[code, "ticker"])
        if df is None: return None
        dts = df["date"].values.astype(str)
        j = np.searchsorted(dts, str(pick_date), "right")  # 進場=推薦隔日
        if j >= len(df): return None
        H = df["High"].values.astype(float); L = df["Low"].values.astype(float); C = df["Close"].values.astype(float)
        e = (H[j] + L[j]) / 2
        if e <= 0: return None
        close_r = C[-1] / e - 1
        max_r = np.max(H[j:]) / e - 1
        return close_r, max_r

    def week_avg(df, pick_date):
        cr, mr = [], []
        for r in df.itertuples():
            v = pick_ret(r.code, pick_date)
            if v: cr.append(v[0]); mr.append(v[1])
        if not cr: return None, None
        return np.mean(cr)*100, np.mean(mr)*100

    weeks = sorted(set(ours) | set(monk))
    rows = []
    for w in weeks:
        # 進場日 = w 的隔一交易日；距今交易日數 & 大盤報酬 用 TAIEX
        j = np.searchsorted(tdates, w, "right")
        if j >= len(tdates): continue
        days = len(tdates) - 1 - j
        mkt = round(float(tidx[-1]/tidx[j] - 1)*100, 2) if tidx[j] > 0 else None
        oc, om = week_avg(ours[w], w) if w in ours else (None, None)
        mc, mm = week_avg(monk[w], w) if w in monk else (None, None)
        rows.append({"date": w, "days": int(days),
                     "our_close": None if oc is None else round(oc,2), "our_max": None if om is None else round(om,2),
                     "monkey_close": None if mc is None else round(mc,2), "monkey_max": None if mm is None else round(mm,2),
                     "market": mkt})
    def avg(key):
        v = [r[key] for r in rows if r[key] is not None]
        return round(float(np.mean(v)),2) if v else None
    summary = {"updated": pd.Timestamp.now("UTC").isoformat(), "latest_date": latest, "n_weeks": len(rows),
               "weeks": rows,
               "avg": {k: avg(k) for k in ["our_close","our_max","monkey_close","monkey_max","market"]}}
    with open(os.path.join(ROOT,"data","performance.json"),"w",encoding="utf-8") as f:
        json.dump(summary,f,ensure_ascii=False,indent=1)
    a = summary["avg"]
    print(f"{len(rows)}週. 平均(收盤): 我們{a['our_close']}% 猴子{a['monkey_close']}% 大盤{a['market']}%",flush=True)

if __name__ == "__main__":
    main()
