# 台灣汽機車日報

這是 GitHub Pages 靜態新聞索引，展示台灣汽車、機車、交通法規相關 RSS 新聞，點擊前往原始新聞網站。

## 安裝

1. 在 GitHub 建立公開 repository，將此資料夾的內容上傳到 repository 根目錄（包含 `.github/workflows/update-news.yml` 隱藏資料夾）。
2. 進入 repository > Settings > Pages > Build and deployment > Source，選擇 **GitHub Actions**。
3. 開啟 repository > Actions > **更新新聞並發布網站** > Run workflow；首次執行可能需要先啟用 Actions。
4. 成功後，網址是 `https://你的帳號.github.io/你的倉庫名稱/`。如果 repo 名稱為 `你的帳號.github.io`，網址會是 `https://你的帳號.github.io/`。
5. 之後 GitHub Actions 每 6 小時執行一次。因排程限制，可能延遲。你也能隨時手動執行。

## 程式運作

- `index.html`：網頁畫面（含 CSS 與 JavaScript）。
- `scripts/update_news.py`：抓取新聞 RSS；以標題過濾分類，補上該篇文章的 RSS 圖或 Open Graph 封面圖，寫入 `news.json`。
- `requirements.txt`：Python 依賴套件。
- `.github/workflows/update-news.yml`：抓取新聞、建立網站並直接部署 GitHub Pages。**不要改成從 branch 發布**。

## 注意

- GitHub Actions 執行需要外網能正常存取 RSS。資料來源若阻擋爬取、變更 RSS 或限制圖片外連，個別新聞可能缺少；網頁會顯示分類示意圖。若本次完全沒取得新聞，工作流程會失敗，既有網站不會被覆蓋。
- 文章圖片均來自該篇 RSS 或原始新聞頁面的圖片中繼資料；不從任意相似車款的網路圖片代替。圖片使用及引用方式需遵守新聞原網站著作權與服務條款，尤其是商業用途。
- 交通規定更新時，RSS 僅提供新聞資訊，**不表示已正式生效**。請以主管機關原始公告為準。
- 本範例每則只顯示標題、來源、發布日期、簡短摘要並連結原文，不轉載全文。
