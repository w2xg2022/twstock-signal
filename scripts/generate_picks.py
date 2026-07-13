# -*- coding: utf-8 -*-
"""產生本週入選（我們 + 猴子）：
我們：4層多頭排列(MA5>10>20>60,MA20升,收盤>MA5) → 量>1000張 → beta120∈[0,1] → 收盤離MA20<10% → alpha120排序取第6-10名
去重：20交易日內(持有期)已入選過的不再選，由下一名遞補；猴子同理
猴子：全市場隨機5檔，以資料日為種子 — 致敬 Malkiel《漫步華爾街》"""
import os, sys, glob, random
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

TOPN = 5; EXT = 0.10; HOLD = 20; VOL_MIN = 1000; SKIP = 5; MA_REG = 60; REG_CONFIRM = 5; PRICE_MAX = 200; N_MONKEY = 10; ROOT = lib.ROOT  # SKIP:取6-10; REG_CONFIRM:連續5天跌破才轉弱; PRICE_MAX:排除入選日收盤>=200的貴股(高原120-200,取200); N_MONKEY:猴子隻數(取報酬中位數那隻展示)

def held_within(dirn, taiex_dates, cur_i):
    """回傳 20交易日內已入選的 code 集合"""
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
    tdays = {mk: set(idf["date"].values.astype(str)) for mk, idf in idx.items()}  # FinMind大盤指數=權威交易日曆;有無交易日以此為準,擋yfinance休市日(如颱風)的幽靈K棒
    # regime 濾網：市場指數站上 MA60(季線) 才進場，跌破則該市場的股票標記轉弱(判定空手)
    regime_ok = {}  # 連續5天跌破MA60才轉弱(避免單日插針whipsaw)
    for mk, idf in idx.items():
        v = idf["idx"].values.astype(float); ma = pd.Series(v).rolling(MA_REG).mean().values
        cb = 0  # 從最後一日往回數連續跌破MA60的天數
        for k in range(len(v) - 1, -1, -1):
            if np.isfinite(ma[k]) and v[k] < ma[k]: cb += 1
            else: break
        regime_ok[mk] = bool(len(v) >= MA_REG and cb < REG_CONFIRM)
    print(f"regime: 上市{'多' if regime_ok['TWSE'] else '空'} 上櫃{'多' if regime_ok['OTC'] else '空'}", flush=True)
    prices = lib.fetch_prices(stocks["ticker"].tolist())
    print(f"抓到價格 {len(prices)} 檔", flush=True)

    rows = []; data_date = ""; universe = []
    for r in stocks.itertuples():
        df = prices.get(r.ticker)
        if df is None or idx[r.market].empty: continue
        df = df[df["date"].isin(tdays[r.market])]  # 只保留FinMind有的交易日:擋掉yfinance幽靈K棒(否則會誤產休市日入選)
        if len(df) < 260: continue
        cl = float(df["Close"].iloc[-1])  # 便宜取最新收盤:先擋貴股,超過門檻不必算features
        if not np.isfinite(cl) or cl <= 0: continue
        data_date = max(data_date, str(df["date"].iloc[-1]))
        universe.append((r.code, r.name, r.market, cl))  # 全市場(給猴子),不套價格/選股濾網
        if cl >= PRICE_MAX: continue  # 貴股:已入universe,跳過4層MA/alpha/beta計算(省算力)
        feat = lib.compute_features(df, idx[r.market]); last = feat.iloc[-1]
        if not np.isfinite(last["Close"]) or last["Close"] <= 0: continue
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
    # 我們：alpha 由高到低，跳過持有中，取第 SKIP+1 .. SKIP+TOPN 名(6-10,配4層排列，walk-forward最佳)
    # 大樣本證實：最高alpha最延伸易回落，第6-13名是穩健高原;取8-12(平台中央)與6-10報酬統計等價(t≈0.2)但OOS前後半更均衡
    D = pd.DataFrame(rows).sort_values("alpha120", ascending=False)
    D = D[~D["code"].isin(held_our)].reset_index(drop=True)
    start = min(SKIP, max(0, len(D) - TOPN))  # 弱市候選不足時自動下移,保證取滿TOPN檔、仍避開最前段
    D = D.iloc[start:start+TOPN].reset_index(drop=True)
    D["rank"] = range(start + 1, start + 1 + len(D))
    D["regime"] = D["market"].map(lambda m: int(regime_ok[m]))  # 1=市場站上季線可進場; 0=轉弱判定空手
    D.insert(0, "pick_date", data_date)
    os.makedirs(os.path.join(ROOT, "data", "picks"), exist_ok=True)
    D.to_csv(os.path.join(ROOT, "data", "picks", f"{data_date}.csv"), index=False, encoding="utf-8-sig")
    print(f"資料日 {data_date}, 我們入選前{len(D)}:", flush=True)
    for r in D.itertuples():
        print(f"  {r.rank} {r.code} {r.name[:8]} α120={r.alpha120:+.2f} β120={r.beta120:.2f}", flush=True)
    # 猴子：N_MONKEY 隻各自隨機5檔(種子=資料日×100+k,可重現);track_perf 取報酬中位數那隻展示,移除單隻運氣
    rows_m = []; base = int(data_date.replace("-", ""))
    for k in range(N_MONKEY):
        rng = random.Random(base * 100 + k)
        pool = universe[:]; rng.shuffle(pool); mk = pool[:TOPN]  # 全市場隨機5(不套濾網、不去重,各猴子獨立)
        for c,n,m,cl in mk:
            rows_m.append(dict(monkey_id=k, pick_date=data_date, code=c, name=n, market=m, close=round(cl,2)))
    M = pd.DataFrame(rows_m)
    os.makedirs(os.path.join(ROOT, "data", "monkey"), exist_ok=True)
    M.to_csv(os.path.join(ROOT, "data", "monkey", f"{data_date}.csv"), index=False, encoding="utf-8-sig")
    print(f"🐒 產生 {N_MONKEY} 隻猴子(各5檔), track_perf 取報酬中位數展示", flush=True)

if __name__ == "__main__":
    main()
