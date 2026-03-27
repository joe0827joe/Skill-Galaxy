# 🌌 Skill Galaxy AI (104 技術銀河分析系統)

> **探索職場銀河，定位您的核心星系。** 這不僅是一個 104 職缺爬取器，更是一個具備 **RAG (檢索增強生成)** 與 **物理解析星圖** 的高端技術情報中樞。

---

## 💎 核心旗艦功能

### 1. 🌌 物理解析星雲地圖 (Physics Topology)
- **核心錨定佈局 (Anchor Core)**：自動識別市場熱度最高技術並鎖定於中心，建立穩定的視覺記憶地圖。
- **高對比顯影 (Ultra-Visibility)**：32px+ 巨量標籤配合 8px 黑邊描邊，確保在任何縮放比例下文字皆清晰可見。
- **力導向規律 (Stable Seed)**：採用固定物理隨機種子，確保每次重新整理時技術位置保持一致。

### 2. 🧠 異步「懶加載」智慧 (Lazy-Intelligence)
- **疾速渲染**：地圖與排行榜瞬間開啟，AI 語意分析在背景按需生成，完全不卡頓。
- **一鍵職場概覽**：點擊任何技術球體，即刻從 AI 腦中提取該技術在當前職場的具體定位。

### 3. 🌐 全球 RAG 深度檢索 (Research Mode)
- **實時網絡衛星**：整合 Google Custom Search API 與 DuckDuckGo (備援)，即時抓取全球最新技術趨勢。
- **AI 情資報告**：自動將網頁數據轉化為結構化的 Markdown 專業報告，涵蓋技術定義與職涯建議。

### 4. 📂 多任務情據管理 (Task Manager)
- **獨立時空**：每個採集任務皆擁有獨立的 SQLite 資料庫與分析環境。
- **視覺控制台**：直覺化的任務切換按鈕，支援在「戰情室」與「地圖」之間原位跳轉。

---

## 🛠️ 技術架構

- **Backend**: Python 3.x (Flask) + SQLite3
- **Frontend**: Vanilla JS + Vis.js Network Engine + CSS Glassmorphism
- **AI Core**: LangChain + OpenAI (GPT-4o mini)
- **Intelligence Bridge**: Google Custom Search JSON API / DuckDuckGo Scraping

---

## 🚀 快速啟動

### 1. 安裝環境
```bash
pip install -r requirements.txt
```

### 2. 啟動引擎
```bash
python app.py
```

### 3. 配置情報金鑰
進入首頁，在「系統設定組件」填入您的：
- **OpenAI API Key**: 用於語意分析與報告生成。
- **Google Search Key / CX**: 用於啟動官方高速 RAG 檢索。

---

## ⚖️ 免責聲明 (Disclaimer & Responsible Use)

本專案係基於 **「技術研究」** 與 **「學術交流」** 目的開發，開源前請務必瞭解以下核心要點：

1.  **非官方工具**：本系統與 104 官方無任何隸屬關係，其數據採集邏輯僅供個人學習與研究使用。
2.  **遵守規範**：使用者應自覺遵守 104 網站之 `robots.txt` 與相關使用條款。**嚴禁將本工具用於大規模採集、商業性質銷售或任何可能違反法律之用途。**
3.  **無擔保責任**：依據 **MIT License**，本軟體按「原樣」提供，作者不對任何因使用、修改、分發本軟體所產生的損失、糾紛或賠償承擔任何法律責任。
4.  **數據資安**：請妥善保管本地存儲的 API Key 與資料庫，建議使用 `.gitignore` 排除所有數據存儲目錄。