# -*- coding: utf-8 -*-
"""共用：股票清單、抓價、指標、V1篩選、alpha、營收加速"""
import os, io, time, requests
import numpy as np, pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVDIR = os.path.join(ROOT, "data", "revenue")
FINMIND = "https://api.finmindtrade.com/api/v4/data"
TOKEN = os.getenv("FINMIND_TOKEN", "")  # GitHub Secret; 沒有就用匿名

STOCK_LIST_CSV = os.path.join(ROOT, "data", "stock_list.csv")

def _cached_stock_list():
    if os.path.exists(STOCK_LIST_CSV):
        try: return pd.read_csv(STOCK_LIST_CSV, dtype={"code": str})
        except Exception: pass
    return pd.DataFrame(columns=["code", "name", "market", "ticker"])

def _fetch_market(url, mk, sfx):
    """抓單一市場清單；失敗或空回傳空 list"""
    try:
        r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        d = None
        for enc in ("utf-8-sig", "big5", "utf-8"):
            try: d = pd.read_csv(io.StringIO(r.content.decode(enc))); break
            except Exception: d = None
        if d is None: return []
        cc = [c for c in d.columns if "代號" in c][0]; nc = [c for c in d.columns if "名稱" in c][0]
        out = []
        for _, row in d.iterrows():
            code = str(row[cc]).strip()
            if code.isdigit() and len(code) == 4:
                out.append(dict(code=code, name=str(row[nc]).strip(), market=mk, ticker=code + sfx))
        return out
    except Exception:
        return []

def load_stock_list():
    """上市(t187ap03_L)+上櫃(t187ap03_O) -> DataFrame[code,name,market('TWSE'/'OTC'),ticker]
    逐市場抓 MOPS opendata；抓不到或回傳空的，就用 data/stock_list.csv 舊清單頂替(不讓整批清空)，
    成功則把最新清單寫回快取。"""
    cached = _cached_stock_list()
    frames = []
    for url, mk, sfx in [("https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv", "TWSE", ".TW"),
                         ("https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv", "OTC", ".TWO")]:
        rows = _fetch_market(url, mk, sfx)
        if rows:
            frames.append(pd.DataFrame(rows))
        else:
            old = cached[cached["market"] == mk]
            print(f"  {mk} 清單抓取失敗/空，改用舊清單 {len(old)} 檔", flush=True)
            frames.append(old)
    out = pd.concat(frames, ignore_index=True).drop_duplicates("code").reset_index(drop=True)
    if not out.empty:
        try:
            os.makedirs(os.path.dirname(STOCK_LIST_CSV), exist_ok=True)
            out.to_csv(STOCK_LIST_CSV, index=False, encoding="utf-8-sig")
        except Exception: pass
    return out

def fetch_prices(tickers, start="2014-01-01"):
    """批次抓 OHLCV：同時保留原始價(High/Low/Close 給顯示)與還原價(aHigh/aLow/aClose 給指標與報酬)
    -> {ticker: DataFrame[date,Open,High,Low,Close,aHigh,aLow,aClose,Volume]}"""
    res = {}
    for i in range(0, len(tickers), 80):
        chunk = tickers[i:i+80]
        try:
            data = yf.download(chunk, start=start, auto_adjust=False, group_by="ticker",
                               threads=True, progress=False)
        except Exception:
            time.sleep(3); continue
        multi = isinstance(data.columns, pd.MultiIndex)
        for t in chunk:
            try:
                df = data[t] if multi else data
                df = df[["Open","High","Low","Close","Adj Close","Volume"]].dropna()
                if len(df) < 260: continue
                df = df.reset_index(); df.columns = ["date","Open","High","Low","Close","AdjClose","Volume"]
                df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
                ratio = df["AdjClose"] / df["Close"].replace(0, np.nan)   # 還原/原始 比例
                df["aClose"] = df["AdjClose"]; df["aHigh"] = df["High"]*ratio; df["aLow"] = df["Low"]*ratio
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
    """技術指標一律用還原價(aClose/aHigh/aLow)計算；回傳 Close=原始收盤(顯示用)。需 idx_df[date,idx]"""
    g = df.merge(idx_df, on="date", how="left"); g["idx"] = g["idx"].ffill()
    aC = g["aClose"].values.astype(float)  # 還原收盤(指標用)
    rawC = g["Close"].values.astype(float)  # 原始收盤(顯示用)
    IX = g["idx"].values.astype(float); c = pd.Series(aC); s = c.pct_change(); m = pd.Series(IX).pct_change()
    m5 = c.rolling(5).mean().values; m10 = c.rolling(10).mean().values; m20 = c.rolling(20).mean().values
    v1 = (m5 > m10) & (m10 > m20) & (np.r_[False, m20[1:] > m20[:-1]]) & (aC > m5)
    b120 = s.rolling(120).cov(m) / m.rolling(120).var()
    a120 = ((s.rolling(120).mean() - b120 * m.rolling(120).mean()) * 252).values
    d240h = (aC / c.rolling(240).max().values - 1)
    ext = aC / m20 - 1
    return pd.DataFrame(dict(date=g["date"].values, Close=rawC, v1=v1, alpha120=a120,
                             beta120=b120.values, d240h=d240h, ext=ext))
