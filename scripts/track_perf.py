# -*- coding: utf-8 -*-
"""樣本外對戰成績單：我們(前5) vs 猴子(隨機5)
每檔報酬 = 進場(推薦隔日(H+L)/2) → 第15-20天均價(TWAP) 的「超越大盤」報酬。
每週取5檔平均，累積成權益曲線。輸出 data/performance.json"""
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

def excess_1520(df, idxdf, entry_date):
    d = df.merge(idxdf, on="date", how="left"); d["idx"] = d["idx"].ffill()
    dts = d["date"].values.astype(str)
    j = np.searchsorted(dts, str(entry_date), "right")  # 推薦後下一交易日=進場
    if j >= len(d) or j + 20 >= len(d): return None
    H = d["High"].values.astype(float); L = d["Low"].values.astype(float)
    C = d["Close"].values.astype(float); IX = d["idx"].values.astype(float)
    e = (H[j] + L[j]) / 2
    if e <= 0 or IX[j] <= 0: return None
    px = np.mean(C[j+15:j+21]); ii = np.mean(IX[j+15:j+21])
    return (px/e - 1) - (ii/IX[j] - 1)

def main():
    ours = load("picks", TOPN); monk = load("monkey")
    if not ours: print("尚無推薦"); return
    slist = lib.load_stock_list().set_index("code")
    allcodes = set()
    for d in list(ours.values()) + list(monk.values()): allcodes |= set(d["code"].astype(str))
    tickers = [slist.loc[c, "ticker"] for c in allcodes if c in slist.index]
    prices = lib.fetch_prices(tickers)
    idx = {"TWSE": lib.fetch_index("TAIEX"), "OTC": lib.fetch_index("TPEx")}
    def week_excess(df):
        vals = []
        for r in df.itertuples():
            if r.code not in slist.index: continue
            tk = slist.loc[r.code, "ticker"]; mk = slist.loc[r.code, "market"]
            p = prices.get(tk)
            if p is None or idx[mk].empty: continue
            x = excess_1520(p, idx[mk], r.pick_date)
            if x is not None: vals.append(x)
        return np.mean(vals)*100 if vals else None
    weeks = sorted(set(ours) | set(monk))
    hist = []
    for w in weeks:
        oe = week_excess(ours[w]) if w in ours else None
        me = week_excess(monk[w]) if w in monk else None
        hist.append({"date": w, "our": None if oe is None else round(oe,2),
                     "monkey": None if me is None else round(me,2)})
    done = [h for h in hist if h["our"] is not None and h["monkey"] is not None]
    def cum(key):
        c=1.0; out=[]
        for h in done: c*=(1+h[key]/100); out.append(round(c-1,4))
        return out
    oc, mc = cum("our"), cum("monkey")
    summary = {"updated": pd.Timestamp.now("UTC").isoformat(),
               "n_weeks_done": len(done),
               "our_avg": round(np.mean([h["our"] for h in done]),2) if done else None,
               "monkey_avg": round(np.mean([h["monkey"] for h in done]),2) if done else None,
               "our_beats_monkey_weeks": sum(1 for h in done if h["our"]>h["monkey"]),
               "our_cum": oc[-1] if oc else None, "monkey_cum": mc[-1] if mc else None,
               "history": hist,
               "cum_curve": [{"date":done[i]["date"],"our":oc[i],"monkey":mc[i]} for i in range(len(done))]}
    with open(os.path.join(ROOT,"data","performance.json"),"w",encoding="utf-8") as f:
        json.dump(summary,f,ensure_ascii=False,indent=1)
    print(f"對戰: {len(done)}週已結算, 我們均{summary['our_avg']}% vs 猴子{summary['monkey_avg']}%, 我們贏{summary['our_beats_monkey_weeks']}週",flush=True)

if __name__ == "__main__":
    main()
