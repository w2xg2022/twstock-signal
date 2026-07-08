# -*- coding: utf-8 -*-
"""樣本外成績單：讀 data/picks/*.csv 的推薦 + 最新價，算每期推薦事後報酬（對大盤超額）
主指標=進場後第15~20天均價(TWAP,去單日雜訊)；另記 5/10/20/30日 供參考。
輸出 data/performance.json"""
import os, sys, json, glob
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

TOPN = 5; ROOT = lib.ROOT

def main():
    files = sorted(glob.glob(os.path.join(ROOT, "data", "picks", "*.csv")))
    if not files:
        print("尚無推薦紀錄", flush=True); return
    P = pd.concat([pd.read_csv(f, dtype={"code": str}) for f in files], ignore_index=True)
    P = P[P["rank"] <= TOPN]
    slist = lib.load_stock_list().set_index("code")
    codes = [c for c in P["code"].unique() if c in slist.index]
    prices = lib.fetch_prices([slist.loc[c, "ticker"] for c in codes])
    idx = {"TWSE": lib.fetch_index("TAIEX"), "OTC": lib.fetch_index("TPEx")}

    per = []
    for r in P.itertuples():
        if r.code not in slist.index: continue
        tk = slist.loc[r.code, "ticker"]; mk = slist.loc[r.code, "market"]
        df = prices.get(tk)
        if df is None or idx[mk].empty: continue
        d = df.merge(idx[mk], on="date", how="left"); d["idx"] = d["idx"].ffill()
        dts = d["date"].values.astype(str)
        j = np.searchsorted(dts, str(r.pick_date), "right")  # 推薦後下一交易日=進場
        if j >= len(d) - 1: continue
        H = d["High"].values.astype(float); L = d["Low"].values.astype(float)
        C = d["Close"].values.astype(float); IX = d["idx"].values.astype(float)
        entry = (H[j] + L[j]) / 2
        if entry <= 0 or IX[j] <= 0: continue
        rec = dict(pick_date=str(r.pick_date), code=r.code, name=r.name)
        # 主指標: 第15-20天均價 超額
        if j + 20 < len(d):
            px = np.mean(C[j+15:j+21]); ii = np.mean(IX[j+15:j+21])
            rec["x_w1520"] = (px/entry - 1) - (ii/IX[j] - 1)
        for h in [5, 10, 20, 30]:
            if j + h < len(d):
                rec[f"x{h}"] = (C[j+h]/entry - 1) - (IX[j+h]/IX[j] - 1)
        per.append(rec)
    PP = pd.DataFrame(per)
    summary = {"updated": pd.Timestamp.utcnow().isoformat(), "n_weeks": len(files),
               "n_picks_tracked": len(PP), "exit_rule": "進場後第15-20天均價(TWAP)", "horizons": {}}
    for col, lab in [("x_w1520", "15-20日均價(主)"), ("x5", "5日"), ("x10", "10日"), ("x20", "20日"), ("x30", "30日")]:
        if col in PP and PP[col].notna().any():
            v = PP[col].dropna().values
            summary["horizons"][lab] = dict(n=int(len(v)), mean_excess=round(float(v.mean())*100, 2),
                                            win_rate=round(float((v > 0).mean())*100, 1),
                                            median_excess=round(float(np.median(v))*100, 2))
    if "x_w1520" in PP:
        wk = PP.dropna(subset=["x_w1520"]).groupby("pick_date")["x_w1520"].mean()
        eq = (1 + wk).cumprod()
        summary["equity_curve"] = [{"date": d, "excess_mean": round(v*100, 2), "cum": round(c-1, 4)}
                                   for d, v, c in zip(wk.index, wk.values, eq.values)]
    with open(os.path.join(ROOT, "data", "performance.json"), "w", encoding="utf-8") as fo:
        json.dump(summary, fo, ensure_ascii=False, indent=1)
    print("績效彙總：", json.dumps(summary["horizons"], ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
