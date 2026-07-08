# -*- coding: utf-8 -*-
"""產生本週推薦（我們 + 猴子）：
我們：多頭排列 → beta120∈[0,1] → alpha120排序 → 前5（data/picks/<日>.csv）
猴子：全市場隨機5檔，以資料日為種子（data/monkey/<日>.csv）— 致敬 Malkiel《漫步華爾街》"""
import os, sys, random
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

TOPN = 5
ROOT = lib.ROOT

def main():
    stocks = lib.load_stock_list()
    print(f"全市場 {len(stocks)} 檔", flush=True)
    idx = {"TWSE": lib.fetch_index("TAIEX"), "OTC": lib.fetch_index("TPEx")}
    prices = lib.fetch_prices(stocks["ticker"].tolist())
    print(f"抓到價格 {len(prices)} 檔", flush=True)

    rows = []; data_date = ""; universe = []
    for r in stocks.itertuples():
        df = prices.get(r.ticker)
        if df is None or idx[r.market].empty: continue
        feat = lib.compute_features(df, idx[r.market])
        last = feat.iloc[-1]
        if not np.isfinite(last["Close"]) or last["Close"] <= 0: continue
        data_date = max(data_date, str(last["date"]))
        universe.append((r.code, r.name, r.market, float(last["Close"])))
        if not last["v1"]: continue
        if not np.isfinite(last["alpha120"]) or not np.isfinite(last["beta120"]): continue
        if not (0 <= last["beta120"] < 1): continue
        rows.append(dict(code=r.code, name=r.name, market=r.market, close=round(float(last["Close"]),2),
                         alpha120=round(float(last["alpha120"]),4), beta120=round(float(last["beta120"]),3),
                         d240h=round(float(last["d240h"]),4)))
    if not rows:
        print("無符合條件的股票", flush=True); return
    D = pd.DataFrame(rows).sort_values("alpha120", ascending=False).reset_index(drop=True)
    D["rank"] = D.index + 1; D.insert(0, "pick_date", data_date)
    os.makedirs(os.path.join(ROOT, "data", "picks"), exist_ok=True)
    D.to_csv(os.path.join(ROOT, "data", "picks", f"{data_date}.csv"), index=False, encoding="utf-8-sig")
    print(f"資料日 {data_date}, 我們推薦前{TOPN}:", flush=True)
    for r in D.head(TOPN).itertuples():
        print(f"  {r.rank} {r.code} {r.name[:8]} α120={r.alpha120:+.2f} β120={r.beta120:.2f}", flush=True)
    # 猴子：以資料日為種子，全市場隨機5檔（可重現、不可事後竄改）
    rng = random.Random(int(data_date.replace("-", "")))
    mk = rng.sample(universe, min(TOPN, len(universe)))
    M = pd.DataFrame([dict(pick_date=data_date, code=c, name=n, market=m, close=round(cl,2)) for c,n,m,cl in mk])
    os.makedirs(os.path.join(ROOT, "data", "monkey"), exist_ok=True)
    M.to_csv(os.path.join(ROOT, "data", "monkey", f"{data_date}.csv"), index=False, encoding="utf-8-sig")
    print(f"🐒 猴子隨機5檔: {', '.join(c for c,_,_,_ in mk)}", flush=True)

if __name__ == "__main__":
    main()
