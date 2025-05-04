from flask import Flask, request, jsonify
import logging
import base64
import os
import utils
import summarizer
import requests
import datetime
import time
import yaml
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# --- Logging Configuration ---
# Configure basic logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Reduce verbosity of apscheduler and requests/urllib3 logs
logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)
# Get logger for this module
logger = logging.getLogger(__name__)

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Configuration & Constants ---
SERVER_DIR = os.path.dirname(__file__)
API_KEY_FILE = os.path.join(SERVER_DIR, "api_key.txt")
PROMPT_CONFIG_FILE = os.path.join(SERVER_DIR, "prompt_config.yaml")
LOGS_DIR = os.path.abspath(os.path.join(SERVER_DIR, "../logs")) # Logs directory outside server
REF_AUDIO_PATH = os.path.abspath(os.path.join(SERVER_DIR, "../ref_audio.wav"))

# Ensure logs directory exists
os.makedirs(LOGS_DIR, exist_ok=True)

# --- Helper Function for Logging Request Data ---
def log_request_data(timestamp_str, source_identifier, web_text, summary, audio_content):
    """Logs request details into a timestamped directory."""
    try:
        # Sanitize source_identifier for directory name if it's a URL
        dir_name_part = timestamp_str
        if isinstance(source_identifier, str) and ('/' in source_identifier or ':' in source_identifier):
             try:
                  # Attempt to use hostname or a safe part of the URL
                  from urllib.parse import urlparse
                  parsed_url = urlparse(source_identifier)
                  safe_name = parsed_url.hostname or "source"
                  safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in safe_name)
                  dir_name_part = f"{timestamp_str}_{safe_name[:30]}" # Limit length
             except Exception:
                  dir_name_part = f"{timestamp_str}_source" # Fallback

        request_log_dir = os.path.join(LOGS_DIR, dir_name_part)
        os.makedirs(request_log_dir, exist_ok=True)

        with open(os.path.join(request_log_dir, "source.txt"), "w", encoding="utf-8") as f:
             f.write(f"Source: {source_identifier}\n")
        logger.debug(f"Logged source identifier to {request_log_dir}/source.txt")

        with open(os.path.join(request_log_dir, "web_content.txt"), "w", encoding="utf-8") as f:
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

# --- Scheduled Task Function ---
def run_scheduled_summaries():
    """Job function executed by the scheduler."""
    # Use app context to ensure access to config, etc. if needed, although reading files directly is safer
    with app.app_context():
        logger.info("Starting scheduled summary run...")
        try:
            # Load config within the job to get fresh values if file changes
            with open(PROMPT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            scheduled_feeds = config.get("scheduled_rss_feeds", [])
            system_prompt = config.get("system_prompt", "")
            user_prompt_template = config.get("user_prompt_template", "") # Includes 3-min length instruction

            if not scheduled_feeds:
                logger.info("No scheduled RSS feeds configured. Skipping run.")
                return

            # Read API key (assuming Gemini for scheduled tasks for now)
            # TODO: Make the scheduled summarizer configurable
            api_key = utils.read_api_key(filepath=API_KEY_FILE, key_type="gemini")

            logger.info(f"Processing {len(scheduled_feeds)} scheduled feeds...")
            for feed_url in scheduled_feeds:
                try:
                    logger.info(f"Processing feed: {feed_url}")
                    # 1. Get latest article URL
                    article_url = utils.get_latest_article_url_from_rss(feed_url)
                    if not article_url:
                        logger.warning(f"Could not get article URL from RSS: {feed_url}. Skipping.")
                        continue

                    # 2. Get webpage text
                    web_text = utils.get_webpage_text(article_url)
                    if not web_text:
                        logger.warning(f"Could not extract text from article: {article_url}. Skipping.")
                        continue

                    # 3. Summarize (using Gemini by default for schedule)
                    summary = summarizer.summarize_text_with_gemini(web_text, api_key, system_prompt, user_prompt_template)

                    # 4. Call voice API
                    effective_ref_audio_path = REF_AUDIO_PATH if os.path.exists(REF_AUDIO_PATH) else None
                    audio_content = utils.call_voice_api(summary, ref_audio_path=effective_ref_audio_path)

                    # 5. Log results
                    now = datetime.datetime.now(pytz.utc) # Use UTC for timestamp consistency
                    timestamp_str = now.strftime("%Y%m%d_%H%M%S_%f")[:-3] # Add milliseconds
                    log_request_data(timestamp_str, feed_url, web_text, summary, audio_content)

                    logger.info(f"Successfully processed and logged feed: {feed_url}")
                    time.sleep(1) # Small delay between feeds

                except Exception as e:
                    logger.error(f"Failed to process scheduled feed {feed_url}: {e}", exc_info=True)
                    # Continue to the next feed

            logger.info("Finished scheduled summary run.")

        except Exception as e:
            logger.error(f"Error during scheduled summary run setup: {e}", exc_info=True)


# --- API Endpoint ---
@app.route('/summarize', methods=['POST'])
def summarize_endpoint():
    """ API endpoint for on-demand summarization. """
    # (Existing endpoint code remains largely the same)
    if not request.is_json:
        logger.warning("Received non-JSON request")
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    url_from_request = data.get('url')
    rss_url_from_request = data.get('rss_url')
    summarizer_choice = data.get('summarizer_choice', 'gemini')

    if not url_from_request and not rss_url_from_request:
        logger.warning("Missing 'url' or 'rss_url' in request data")
        return jsonify({"error": "Request must contain either 'url' or 'rss_url'"}), 400

    now = datetime.datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S") + f"_{now.microsecond // 1000:03d}"
    log_prefix = f"Request ID [{timestamp_str}]:"

    target_url = None
    source_identifier = None
    source_type = None

    try:
        if rss_url_from_request:
            source_type = "RSS"
            source_identifier = rss_url_from_request
            target_url = utils.get_latest_article_url_from_rss(rss_url_from_request)
            if not target_url:
                logger.error(f"{log_prefix} Could not get article URL from RSS feed: {rss_url_from_request}")
                return jsonify({"error": f"Could not retrieve article from RSS feed: {rss_url_from_request}"}), 400
        else:
            source_type = "Direct URL"
            source_identifier = url_from_request
            target_url = url_from_request

        logger.info(f"{log_prefix} Processing {source_type}: {target_url} (from {source_identifier}) with summarizer: {summarizer_choice}")

        # 1. Read configurations
        api_key = utils.read_api_key(filepath=API_KEY_FILE, key_type=summarizer_choice)
        system_prompt, user_prompt_template = utils.read_prompt_config(filepath=PROMPT_CONFIG_FILE)

        # 2. Get webpage text
        web_text = utils.get_webpage_text(target_url)
        if not web_text:
            logger.warning(f"{log_prefix} No text extracted from {target_url}, returning error.")
            return jsonify({"error": f"Could not extract text content from the target URL: {target_url}"}), 400

        # 3. Summarize text
        summary = ""
        if summarizer_choice == "gemini":
            summary = summarizer.summarize_text_with_gemini(web_text, api_key, system_prompt, user_prompt_template)
        elif summarizer_choice == "openrouter":
            summary = summarizer.summarize_text_with_openrouter(web_text, api_key, system_prompt, user_prompt_template)
        else:
            logger.error(f"{log_prefix} Invalid summarizer choice: {summarizer_choice}")
            return jsonify({"error": f"Invalid summarizer choice: {summarizer_choice}"}), 400

        logger.info(f"{log_prefix} Generated Summary ({summarizer_choice}): {summary[:100]}...")

        # 4. Call voice API
        effective_ref_audio_path = REF_AUDIO_PATH if os.path.exists(REF_AUDIO_PATH) else None
        audio_content = utils.call_voice_api(summary, ref_audio_path=effective_ref_audio_path)

        # 5. Log data
        log_request_data(timestamp_str, source_identifier, web_text, summary, audio_content)

        # 6. Encode audio data as Base64
        audio_base64 = base64.b64encode(audio_content).decode('utf-8')
        logger.info(f"{log_prefix} Encoded audio to Base64")

        # 7. Return summary text and Base64 encoded audio
        return jsonify({
            "summary_text": summary,
            "audio_base64": audio_base64
        })

    except FileNotFoundError as e:
         logger.error(f"{log_prefix} Configuration file not found: {e}", exc_info=True)
         return jsonify({"error": f"Server configuration error: {e}"}), 500
    except ValueError as e:
         logger.error(f"{log_prefix} Value error during processing: {e}", exc_info=True)
         return jsonify({"error": f"Processing error: {e}"}), 500
    except requests.exceptions.RequestException as e:
         logger.error(f"{log_prefix} API request failed: {e}", exc_info=True)
         return jsonify({"error": f"Failed to communicate with an external API: {e}"}), 502
    except Exception as e:
        logger.error(f"{log_prefix} An unexpected error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500


# --- Scheduler Setup & Start ---
# Check if scheduler is already running (e.g., in case of Flask reloader)
if not app.config.get('SCHEDULER_RUNNING'):
    scheduler = BackgroundScheduler(timezone=pytz.utc)
    # Schedule the job to run daily at midnight UTC
    # scheduler.add_job(run_scheduled_summaries, 'cron', hour=0, minute=0, id='daily_summary_job')
    scheduler.add_job(run_scheduled_summaries, trigger='interval', seconds=60, id='daily_summary_job')
    try:
        scheduler.start()
        logger.info("Scheduler started. Job 'run_scheduled_summaries' scheduled daily at 00:00 UTC.")
        # Shut down the scheduler when exiting the app
        atexit.register(lambda: scheduler.shutdown())
        app.config['SCHEDULER_RUNNING'] = True
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)
else:
    logger.info("Scheduler already running.")


# --- Main Execution ---
if __name__ == '__main__':
    # Run Flask app (for development)
    # Use 'flask --app summarizer_server/main run' for better practice
    logger.info("Starting Flask development server via __main__...")
    # use_reloader=False is important to prevent scheduler from running twice in debug mode
    app.run(debug=True, port=5000, use_reloader=False)