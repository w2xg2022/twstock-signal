# -*- coding: utf-8 -*-
"""產生本週推薦（定案策略）：
V1多頭排列篩選 → beta120∈[0,1]濾網 → alpha120排序 → 前5
輸出 data/picks/<資料日>.csv（含全部通過篩選的清單，rank<=5為推薦）"""
import os, sys
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

    rows = []; data_date = ""
    for r in stocks.itertuples():
        df = prices.get(r.ticker)
        if df is None or idx[r.market].empty: continue
        feat = lib.compute_features(df, idx[r.market])
        last = feat.iloc[-1]
        data_date = max(data_date, str(last["date"]))
        # 篩選: V1多頭排列 且 beta120∈[0,1]
        if not last["v1"]: continue
        if not np.isfinite(last["alpha120"]) or not np.isfinite(last["beta120"]): continue
        if not (0 <= last["beta120"] < 1): continue
        rows.append(dict(code=r.code, name=r.name, market=r.market, close=round(float(last["Close"]),2),
                         alpha120=round(float(last["alpha120"]),4), beta120=round(float(last["beta120"]),3),
                         d240h=round(float(last["d240h"]),4)))
    D = pd.DataFrame(rows)
    if D.empty:
        print("無符合條件的股票", flush=True); return
    # 排序：alpha120（風險調整後相對強勢）由高到低
    D = D.sort_values("alpha120", ascending=False).reset_index(drop=True)
    D["rank"] = D.index + 1
    D.insert(0, "pick_date", data_date)
    os.makedirs(os.path.join(ROOT, "data", "picks"), exist_ok=True)
    fp = os.path.join(ROOT, "data", "picks", f"{data_date}.csv")
    D.to_csv(fp, index=False, encoding="utf-8-sig")
    print(f"資料日 {data_date}, 通過篩選 {len(D)} 檔, 推薦前{TOPN}:", flush=True)
    for r in D.head(TOPN).itertuples():
        print(f"  {r.rank:>2} {r.code} {r.name[:8]:<9} {('上市' if r.market=='TWSE' else '上櫃')} "
              f"α120={r.alpha120:+.2f} β120={r.beta120:.2f} 距52高={r.d240h*100:+.1f}%", flush=True)
    print(f"寫入 {fp}", flush=True)

if __name__ == "__main__":
    main()
