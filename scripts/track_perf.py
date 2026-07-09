# -*- coding: utf-8 -*-
"""樣本外對戰成績單：每週個股明細（我們/猴子）+ 每週彙總
每檔：買入價=推薦隔日(H+L)/2；出場=ATR移動停利（收盤自持有期高點回落 ATR_K×ATR(14) 即出場，最長抱 MAXH 天）。
  賣出價=出場當日收盤（未出場則=最新收盤，仍持有）；最高價=進場至出場區間最高。
  報酬%(收盤)=賣出/買入−1；報酬%(最高)=最高/買入−1（皆取2位小數，用還原價）。組內依收盤報酬由高到低。
大盤分 上市(TAIEX)/上櫃(TPEx)，各有 收盤%/最高%。
週狀態：該週我們+猴子 10 檔全部出場=已結束；否則預測中。輸出 data/performance.json"""
import os, sys, json, glob
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

TOPN = 5; ROOT = lib.ROOT; ATR_N = 14; ATR_K = 3.0; MAXH = 60  # ATR移動停利:回落ATR_K倍ATR出場,最長持有MAXH交易日

def load(dirn, rank_cap=None):
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "data", dirn, "*.csv"))):
        d = pd.read_csv(f, dtype={"code": str})
        if rank_cap and "rank" in d: d = d[d["rank"] <= rank_cap]
        out[os.path.basename(f)[:-4]] = d
    return out

def tick(p):
    """湊到台股合法升降單位(檔位)"""
    if p < 10: t = 0.01
    elif p < 50: t = 0.05
    elif p < 100: t = 0.1
    elif p < 500: t = 0.5
    elif p < 1000: t = 1.0
    else: t = 5.0
    return round(round(p / t) * t, 2)

def idx_ret(idxdf, pick_date):
    dts = idxdf["date"].values.astype(str); v = idxdf["idx"].values.astype(float)
    j = np.searchsorted(dts, str(pick_date), "right")  # j=次一交易日；j-1=推薦日
    if j >= len(v) or j < 1: return None, None
    base = (v[j-1] + v[j]) / 2   # 大盤基準=推薦日收盤與次一交易日收盤的均值(降低次日單日大漲跌造成的失真)
    if base <= 0: return None, None
    return round(float(v[-1]/base-1)*100, 2), round(float(np.max(v[j:])/base-1)*100, 2)

def main():
    ours = load("picks"); monk = load("monkey")  # picks已是選定的5檔(rank 6-10)，不再用rank_cap過濾
    if not ours: print("尚無推薦"); return
    slist = lib.load_stock_list().set_index("code")
    allcodes = set()
    for d in list(ours.values()) + list(monk.values()): allcodes |= set(d["code"].astype(str))
    prices = lib.fetch_prices([slist.loc[c, "ticker"] for c in allcodes if c in slist.index])
    taiex = lib.fetch_index("TAIEX"); tpex = lib.fetch_index("TPEx")
    tdates = taiex["date"].values.astype(str); latest = tdates[-1]

    def detail_one(code, name, market, pick_date, regime=1):
        if code not in slist.index: return None
        name = str(slist.loc[code, "name"])  # 一律用清單簡稱顯示
        df = prices.get(slist.loc[code, "ticker"])
        if df is None: return None
        dts = df["date"].values.astype(str)
        j = np.searchsorted(dts, str(pick_date), "right")  # 進場=推薦隔日
        if j >= len(df): return None
        H = df["High"].values.astype(float); L = df["Low"].values.astype(float); C = df["Close"].values.astype(float)         # 原始(顯示)
        aH = df["aHigh"].values.astype(float); aC = df["aClose"].values.astype(float)                                          # 還原(報酬)
        e = tick((H[j] + L[j]) / 2)  # 買入價=當日(高+低)/2，湊合法檔位
        if e <= 0 or C[j] <= 0: return None
        ae = e * (aC[j] / C[j])       # 對應還原買入價
        # ATR(14) 移動停利：收盤自持有期高點回落 ATR_K×ATR 即出場；最長抱 MAXH 天
        pcC = np.r_[C[0], C[:-1]]
        tr = np.maximum.reduce([H - L, np.abs(H - pcC), np.abs(L - pcC)])
        atr = pd.Series(tr).rolling(ATR_N).mean().values
        end = len(df) - 1; cap = j + MAXH
        exit_i = None; peak = H[j]
        for i in range(j, min(cap, end) + 1):
            if np.isfinite(atr[i]) and C[i] <= peak - ATR_K * atr[i]:
                exit_i = i; break
            peak = max(peak, H[i])
        if exit_i is not None: exited = True                 # ATR 觸發出場
        elif cap <= end: exit_i = cap; exited = True         # 抱滿 MAXH 天到期出場
        else: exit_i = end; exited = False                   # 未觸發、也還沒滿 MAXH 天 -> 仍持有
        sell = float(C[exit_i]); sell_a = float(aC[exit_i])
        hi_r = float(np.max(H[j:exit_i+1])); hi_a = float(np.max(aH[j:exit_i+1]))
        return {"code": code, "name": name, "market": market, "regime": int(regime),
                "entry": e, "cur": round(sell,2), "hi": round(hi_r,2),
                "rc": round((sell_a/ae-1)*100,2), "rm": round((hi_a/ae-1)*100,2),
                "exited": bool(exited), "hold": int(exit_i - j)}

    def week_list(df, pick_date):
        out = [d for r in df.itertuples() if (d := detail_one(r.code, r.name, r.market, pick_date, getattr(r, "regime", 1)))]
        out.sort(key=lambda x: -x["rc"])
        return out

    weeks = sorted(set(ours) | set(monk), reverse=True)
    agg = []; detail = []
    for w in weeks:
        j = np.searchsorted(tdates, w, "right")
        if j >= len(tdates): continue
        days = int(len(tdates) - 1 - j)
        mtc, mtm = idx_ret(taiex, w); moc, mom = idx_ret(tpex, w)
        od = week_list(ours[w], w) if w in ours else []
        md = week_list(monk[w], w) if w in monk else []
        avg = lambda lst, k: round(float(np.mean([x[k] for x in lst])), 2) if lst else None
        # 套用regime版：轉弱(regime=0)的股票視為空手(該檔報酬=0)
        avgr = lambda lst, k: round(float(np.mean([(x[k] if x["regime"] else 0.0) for x in lst])), 2) if lst else None
        alls = od + md
        settled = bool(alls) and all(x["exited"] for x in alls)  # 我們+猴子全部出場才算已結束
        st = "settled" if settled else "running"
        nwk = sum(1 for x in od if not x["regime"])  # 本週我們有幾檔轉弱(建議空手)
        mkt = {"market_twse_close": mtc, "market_twse_max": mtm, "market_otc_close": moc, "market_otc_max": mom}
        agg.append({"date": w, "days": days, "status": st,
                    "our_close": avg(od,"rc"), "our_max": avg(od,"rm"),
                    "our_close_reg": avgr(od,"rc"), "our_max_reg": avgr(od,"rm"), "weak": nwk,
                    "our_close_t80": top80(od,"rc"), "monkey_close_t80": top80(md,"rc"),
                    "monkey_close": avg(md,"rc"), "monkey_max": avg(md,"rm"), **mkt})
        detail.append({"date": w, "days": days, "status": st, "weak": nwk, "our": od, "monkey": md, **mkt})
    keys = ["our_close","our_max","our_close_reg","our_max_reg","monkey_close","monkey_max","market_twse_close","market_twse_max","market_otc_close","market_otc_max"]
    def gavg(k):
        v = [r[k] for r in agg if r[k] is not None]
        return round(float(np.mean(v)),2) if v else None
    summary = {"updated": pd.Timestamp.now("UTC").isoformat(), "latest_date": latest, "n_weeks": len(agg),
               "weeks": agg, "detail": detail, "avg": {k: gavg(k) for k in keys}}
    json.dump(summary, open(os.path.join(ROOT,"data","performance.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    ns = sum(1 for r in agg if r["status"]=="settled")
    print(f"{len(agg)}週 (預測中{len(agg)-ns}/已結束{ns}). 平均收盤 我們{summary['avg']['our_close']} 猴子{summary['avg']['monkey_close']} 大盤上市{summary['avg']['market_twse_close']}/上櫃{summary['avg']['market_otc_close']}", flush=True)

if __name__ == "__main__":
    main()
