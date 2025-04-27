from flask import Flask, request, jsonify
import logging
import base64
import os
import utils
import summarizer
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Determine server directory for relative paths
SERVER_DIR = os.path.dirname(__file__)
API_KEY_FILE = os.path.join(SERVER_DIR, "api_key.txt")
PROMPT_CONFIG_FILE = os.path.join(SERVER_DIR, "prompt_config.yaml")
REF_AUDIO_PATH = os.path.abspath(os.path.join(SERVER_DIR, "ref_audio.wav"))


@app.route('/summarize', methods=['POST'])
def summarize_endpoint():
    """
    API endpoint to receive a URL, summarize it, get TTS audio, and return audio data.
    Expects JSON payload: {"url": "...", "summarizer_choice": "gemini" | "openrouter"}
    Returns JSON payload: {"audio_base64": "..."} or {"error": "..."}
    """
    if not request.is_json:
        logger.error("Request is not JSON")
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    url = data.get('url')
    summarizer_choice = data.get('summarizer_choice', 'gemini') # Default to gemini

    if not url:
        logger.error("Missing 'url' in request data")
        return jsonify({"error": "Missing 'url' in request data"}), 400

    logger.info(f"Received request for URL: {url} with summarizer: {summarizer_choice}")

    try:
        # 1. Read configurations
        # Assuming api_key.txt holds the key for the chosen summarizer
        api_key = utils.read_api_key(filepath=API_KEY_FILE, key_type=summarizer_choice)
        system_prompt, user_prompt_template = utils.read_prompt_config(filepath=PROMPT_CONFIG_FILE)

        # 2. Get webpage text
        web_text = utils.get_webpage_text(url)
        if not web_text:
            logger.warning("No text extracted, returning empty audio.")
            # Return empty audio or a specific error message? Returning empty for now.
            return jsonify({"audio_base64": ""})

        # 3. Summarize text
        summary = ""
        if summarizer_choice == "gemini":
            summary = summarizer.summarize_text_with_gemini(web_text, api_key, system_prompt, user_prompt_template)
        elif summarizer_choice == "openrouter":
            summary = summarizer.summarize_text_with_openrouter(web_text, api_key, system_prompt, user_prompt_template)
        else:
            logger.error(f"Invalid summarizer choice: {summarizer_choice}")
            return jsonify({"error": f"Invalid summarizer choice: {summarizer_choice}"}), 400

        logger.info(f"Generated Summary ({summarizer_choice}): {summary[:100]}...") # Log beginning of summary

        # 4. Call voice API
        # Pass the absolute path to ref_audio.wav if it exists
        audio_content = utils.call_voice_api(summary, ref_audio_path=REF_AUDIO_PATH if os.path.exists(REF_AUDIO_PATH) else None)

        # 5. Encode audio data as Base64
        audio_base64 = base64.b64encode(audio_content).decode('utf-8')
        logger.info("Encoded audio to Base64")

        # 6. Return Base64 encoded audio
        return jsonify({"audio_base64": audio_base64})

    except FileNotFoundError as e:
         logger.error(f"Configuration file not found: {e}")
         return jsonify({"error": f"Server configuration error: {e}"}), 500
    except ValueError as e: # Catch API key errors or Gemini blocks
         logger.error(f"Value error during processing: {e}")
         return jsonify({"error": f"Processing error: {e}"}), 500
    except requests.exceptions.RequestException as e:
         logger.error(f"API request failed: {e}")
         return jsonify({"error": f"Failed to communicate with an external API: {e}"}), 502
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500

if __name__ == '__main__':
    # Note: For development only. Use a proper WSGI server like Gunicorn in production.
    logger.info("Starting Flask development server...")
    # Make sure api_key.txt, prompt_config.yaml, and ref_audio.wav are in the same directory
    app.run(debug=True, port=5000) # Runs on http://127.0.0.1:5000