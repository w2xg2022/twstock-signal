# -*- coding: utf-8 -*-
"""整理 docs/data/*.json 供 Pages: latest.json(本週我們vs猴子) + performance.json(歷史對戰)"""
import os, json, glob, shutil
import pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs", "data"); os.makedirs(DOCS, exist_ok=True)

pk = sorted(glob.glob(os.path.join(ROOT, "data", "picks", "*.csv")))
mk = sorted(glob.glob(os.path.join(ROOT, "data", "monkey", "*.csv")))
latest = {}
if pk:
    d = pd.read_csv(pk[-1], dtype={"code": str})
    latest["pick_date"] = str(d["pick_date"].iloc[0])
    latest["our"] = d[d["rank"] <= 5].to_dict(orient="records")
if mk:
    m = pd.read_csv(mk[-1], dtype={"code": str})
    latest["monkey"] = m.to_dict(orient="records")
json.dump(latest, open(os.path.join(DOCS, "latest.json"), "w", encoding="utf-8"), ensure_ascii=False)

perf = os.path.join(ROOT, "data", "performance.json")
if os.path.exists(perf): shutil.copy(perf, os.path.join(DOCS, "performance.json"))
print("docs 資料已更新", flush=True)
