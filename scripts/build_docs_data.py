# -*- coding: utf-8 -*-
"""複製 performance.json 到 docs/data/ 供 Pages 使用"""
import os, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs", "data"); os.makedirs(DOCS, exist_ok=True)
src = os.path.join(ROOT, "data", "performance.json")
if os.path.exists(src):
    shutil.copy(src, os.path.join(DOCS, "performance.json"))
    print("docs 資料已更新", flush=True)
