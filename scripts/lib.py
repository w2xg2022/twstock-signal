# -*- coding: utf-8 -*-
"""共用：股票清單、抓價、指標、V1篩選、alpha、營收加速"""
import os, io, time, requests
import numpy as np, pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVDIR = os.path.join(ROOT, "data", "revenue")
FINMIND = "https://api.finmindtrade.com/api/v4/data"
TOKEN = os.getenv("FINMIND_TOKEN", "")  # GitHub Secret; 沒有就用匿名

def load_stock_list():
    """上市(t187ap03_L)+上櫃(t187ap03_O) -> DataFrame[code,name,market('TWSE'/'OTC'),ticker]"""
    out = []
    for url, mk, sfx in [("https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv", "TWSE", ".TW"),
                         ("https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv", "OTC", ".TWO")]:
        r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        for enc in ("utf-8-sig", "big5", "utf-8"):
            try: d = pd.read_csv(io.StringIO(r.content.decode(enc))); break
            except Exception: continue
        cc = [c for c in d.columns if "代號" in c][0]; nc = [c for c in d.columns if "名稱" in c][0]
        for _, row in d.iterrows():
            code = str(row[cc]).strip()
            if code.isdigit() and len(code) == 4:
                out.append(dict(code=code, name=str(row[nc]).strip(), market=mk, ticker=code + sfx))
    return pd.DataFrame(out).drop_duplicates("code").reset_index(drop=True)

def fetch_prices(tickers, start="2014-01-01"):
    """批次抓還原OHLCV -> {ticker: DataFrame[date,Open,High,Low,Close,Volume]}"""
    res = {}
    for i in range(0, len(tickers), 80):
        chunk = tickers[i:i+80]
        try:
            data = yf.download(chunk, start=start, auto_adjust=True, group_by="ticker",
                               threads=True, progress=False)
        except Exception:
            time.sleep(3); continue
        for t in chunk:
            try:
                df = data if len(chunk) == 1 else data[t]
                df = df[["Open","High","Low","Close","Volume"]].dropna()
                if len(df) >= 260:
                    df = df.reset_index(); df.columns = ["date","Open","High","Low","Close","Volume"]
                    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
                    res[t] = df
            except Exception: pass
        time.sleep(1)
    return res

IDXDIR = os.path.join(ROOT, "data", "index")

def fetch_index(data_id, start="2014-01-01"):
    """抓大盤指數；成功則更新快取 data/index/<id>.csv，失敗則用快取 fallback（對限流/FinMind當機穩健）"""
    cache = os.path.join(IDXDIR, f"{data_id}.csv")
    for use_tok in ([True, False] if TOKEN else [False]):
        p = dict(dataset="TaiwanStockTotalReturnIndex", data_id=data_id, start_date=start)
        if use_tok: p["token"] = TOKEN
        try:
            j = requests.get(FINMIND, params=p, timeout=60).json()
            if j.get("status") == 200 and j.get("data"):
                d = pd.DataFrame(j["data"])
                v = [c for c in d.columns if c not in ("date","stock_id") and pd.api.types.is_numeric_dtype(d[c])][0]
                out = d[["date", v]].rename(columns={v: "idx"})
                os.makedirs(IDXDIR, exist_ok=True); out.to_csv(cache, index=False)
                return out
        except Exception: pass
    if os.path.exists(cache):
        print(f"  指數 {data_id} 抓取失敗，改用快取", flush=True)
        return pd.read_csv(cache)
    return pd.DataFrame(columns=["date","idx"])

def rev_accel_map():
    """讀 data/revenue 快取 -> {code: (announce_dates[], accel[])}, accel=YoY - 過去12月YoY均, winsorize"""
    clip = lambda x, a, b: max(a, min(b, x))
    out = {}
    if not os.path.isdir(REVDIR): return out
    for f in os.listdir(REVDIR):
        if not f.endswith(".csv"): continue
        code = f[:-4]
        try: g = pd.read_csv(os.path.join(REVDIR, f))
        except Exception: continue
        if g.empty or "revenue" not in g: continue
        g["ym"] = g["revenue_year"]*12 + g["revenue_month"]
        g = g.sort_values("ym").drop_duplicates("ym")
        ym = g["ym"].values; rv = g["revenue"].values.astype(float); yoy = {}
        for i in range(len(ym)):
            j = np.where(ym == ym[i]-12)[0]
            if len(j) and rv[j[0]] > 0: yoy[ym[i]] = clip(rv[i]/rv[j[0]]-1, -0.8, 3.0)
        ad = []; av = []
        for k in sorted(yoy):
            prev = [yoy[k-1-p] for p in range(12) if (k-1-p) in yoy]
            if len(prev) < 6: continue
            y = k//12; mo = k % 12 or 12; y2 = y + (mo == 12); m2 = (mo % 12) + 1
            ad.append(f"{y2:04d}-{m2:02d}-10"); av.append(clip(yoy[k]-np.mean(prev), -1.5, 1.5))
        if ad: out[code] = (np.array(ad), np.array(av))
    return out

def compute_features(df, idx_df):
    """回傳 DataFrame(index對齊df) 含 v1, alpha120, d240h; 需 idx_df[date,idx]"""
    g = df.merge(idx_df, on="date", how="left"); g["idx"] = g["idx"].ffill()
    C = g["Close"].values.astype(float); H = g["High"].values.astype(float); L = g["Low"].values.astype(float)
    IX = g["idx"].values.astype(float); c = pd.Series(C); s = c.pct_change(); m = pd.Series(IX).pct_change()
    m5 = c.rolling(5).mean().values; m10 = c.rolling(10).mean().values; m20 = c.rolling(20).mean().values
    v1 = (m5 > m10) & (m10 > m20) & (np.r_[False, m20[1:] > m20[:-1]]) & (C > m5)
    b120 = s.rolling(120).cov(m) / m.rolling(120).var()
    a120 = ((s.rolling(120).mean() - b120 * m.rolling(120).mean()) * 252).values
    d240h = (C / c.rolling(240).max().values - 1)
    ext = C / m20 - 1  # 收盤離MA20（過度延伸=追高風險）
    return pd.DataFrame(dict(date=g["date"].values, Close=C, High=H, Low=L, idx=IX,
                             v1=v1, alpha120=a120, beta120=b120.values, d240h=d240h, ext=ext))
