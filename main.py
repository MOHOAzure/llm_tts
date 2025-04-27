import requests
from bs4 import BeautifulSoup
import logging
import yaml
import google.generativeai as genai
import trafilatura

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration Reading Functions ---

def read_api_key(filepath="api_key.txt", key_type="google"):
    """Reads the specified API key (google or openrouter) from a file."""
    # Simple approach: assume api_key.txt holds the key needed for the selected summarizer
    # A more robust approach would use separate files or a config file for multiple keys.
    try:
        with open(filepath, "r") as f:
            key = f.read().strip()
            logger.info(f"Read API key for {key_type} from {filepath}")
            return key
    except FileNotFoundError:
        logger.error(f"API key file not found: {filepath}")
        raise

def read_prompt_config(filepath="prompt_config.yaml"):
    """Reads system and user prompt templates from a YAML file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            system_prompt = config.get("system_prompt", "")
            user_prompt_template = config.get("user_prompt_template", "")
            logger.info(f"Read prompts from {filepath}")
            return system_prompt, user_prompt_template
    except FileNotFoundError:
        logger.error(f"Prompt config file not found: {filepath}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {filepath}: {e}")
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

# --- Summarization Functions ---

def summarize_text_with_gemini(text, api_key, system_prompt, user_prompt_template):
    """Summarizes the given text using the standard Google Gemini API."""
    if not api_key:
        logger.error("Google API key is missing.")
        raise ValueError("Missing Google API key")

    try:
        genai.configure(api_key=api_key)
        generation_config = {"temperature": 0.0, "top_p": 1, "top_k": 1} # Simplified config
        safety_settings = [ # Standard safety settings
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        
        # Use a model available via standard API key, e.g., gemini-2.0-flash
        model_name = "gemini-2.0-flash" 
        logger.info(f"Using Gemini model: {model_name}")
        
        model = genai.GenerativeModel(model_name=model_name,
                                      generation_config=generation_config,
                                      system_instruction=system_prompt,
                                      safety_settings=safety_settings)

        user_prompt = user_prompt_template.replace("{{text}}", text)
        logger.info("Sending request to Google Gemini API...")
        response = model.generate_content(user_prompt)

        # Handle potential blocks or errors in response
        if not response.parts:
             if response.prompt_feedback.block_reason:
                  block_reason = response.prompt_feedback.block_reason
                  logger.error(f"Gemini request blocked. Reason: {block_reason}")
                  raise ValueError(f"Gemini request blocked: {block_reason}")
             else:
                  logger.error("Gemini response missing parts and block reason. Unknown error.")
                  raise ValueError("Gemini returned an empty response.")

        summary = response.text
        logger.info("Successfully received summary from Gemini.")
        return summary

    except Exception as e:
        logger.error(f"Google Gemini API request failed: {e}")
        # Consider logging response details if available: response.prompt_feedback
        raise

def summarize_text_with_openrouter(text, api_key, system_prompt, user_prompt_template):
    """Summarizes the given text using the OpenRouter API."""
    if not api_key:
        logger.error("OpenRouter API key is missing.")
        raise ValueError("Missing OpenRouter API key")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "YOUR_SITE_URL", # Optional
        "X-Title": "Webpage Summarizer" # Optional
    }
    user_prompt = user_prompt_template.replace("{{text}}", text)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    # You might want to make the model configurable here too
    openrouter_model = "google/gemini-flash-1.5" # Example model on OpenRouter
    data = {"model": openrouter_model, "messages": messages}
    logger.info(f"Sending request to OpenRouter API (Model: {openrouter_model})...")

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        summary = response.json()['choices'][0]['message']['content']
        logger.info("Successfully received summary from OpenRouter.")
        return summary
    except requests.exceptions.RequestException as e:
        logger.error(f"OpenRouter API request failed: {e}")
        if response is not None:
             logger.error(f"Response status code: {response.status_code}, Text: {response.text}")
        raise
    except (KeyError, IndexError) as e:
        logger.error(f"Error parsing OpenRouter response: {e}")
        logger.error(f"Full response: {response.json()}")
        raise

# --- Voice Synthesis Functions ---

def call_voice_api(summary, voice_api_url="http://127.0.0.1:9880/tts", ref_audio_path="ref_audio.wav"):
    """Calls the local voice API to synthesize the summary."""
    voice_params = {
        "text": summary, "text_lang": "zh", "ref_audio_path": ref_audio_path,
        "prompt_lang": "auto", "text_split_method": "cut5", "batch_size": "1",
        "media_type": "wav", "streaming_mode": "false"
    }
    try:
        logger.info(f"Sending request to voice API: {voice_api_url}")
        response = requests.get(voice_api_url, params=voice_params)
        response.raise_for_status()
        logger.info("Successfully received audio from voice API.")
        return response.content
    except requests.exceptions.RequestException as e:
        logger.error(f"Voice API request failed: {e}")
        raise

def save_audio(audio_content, output_path="output.wav"):
    """Saves the audio content to a file."""
    try:
        with open(output_path, "wb") as f:
            f.write(audio_content)
        logger.info(f"Audio successfully saved to {output_path}")
    except IOError as e:
        logger.error(f"Error saving audio file {output_path}: {e}")
        raise

# --- Main Execution ---

def main(url, summarizer_choice="gemini"): # Added choice parameter
    """Main function to orchestrate the summarization and speech synthesis."""
    try:
        # Read configurations
        # Assuming api_key.txt holds the key for the chosen summarizer
        api_key = read_api_key(key_type=summarizer_choice)
        system_prompt, user_prompt_template = read_prompt_config()

        # Core process
        web_text = get_webpage_text(url)
        if not web_text:
             logger.warning("No text extracted from webpage. Skipping.")
             return
        logger.info(f"web text: {web_text}")

        # Choose summarizer
        if summarizer_choice == "gemini":
            logger.info("Using Gemini for summarization.")
            summary = summarize_text_with_gemini(web_text, api_key, system_prompt, user_prompt_template)
        elif summarizer_choice == "openrouter":
            logger.info("Using OpenRouter for summarization.")
            # Note: Ensure api_key.txt contains the OpenRouter key if choosing this
            summary = summarize_text_with_openrouter(web_text, api_key, system_prompt, user_prompt_template)
        else:
            logger.error(f"Invalid summarizer choice: {summarizer_choice}")
            return

        logger.info(f"Generated Summary ({summarizer_choice}):\n{summary}")
        audio_content = call_voice_api(summary)
        save_audio(audio_content)

    except Exception as e:
        # Log the full traceback for better debugging
        logger.exception(f"An error occurred in the main process: {e}")


if __name__ == "__main__":
    target_url = "https://blog.google/technology/ai/google-gemini-ai/"
    
    # --- CHOOSE SUMMARIZER HERE ---
    selected_summarizer = "gemini" # or "openrouter" 
    # -----------------------------

    # Ensure api_key.txt contains the correct key for the selected_summarizer
    if selected_summarizer == "gemini":
        print("Ensure api_key.txt contains your Google API Key.")
    elif selected_summarizer == "openrouter":
         print("Ensure api_key.txt contains your OpenRouter API Key.")

    main(target_url, summarizer_choice=selected_summarizer)