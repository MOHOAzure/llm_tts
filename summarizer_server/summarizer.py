import requests
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

# --- Summarization Functions ---

def summarize_text_with_gemini(text, api_key, system_prompt, user_prompt_template):
    """Summarizes the given text using the standard Google Gemini API."""
    if not api_key:
        logger.error("Google API key is missing.")
        raise ValueError("Missing Google API key")

    try:
        genai.configure(api_key=api_key)
        generation_config = {"temperature": 0.0, "top_p": 1, "top_k": 1}
        safety_settings = [
            # {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            # {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            # {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            # {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        
        # Use a model available via standard API key, e.g., 
        # gemini-2.5-pro-preview-03-25, gemini-2.5-flash-preview-04-17
        # gemini-2.0-flash-lite, gemini-2.0-flash

        model_name = "gemini-2.5-pro-preview-03-25"
        logger.info(f"Using Gemini model: {model_name}")
        
        model = genai.GenerativeModel(model_name=model_name,
                                      generation_config=generation_config,
                                      system_instruction=system_prompt,
                                      safety_settings=safety_settings)

        user_prompt = user_prompt_template.replace("{{text}}", text)
        logger.info("Sending request to Google Gemini API...")
        response = model.generate_content(user_prompt)

        if not response.parts:
             if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                  block_reason = response.prompt_feedback.block_reason
                  logger.error(f"Gemini request blocked. Reason: {block_reason}")
                  raise ValueError(f"Gemini request blocked: {block_reason}")
             else:
                  # Log the full response if possible for debugging non-standard errors
                  try:
                      full_response_text = str(response)
                  except Exception:
                      full_response_text = "Could not serialize response."
                  logger.error(f"Gemini response missing parts and block reason. Unknown error. Response: {full_response_text}")
                  raise ValueError("Gemini returned an empty or invalid response.")

        summary = response.text
        logger.info("Successfully received summary from Gemini.")
        return summary

    except Exception as e:
        logger.exception(f"Google Gemini API request failed: {e}") # Use logger.exception to include traceback
        raise

def summarize_text_with_openrouter(text, api_key, system_prompt, user_prompt_template):
    """Summarizes the given text using the OpenRouter API."""
    if not api_key:
        logger.error("OpenRouter API key is missing.")
        raise ValueError("Missing OpenRouter API key")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "YOUR_SITE_URL",
        "X-Title": "Webpage Summarizer" # Optional
    }
    user_prompt = user_prompt_template.replace("{{text}}", text)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    openrouter_model = "google/gemini-2.0-flash-exp:free" # Example model on OpenRouter
    data = {"model": openrouter_model, "messages": messages}
    logger.info(f"Sending request to OpenRouter API (Model: {openrouter_model})...")

    response = None # Initialize response to None
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        summary = response.json()['choices'][0]['message']['content']
        logger.info("Successfully received summary from OpenRouter.")
        return summary
    except requests.exceptions.RequestException as e:
        # Log response details if available
        response_details = ""
        if response is not None:
            response_details = f" Status: {response.status_code}, Text: {response.text}"
        logger.exception(f"OpenRouter API request failed: {e}{response_details}")
        raise
    except (KeyError, IndexError, TypeError) as e: # Added TypeError for potential .json() issues
        response_details = ""
        if response is not None:
             try:
                  response_details = f" Response: {response.json()}"
             except Exception:
                  response_details = f" Response Text: {response.text}" # Fallback if .json() fails
        logger.exception(f"Error parsing OpenRouter response: {e}{response_details}")
        raise
    except Exception as e: # Catch any other unexpected errors
        logger.exception(f"An unexpected error occurred during OpenRouter summarization: {e}")
        raise