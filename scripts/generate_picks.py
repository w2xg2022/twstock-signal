# -*- coding: utf-8 -*-
"""產生本週推薦（我們 + 猴子）：
我們：多頭排列 → beta120∈[0,1] → 收盤離MA20<10% → alpha120排序 → 前5
去重：20交易日內(持有期)已推薦過的不再選，由下一名遞補；猴子同理
猴子：全市場隨機5檔，以資料日為種子 — 致敬 Malkiel《漫步華爾街》"""
import os, sys, glob, random
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

TOPN = 5; EXT = 0.10; HOLD = 20; VOL_MIN = 1000; SKIP = 5; ROOT = lib.ROOT  # VOL_MIN:近20日日均量下限(張); SKIP:跳過前幾名alpha(取6-10名)

def held_within(dirn, taiex_dates, cur_i):
    """回傳 20交易日內已推薦的 code 集合"""
    held = set()
    for f in glob.glob(os.path.join(ROOT, "data", dirn, "*.csv")):
        pd_ = os.path.basename(f)[:-4]
        pi = int(np.searchsorted(taiex_dates, pd_))
        if 0 <= cur_i - pi < HOLD:
            try: held |= set(pd.read_csv(f, dtype={"code": str})["code"].astype(str))
            except Exception: pass
    return held

def main():
    stocks = lib.load_stock_list()
    print(f"全市場 {len(stocks)} 檔", flush=True)
    idx = {"TWSE": lib.fetch_index("TAIEX"), "OTC": lib.fetch_index("TPEx")}
    tdates = idx["TWSE"]["date"].values.astype(str)
    prices = lib.fetch_prices(stocks["ticker"].tolist())
    print(f"抓到價格 {len(prices)} 檔", flush=True)

    rows = []; data_date = ""; universe = []
    for r in stocks.itertuples():
        df = prices.get(r.ticker)
        if df is None or idx[r.market].empty: continue
        feat = lib.compute_features(df, idx[r.market]); last = feat.iloc[-1]
        if not np.isfinite(last["Close"]) or last["Close"] <= 0: continue
        data_date = max(data_date, str(last["date"]))
        universe.append((r.code, r.name, r.market, float(last["Close"])))
        if not last["v1"]: continue
        if not np.isfinite(last["vol20"]) or last["vol20"]/1000 <= VOL_MIN: continue  # 流動性:近20日日均量>1000張
        if not all(np.isfinite(last[k]) for k in ["alpha120","beta120","ext"]): continue
        if not (0 <= last["beta120"] < 1) or last["ext"] > EXT: continue
        rows.append(dict(code=r.code, name=r.name, market=r.market, close=round(float(last["Close"]),2),
                         alpha120=round(float(last["alpha120"]),4), beta120=round(float(last["beta120"]),3),
                         d240h=round(float(last["d240h"]),4)))
    if not rows:
        print("無符合條件的股票", flush=True); return
    cur_i = int(np.searchsorted(tdates, data_date))
    held_our = held_within("picks", tdates, cur_i)
    held_mk = held_within("monkey", tdates, cur_i)
    # 我們：alpha 由高到低，跳過持有中，取第 SKIP+1 .. SKIP+TOPN 名(6-10)
    # 大樣本(116期,扣成本)證實：最高alpha最延伸易回落，中段動能(6-10)超額最佳且OOS穩健
    D = pd.DataFrame(rows).sort_values("alpha120", ascending=False)
    D = D[~D["code"].isin(held_our)].reset_index(drop=True).iloc[SKIP:SKIP+TOPN].reset_index(drop=True)
    D["rank"] = range(SKIP + 1, SKIP + 1 + len(D)); D.insert(0, "pick_date", data_date)
    os.makedirs(os.path.join(ROOT, "data", "picks"), exist_ok=True)
    D.to_csv(os.path.join(ROOT, "data", "picks", f"{data_date}.csv"), index=False, encoding="utf-8-sig")
    print(f"資料日 {data_date}, 我們推薦前{len(D)}:", flush=True)
    for r in D.itertuples():
        print(f"  {r.rank} {r.code} {r.name[:8]} α120={r.alpha120:+.2f} β120={r.beta120:.2f}", flush=True)
    # 猴子：以資料日為種子隨機5檔（排除持有中）
    rng = random.Random(int(data_date.replace("-", "")))
    pool = [u for u in universe if u[0] not in held_mk]; rng.shuffle(pool); mk = pool[:TOPN]
    M = pd.DataFrame([dict(pick_date=data_date, code=c, name=n, market=m, close=round(cl,2)) for c,n,m,cl in mk])
    os.makedirs(os.path.join(ROOT, "data", "monkey"), exist_ok=True)
    M.to_csv(os.path.join(ROOT, "data", "monkey", f"{data_date}.csv"), index=False, encoding="utf-8-sig")
    print(f"🐒 猴子隨機5檔: {', '.join(c for c,_,_,_ in mk)}", flush=True)

if __name__ == "__main__":
    main()
