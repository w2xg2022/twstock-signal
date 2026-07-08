# twstock-signal 🧑‍💻 vs 🐒

台股（上市＋上櫃）**每週訊號選股**，每週同時和一隻**選股猴子對戰**，並累積一份**真實的樣本外成績單**。

> 🐒 **猴子選股**：每週從全市場隨機挑 5 檔（以當週日期為種子，可重現、不可事後竄改）。典故來自經濟學家 Burton Malkiel《漫步華爾街》的著名假設——「一隻蒙眼的猴子對著報紙股票版射飛鏢選出的組合，表現未必輸給專家精挑細選」。
> **我們的策略若長期贏不過這隻猴子，就沒有存在的價值。** 這是最誠實的檢驗。

線上查詢：**[https://w2xg2022.github.io/twstock-signal/](https://w2xg2022.github.io/twstock-signal/)**

每週推薦 CSV：**[Releases](https://github.com/w2xg2022/twstock-signal/releases)**

## 策略（131 個月全量回測定案）

三段式：**趨勢過濾 → 風險過濾 → 因子排序 → 取前 5 檔**。

1. **多頭排列篩選**：`MA5 > MA10 > MA20` 且 `MA20 向上` 且 `收盤站上 MA5`
2. **beta120 濾網**：只留 `beta120 ∈ [0, 1]`（波動不高於大盤，控制集中組合的變異）
3. **alpha120 排序**：`alpha120`（120 日對大盤的滾動 OLS 超額報酬 × 252，風險調整後的相對強勢），由高到低取 **前 5 名**

- **入場價**：推薦後**下一個交易日的 (最高＋最低)/2**（多頭排列可能在當週任何一天出現）
- **出場**：進場後**第 15～20 個交易日的均價（TWAP）**——約一個月跑完一輪，且用區間均價去除單日雜訊（回測顯示比單押某一天報酬更高、更顯著）
- **基準**：一律對同期大盤（上市對 TAIEX、上櫃對 TPEx，FinMind 指數）計算超額報酬

> 回測（131 月、全量、扣成本）：top5 × β[0,1] 超越大盤約 **+2.2%/月（t≈2.4）**、贏「隨機選股（猴子）」約 +2.6%。
> 註：檔數越少 beta 濾網要越緊——若改推 3 檔，用 `beta120 ∈ [0, 0.5]`。

## 誠實揭露（重要）

- 這是**正偏態策略**：勝率約 45～50%（靠少數大贏股拉抬），**必須分散、長期執行**，單押必被變異吃掉。
- **急跌後的暴力反彈期，動能因子會逆風**（策略偏趨勢，追不上junk beta反彈）。
- 回測含樂觀成分（集中持股、樣本內）；本倉庫的 `docs/` 績效頁記錄的是**上線後累積的真實樣本外成績**，以那個為準。
- **僅供研究參考，不構成投資建議。**

## 資料來源
- 價格：yfinance（`auto_adjust=True` 還原價），每次執行即時抓取
- 月營收：FinMind `TaiwanStockMonthRevenue`，快取於 `data/revenue/`，每月增量更新
- 大盤指數：FinMind `TaiwanStockTotalReturnIndex`（TAIEX／TPEx）

## 目錄結構
```
scripts/
  lib.py            共用：抓價、指標、V1、alpha、營收
  generate_picks.py 產生本週推薦 -> data/picks/YYYY-MM-DD.csv
  track_perf.py     歷史推薦 + 最新價 -> data/performance.json（樣本外成績單）
  update_revenue.py FinMind 增量更新營收快取
data/
  revenue/<code>.csv  月營收快取
  picks/YYYY-MM-DD.csv 每週推薦存檔
  performance.json     累積績效
docs/                 GitHub Pages（本週名單＋績效曲線）
.github/workflows/
  weekly.yml          每週末：抓/算/追蹤/commit/Release
  pages.yml           自動部署 Pages
```

## 免責聲明
本倉庫資料與推薦僅供研究與學習，不構成任何投資建議。資料與計算可能有誤差或延遲，使用者應自行核實並承擔風險。
