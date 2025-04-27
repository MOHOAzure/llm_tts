import requests

url = "http://127.0.0.1:9880/tts"

params = {
    "text": "TEXT TO VO",
    "text_lang": "zh",
    "ref_audio_path": "ref_audio.wav",
    "prompt_lang": "auto",
    "text_split_method": "cut5",
    "batch_size": "1",
    "media_type": "wav",
    "streaming_mode": "true"
}

try:
    response = requests.get(url, params=params)
    response.raise_for_status()

    with open("output.wav", "wb") as f:
        f.write(response.content)
    print("Audio Saved. output.wav")


except requests.exceptions.RequestException as e:
    print(f"Err: {e}")