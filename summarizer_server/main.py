from flask import Flask, request, jsonify
import logging
import base64
import os
import utils
import summarizer
import requests
import datetime

# Configure basic logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Configuration & Constants ---
SERVER_DIR = os.path.dirname(__file__)
API_KEY_FILE = os.path.join(SERVER_DIR, "api_key.txt")
PROMPT_CONFIG_FILE = os.path.join(SERVER_DIR, "prompt_config.yaml")
LOGS_DIR = os.path.abspath(os.path.join(SERVER_DIR, "logs"))
REF_AUDIO_PATH = os.path.abspath(os.path.join(SERVER_DIR, "ref_audio.wav"))

# Ensure logs directory exists
os.makedirs(LOGS_DIR, exist_ok=True)

# --- Helper Function for Logging ---
def log_request_data(timestamp_str, url, web_text, summary, audio_content):
    """Logs request details into a timestamped directory."""
    try:
        request_log_dir = os.path.join(LOGS_DIR, timestamp_str)
        os.makedirs(request_log_dir, exist_ok=True)

        # Log URL along with web content
        with open(os.path.join(request_log_dir, "web_content.txt"), "w", encoding="utf-8") as f:
            f.write(f"URL: {url}\n\n")
            f.write(web_text)
        logger.info(f"Logged web content to {request_log_dir}/web_content.txt")

        with open(os.path.join(request_log_dir, "summary.txt"), "w", encoding="utf-8") as f:
            f.write(summary)
        logger.info(f"Logged summary to {request_log_dir}/summary.txt")

        with open(os.path.join(request_log_dir, "output.wav"), "wb") as f:
            f.write(audio_content)
        logger.info(f"Logged audio to {request_log_dir}/output.wav")

    except Exception as e:
        logger.error(f"Failed to log request data for {timestamp_str}: {e}", exc_info=True)


# --- API Endpoint ---
@app.route('/summarize', methods=['POST'])
def summarize_endpoint():
    """
    API endpoint to receive a URL, summarize it, get TTS audio,
    and return summary text and audio data.
    Expects JSON payload: {"url": "...", "summarizer_choice": "gemini" | "openrouter"}
    Returns JSON payload: {"summary_text": "...", "audio_base64": "..."} or {"error": "..."}
    """
    if not request.is_json:
        logger.warning("Received non-JSON request")
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    url_from_request = data.get('url')
    rss_url_from_request = data.get('rss_url')
    summarizer_choice = data.get('summarizer_choice', 'gemini') # Default to gemini

    if not url_from_request and not rss_url_from_request:
        logger.warning("Missing 'url' or 'rss_url' in request data")
        return jsonify({"error": "Request must contain either 'url' or 'rss_url'"}), 400

    # Determine the target URL to fetch content from
    target_url = None
    source_type = None
    if rss_url_from_request:
        source_type = "RSS"
        target_url = utils.get_latest_article_url_from_rss(rss_url_from_request)
        if not target_url:
            logger.error(f"Could not get article URL from RSS feed: {rss_url_from_request}")
            return jsonify({"error": f"Could not retrieve article from RSS feed: {rss_url_from_request}"}), 400
    else:
        source_type = "Direct URL"
        target_url = url_from_request

    # Generate timestamp for logging: YYYYMMDD_HHMMSS_ms
    now = datetime.datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S") + f"_{now.microsecond // 1000:03d}"

    logger.info(f"Request ID [{timestamp_str}]: Processing {source_type}: {target_url} (from {rss_url_from_request or url_from_request}) with summarizer: {summarizer_choice}")

    try:
        # 1. Read configurations
        api_key = utils.read_api_key(filepath=API_KEY_FILE, key_type=summarizer_choice)
        system_prompt, user_prompt_template = utils.read_prompt_config(filepath=PROMPT_CONFIG_FILE)

        # 2. Get webpage text from the target URL
        web_text = utils.get_webpage_text(target_url)
        if not web_text:
            logger.warning(f"Request ID [{timestamp_str}]: No text extracted from {target_url}, returning error.")
            return jsonify({"error": f"Could not extract text content from the target URL: {target_url}"}), 400

        # 3. Summarize text
        summary = ""
        if summarizer_choice == "gemini":
            summary = summarizer.summarize_text_with_gemini(web_text, api_key, system_prompt, user_prompt_template)
        elif summarizer_choice == "openrouter":
            summary = summarizer.summarize_text_with_openrouter(web_text, api_key, system_prompt, user_prompt_template)
        else:
            logger.error(f"Request ID [{timestamp_str}]: Invalid summarizer choice: {summarizer_choice}")
            return jsonify({"error": f"Invalid summarizer choice: {summarizer_choice}"}), 400

        logger.info(f"Request ID [{timestamp_str}]: Generated Summary ({summarizer_choice}): {summary[:100]}...")

        # 4. Call voice API
        effective_ref_audio_path = REF_AUDIO_PATH if os.path.exists(REF_AUDIO_PATH) else None
        audio_content = utils.call_voice_api(summary, ref_audio_path=effective_ref_audio_path)

        # 5. Log data (web text, summary, audio) - Log the original source URL/RSS
        log_request_data(timestamp_str, rss_url_from_request or url_from_request, web_text, summary, audio_content)

        # 6. Encode audio data as Base64
        audio_base64 = base64.b64encode(audio_content).decode('utf-8')
        logger.info(f"Request ID [{timestamp_str}]: Encoded audio to Base64")

        # 7. Return summary text and Base64 encoded audio
        return jsonify({
            "summary_text": summary,
            "audio_base64": audio_base64
        })

    except FileNotFoundError as e:
         logger.error(f"Request ID [{timestamp_str}]: Configuration file not found: {e}", exc_info=True)
         return jsonify({"error": f"Server configuration error: {e}"}), 500
    except ValueError as e: # Catch API key errors or Gemini blocks etc.
         logger.error(f"Request ID [{timestamp_str}]: Value error during processing: {e}", exc_info=True)
         return jsonify({"error": f"Processing error: {e}"}), 500
    except requests.exceptions.RequestException as e:
         logger.error(f"Request ID [{timestamp_str}]: API request failed: {e}", exc_info=True)
         return jsonify({"error": f"Failed to communicate with an external API: {e}"}), 502 # Bad Gateway
    except Exception as e:
        logger.error(f"Request ID [{timestamp_str}]: An unexpected error occurred: {e}", exc_info=True) # Use error level
        return jsonify({"error": "An internal server error occurred"}), 500

@app.route('/config/rss_feeds', methods=['GET'])
def get_rss_feeds_config():
    """API endpoint to return the configured list of RSS feeds."""
    try:
        feeds = utils.read_rss_feeds_config(filepath=PROMPT_CONFIG_FILE)
        return jsonify({"rss_feeds": feeds})
    except Exception as e:
        logger.error(f"Error reading RSS feed config: {e}", exc_info=True)
        return jsonify({"error": "Failed to read RSS feed configuration"}), 500

if __name__ == '__main__':
    # Note: For development only. Use a proper WSGI server like Gunicorn in production.
    # Run from the project root using: flask --app summarizer_server/main run
    logger.info("Starting Flask development server via __main__ (use 'flask run' for better practice)...")
    # Make sure api_key.txt, prompt_config.yaml, and ref_audio.wav are in the same directory
    app.run(debug=True, port=5000) # Runs on http://127.0.0.1:5000