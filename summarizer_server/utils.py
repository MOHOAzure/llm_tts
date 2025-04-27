import requests
from bs4 import BeautifulSoup
import logging
import yaml
import trafilatura
import os # Needed for path joining

logger = logging.getLogger(__name__)

# --- Configuration Reading Functions ---

def read_api_key(filepath="api_key.txt", key_type="google"):
    """Reads the specified API key from a file within the server directory."""
    # Construct path relative to this utils.py file
    server_dir = os.path.dirname(__file__)
    full_path = os.path.join(server_dir, filepath)
    try:
        with open(full_path, "r") as f:
            key = f.read().strip()
            logger.info(f"Read API key for {key_type} from {full_path}")
            return key
    except FileNotFoundError:
        logger.error(f"API key file not found: {full_path}")
        raise

def read_prompt_config(filepath="prompt_config.yaml"):
    """Reads system and user prompt templates from a YAML file within the server directory."""
    server_dir = os.path.dirname(__file__)
    full_path = os.path.join(server_dir, filepath)
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            system_prompt = config.get("system_prompt", "")
            user_prompt_template = config.get("user_prompt_template", "")
            logger.info(f"Read prompts from {full_path}")
            return system_prompt, user_prompt_template
    except FileNotFoundError:
        logger.error(f"Prompt config file not found: {full_path}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {full_path}: {e}")
        raise

# --- Core Functionality Functions ---

def get_webpage_text(url):
    """Fetches and extracts main text content from a webpage URL using Trafilatura."""
    logger.info(f"Attempting to fetch and extract main content from: {url}")
    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        logger.warning(f"Trafilatura could not download content from {url}. Falling back.")
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            text = ' '.join(soup.stripped_strings)
            logger.info(f"Successfully fetched text using fallback for {url}")
            return text
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching webpage {url} with fallback: {e}")
            raise
    else:
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        if text:
            logger.info(f"Successfully extracted main content using Trafilatura from {url}")
            return text
        else:
            logger.warning(f"Trafilatura extracted no main content from {url}. Check page structure.")
            return ""

# --- Voice Synthesis Functions ---

def call_voice_api(summary, voice_api_url="http://127.0.0.1:9880/tts", ref_audio_path="../ref_audio.wav"):
    """
    Calls the local voice API to synthesize the summary.
    Assumes ref_audio.wav is one level up from the server directory.
    """
    # Adjust path for ref_audio relative to the server directory
    server_dir = os.path.dirname(__file__)
    ref_audio_full_path = os.path.abspath(os.path.join(server_dir, ref_audio_path))

    if not os.path.exists(ref_audio_full_path):
         logger.warning(f"Reference audio file not found at {ref_audio_full_path}. Proceeding without it.")
         ref_audio_param = None # Or handle as error depending on API requirement
    else:
         ref_audio_param = ref_audio_full_path

    voice_params = {
        "text": summary, "text_lang": "zh",
        "prompt_lang": "auto", "text_split_method": "cut5", "batch_size": "1",
        "media_type": "wav", "streaming_mode": "false"
    }
    # Only include ref_audio_path if it exists
    if ref_audio_param:
        voice_params["ref_audio_path"] = ref_audio_param

    try:
        logger.info(f"Sending request to voice API: {voice_api_url} with params: { {k:v for k,v in voice_params.items() if k != 'text'} }") # Avoid logging full summary
        response = requests.get(voice_api_url, params=voice_params)
        response.raise_for_status()
        logger.info("Successfully received audio data from voice API.")
        # Return raw audio content (bytes)
        return response.content
    except requests.exceptions.RequestException as e:
        logger.error(f"Voice API request failed: {e}")
        if response is not None:
            logger.error(f"Voice API response status: {response.status_code}, text: {response.text}")
        raise