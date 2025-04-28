# 網頁語音摘要 (Webpage Audio Summarizer)

本專案旨在提供一個工具，讓使用者在瀏覽網頁時，能夠快速獲取該網頁內容的 AI 摘要，並以語音形式播放出來。

## 架構 (Architecture)

本專案包含兩個主要部分：

1.  **後端摘要伺服器 (Backend Summarizer Server)**：
    *   一個運行在本地的 Python Flask 伺服器 (`summarizer_server/`)。
    *   負責接收來自瀏覽器擴充功能的 URL。
    *   使用 `trafilatura` 提取網頁主要內容。
    *   呼叫 LLM API (目前支援 Google Gemini 和 OpenRouter) 產生摘要。
    *   呼叫本地的 TTS (文字轉語音) API (預設 `http://127.0.0.1:9880/tts`) 將摘要轉換為音訊。
    *   將音訊數據 (Base64 編碼) 回傳給瀏覽器擴充功能。
2.  **瀏覽器擴充功能 (Browser Extension)**：
    *   一個適用於 Chrome/Brave 等 Chromium 核心瀏覽器的擴充功能 (`extension/`)。
    *   在瀏覽器工具列提供一個按鈕。
    *   點擊按鈕時，獲取當前分頁的 URL。
    *   將 URL 發送給本地的後端摘要伺服器。
    *   接收伺服器回傳的 Base64 音訊數據。
    *   使用 Web Audio API 解碼並播放音訊。

## 設定 (Setup)

### 1. 後端伺服器 (Backend Server)

*   **需求 (Requirements)**：
    *   Python 3.8+
    *   一個本地運行的 TTS API (例如，您提供的位於 `http://127.0.0.1:9880/tts` 的 API)。
    *   Google API Key (用於 Gemini) 或 OpenRouter API Key。
*   **步驟 (Steps)**：
    1.  **克隆/下載專案 (Clone/Download)**：取得本專案的檔案。
    2.  **建立虛擬環境 (Create Virtual Environment)**：
        ```bash
        python -m venv venv
        # Windows
        venv\Scripts\activate
        # macOS/Linux
        source venv/bin/activate
        ```
    3.  **安裝依賴 (Install Dependencies)**：
        ```bash
        pip install -r requirements.txt
        ```
    4.  **設定 API 金鑰 (Configure API Key)**：
        *   在 `summarizer_server/` 資料夾內建立 `api_key.txt` 檔案。
        *   根據您打算使用的 LLM，將 LLM API Key 貼入此檔案。
    5.  **設定 Prompt (Configure Prompts)**：
        *   (可選) 編輯 `summarizer_server/prompt_config.yaml` 來調整 System Prompt 和 User Prompt Template。
    6.  **設定參考音訊 (Configure Reference Audio)**：
        *   確保 `ref_audio.wav` 檔案位於專案根目錄下 (與 `summarizer_server` 同級)。
    7.  **選擇 LLM (Choose LLM)**：
        *   (可選) 編輯 `extension/background.js` 中 `fetch` 請求的 `body` 來改變預設使用的 LLM ('gemini' 或 'openrouter')。請確保 `api_key.txt` 中的金鑰與所選 LLM 對應。
    8.  **啟動伺服器 (Run the Server)**：
        *   確保您的本地 TTS API 正在運行。
        *   在專案根目錄 (`llm_tts`) 下執行：
          ```bash
          python summarizer_server/main.py

          # OR
          # 設定 Flask App 環境變數
          # Windows (cmd)
          set FLASK_APP=summarizer_server.main
          # Windows (PowerShell)
          $env:FLASK_APP = "summarizer_server.main"
          # macOS/Linux
          export FLASK_APP=summarizer_server.main

          # 啟動伺服器 (預設運行在 http://127.0.0.1:5000)
          flask --app summarizer_server/main run
          ```
        *   您應該會看到伺服器啟動的訊息。保持此終端機視窗開啟。

### 2. 瀏覽器擴充功能 (Browser Extension)

*   **需求 (Requirements)**：
    *   Chrome, Brave, Edge 或其他支援 Manifest V3 的 Chromium 核心瀏覽器。
*   **步驟 (Steps)**：
    1.  **準備圖示 (Prepare Icons)**：在 `extension/icons/` 資料夾中放入 `icon16.png`, `icon48.png`, `icon128.png` 圖示檔案。如果您沒有圖示，擴充功能可以無法安裝。
    2.  **打開擴充功能管理頁面 (Open Extensions Page)**：
        *   在瀏覽器中輸入 `chrome://extensions` (Chrome) 或 `brave://extensions` (Brave) 或類似地址。
    3.  **啟用開發人員模式 (Enable Developer Mode)**：
        *   通常在頁面的右上角有一個切換開關。
    4.  **載入未封裝項目 (Load Unpacked)**：
        *   點擊「載入未封裝項目」或類似按鈕。
        *   在彈出的檔案選擇器中，選擇包含 `manifest.json` 的 **`extension` 資料夾** (不是裡面的檔案，是整個資料夾)。
    5.  **完成 (Done)**：您應該會在擴充功能列表中看到「網頁語音摘要」，並且在瀏覽器工具列上看到它的圖示。如果載入時出現錯誤，請檢查 `manifest.json` 是否有語法錯誤。

## 使用方式 (Usage)

1.  確保您的本地 TTS API 正在運行。
2.  確保後端摘要伺服器 (`flask run`) 正在運行。
3.  瀏覽任何您想摘要的網頁 (確保是 `http` 或 `https` 開頭的網址)。
4.  點擊瀏覽器工具列上的「網頁語音摘要」圖示 (圖示下方可能會短暫顯示 "..." 表示處理中)。
5.  稍等片刻，您應該會聽到該網頁的語音摘要。如果過程中發生錯誤，擴充功能會嘗試顯示通知。

## 注意事項 (Notes)

*   目前的錯誤處理還比較基礎。
*   音訊播放直接使用 Web Audio API，格式依賴於您的 TTS API 輸出的格式 (目前假設是 WAV)。如果播放失敗，可能是格式不相容。
*   LLM 模型名稱和設定可以在 `summarizer_server/summarizer.py` 中調整。
*   伺服器預設運行在 `http://127.0.0.1:5000`，如果修改，需要同時更新 `extension/background.js` 中的 `SERVER_URL`。
*   第一次點擊擴充功能圖示後，瀏覽器可能會要求授權 AudioContext 運行，您可能需要再次點擊才能播放聲音。