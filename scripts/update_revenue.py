# -*- coding: utf-8 -*-
"""FinMind 增量更新月營收快取 data/revenue/<code>.csv
只補「最新月份已過期」的股票；token+匿名輪流；碰持續限流就結束（下次再續）。"""
import os, sys, time, requests, datetime as dt
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

TOKEN = lib.TOKEN
def latest_ym(code):
    fp = os.path.join(lib.REVDIR, f"{code}.csv")
    if not os.path.exists(fp): return 0
    try:
        g = pd.read_csv(fp)
        return int((g["revenue_year"]*12 + g["revenue_month"]).max()) if len(g) else 0
    except Exception: return 0

def fetch(code, use_tok):
    p = dict(dataset="TaiwanStockMonthRevenue", data_id=code, start_date="2014-01-01")
    if use_tok: p["token"] = TOKEN
    try:
        j = requests.get(lib.FINMIND, params=p, timeout=30).json()
        return j.get("status"), j.get("data", [])
    except Exception: return None, []

def main():
    os.makedirs(lib.REVDIR, exist_ok=True)
    stocks = lib.load_stock_list()
    now = dt.date.today(); cur_ym = now.year*12 + now.month
    # 只補「快取最新月份 < 上個月」的（表示有新營收可抓）；全新的也補
    todo = [r.code for r in stocks.itertuples() if latest_ym(r.code) < cur_ym - 1]
    print(f"需更新營收 {len(todo)} 檔", flush=True)
    ok = fail = 0
    for i, code in enumerate(todo):
        st, data = fetch(code, TOKEN and i % 2 == 0)
        if st != 200:
            st, data = fetch(code, not (TOKEN and i % 2 == 0))
        if st == 200:
            fail = 0
            if data:
                pd.DataFrame(data)[["date","stock_id","revenue","revenue_year","revenue_month"]] \
                    .to_csv(os.path.join(lib.REVDIR, f"{code}.csv"), index=False)
            ok += 1
        else:
            fail += 1
            if fail >= 4:
                print(f"持續限流，本輪補了{ok}檔，剩下下次續傳", flush=True); break
            time.sleep(8)
        time.sleep(0.25)
    print(f"本輪營收更新完成 {ok} 檔", flush=True)

if __name__ == "__main__":
    main()
