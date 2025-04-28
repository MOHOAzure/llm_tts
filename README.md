# Webpage Audio Summarizer / 網頁語音摘要

This project provides a tool that allows users to quickly obtain an AI-generated summary of the webpage they're viewing — and have it read aloud.

本專案旨在提供一個工具，讓使用者在瀏覽網頁時，能夠快速獲取該網頁內容的 AI 摘要，並以語音形式播放出來。

## Architecture / 架構

The project consists of two main parts:

本專案包含兩個主要部分：

1. **Backend Summarizer Server / 後端摘要伺服器**:
   - A local Python Flask server (`summarizer_server/`).
   - Receives a URL from the browser extension.
   - Extracts the main content from the webpage using `trafilatura`.
   - Calls an LLM API (currently supports Google Gemini and OpenRouter) to generate a summary.
   - Calls a local TTS (Text-to-Speech) API (default: `http://127.0.0.1:9880/tts`) to convert the summary to audio.
   - Returns the audio data (Base64 encoded) to the browser extension.

   - 一個運行在本地的 Python Flask 伺服器 (`summarizer_server/`)。
   - 負責接收來自瀏覽器擴充功能的 URL。
   - 使用 `trafilatura` 提取網頁主要內容。
   - 呼叫 LLM API（目前支援 Google Gemini 和 OpenRouter）產生摘要。
   - 呼叫本地的 TTS (文字轉語音) API（預設為 `http://127.0.0.1:9880/tts`）將摘要轉為音訊。
   - 將音訊數據（Base64 編碼）回傳給瀏覽器擴充功能。

2. **Browser Extension / 瀏覽器擴充功能**:
   - A Chromium extension (for Chrome, Brave, Edge).
   - Adds a toolbar button to the browser.
   - Sends the current tab's URL to the backend summarizer server.
   - Receives the Base64 audio data.
   - Decodes and plays the audio using the Web Audio API.

   - 適用於 Chromium 核心瀏覽器（Chrome、Brave、Edge）的擴充功能。
   - 在瀏覽器工具列添加一個按鈕。
   - 點擊後傳送當前頁面的 URL 到後端摘要伺服器。
   - 接收 Base64 音訊數據。
   - 使用 Web Audio API 解碼並播放音訊。

## Setup / 設定

### 1. Backend Server / 後端伺服器

**Requirements / 需求**:
- Python 3.8+
- A local TTS API (e.g., running at `http://127.0.0.1:9880/tts`).
- Google API Key (for Gemini) or OpenRouter API Key.

**Steps / 步驟**:
1. Clone/Download the project.   克隆/下載本專案。

2. Create a virtual environment.   建立虛擬環境：
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
3. Install dependencies.   安裝依賴：
   ```bash (這裡是註解，不真正結束 code block)
   bash
   pip install -r requirements.txt
   ```

4. Configure API key.   設定 API 金鑰：
   - In `summarizer_server/`, create a file named `api_key.txt`.
   - Paste your LLM API Key inside.

5. Configure prompts (optional). 設定 Prompt（可選）：
   - Edit `summarizer_server/prompt_config.yaml` if you want to adjust System/User Prompts.

6. Configure reference audio. 設定參考音訊：
   - Make sure `ref_audio.wav` is placed in the project root directory.

7. Choose LLM (optional). 選擇 LLM（可選）：
   - Edit `extension/background.js` to set which LLM (`gemini` or `openrouter`) you prefer.

8. Run the server. 啟動伺服器：
   ```bash
   python summarizer_server/main.py
   
   # OR
   set FLASK_APP=summarizer_server.main  # Windows cmd
   $env:FLASK_APP="summarizer_server.main"  # Windows PowerShell
   export FLASK_APP=summarizer_server.main  # macOS/Linux
   flask run
   ```

   You should see the server running at `http://127.0.0.1:5000`.

   您應該會看到伺服器啟動訊息，保持終端機開啟。

### 2. Browser Extension / 瀏覽器擴充功能

**Requirements / 需求**:
- Chrome, Brave, Edge (any Manifest V3-supported browser).

**Steps / 步驟**:
1. Prepare icons. 準備圖示：
   - Place `icon16.png`, `icon48.png`, and `icon128.png` inside `extension/icons/`.

2. Open the extensions page. 打開擴充功能頁面：
   - Enter `chrome://extensions` or `brave://extensions` in your browser.

3. Enable Developer Mode. 啟用開發人員模式。

4. Load unpacked extension. 載入未封裝擴充功能：
   - Select the `extension/` folder.

5. Done! 完成！
   - You should now see the "Webpage Audio Summarizer" icon on your toolbar.

## Usage / 使用方式

1. Ensure your local TTS API is running.

   確保本地 TTS API 已啟動。

2. Ensure the backend server is running.

   確保後端摘要伺服器已啟動。

3. Navigate to any webpage (must start with `http` or `https`).

   瀏覽任何想要摘要的網頁（需以 `http` 或 `https` 開頭）。

4. Click the extension icon.

   點擊擴充功能圖示。

5. Wait a few seconds.

   稍等片刻，即可聽到該網頁的語音摘要。

## Notes / 注意事項

- Error handling is currently basic.

  目前錯誤處理較為基礎。

- Audio playback depends on your TTS output format (currently assumes WAV).

  音訊播放依賴您的 TTS API 輸出格式（目前假設是 WAV）。

- You can adjust model settings in `summarizer_server/summarizer.py`.

  可在 `summarizer_server/summarizer.py` 調整模型設定。

- Server URL defaults to `http://127.0.0.1:5000`, update `extension/background.js` if needed.

  伺服器預設為 `http://127.0.0.1:5000`，若修改，請同步更新 `extension/background.js` 的 `SERVER_URL`。

- First-time AudioContext permission may require a second click.

  第一次授權 AudioContext 時，可能需要再次點擊才能播放。
