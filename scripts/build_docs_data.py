# -*- coding: utf-8 -*-
"""把最新推薦 + 績效整理成 docs/data/*.json 供 Pages 使用"""
import os, sys, json, glob, shutil
import pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs", "data"); os.makedirs(DOCS, exist_ok=True)

files = sorted(glob.glob(os.path.join(ROOT, "data", "picks", "*.csv")))
if files:
    d = pd.read_csv(files[-1], dtype={"code": str})
    top = d[d["rank"] <= 5].to_dict(orient="records")
    json.dump({"pick_date": str(d["pick_date"].iloc[0]), "n_v1": int(len(d)), "top": top},
              open(os.path.join(DOCS, "latest_picks.json"), "w", encoding="utf-8"), ensure_ascii=False)

perf = os.path.join(ROOT, "data", "performance.json")
if os.path.exists(perf):
    shutil.copy(perf, os.path.join(DOCS, "performance.json"))
print("docs 資料已更新", flush=True)
