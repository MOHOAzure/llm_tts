// --- Constants ---
const SERVER_URL = 'http://127.0.0.1:5000/summarize';
let audioContext = null;
let currentAudioSource = null; // To handle stopping previous audio

// --- Helper Functions ---

// Function to decode Base64 string to ArrayBuffer
function base64ToArrayBuffer(base64) {
  try {
    const binaryString = atob(base64);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
  } catch (error) {
    console.error('Error decoding Base64 string:', error);
    // Consider notifying the user about corrupted data
    chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon48.png', // Make sure you have this icon
        title: '播放錯誤',
        message: '從伺服器收到的音訊數據格式錯誤。'
    });
    throw new Error('Invalid Base64 audio data received.');
  }
}

// Function to play audio buffer
async function playAudio(audioBuffer) {
  // Ensure AudioContext is created/resumed after user interaction
  if (!audioContext || audioContext.state === 'suspended') {
     if (audioContext) await audioContext.close(); // Close existing suspended context
     audioContext = new (window.AudioContext || window.webkitAudioContext)();
     // Attempt to resume context if needed, though usually starts in 'running' state here
     if (audioContext.state === 'suspended') {
        await audioContext.resume();
     }
  }


  // Stop any currently playing audio
  if (currentAudioSource) {
    try {
      currentAudioSource.stop();
      console.log("Stopped previous audio source.");
    } catch (e) {
      // It might have already finished, which is fine
      console.warn("Could not stop previous audio source (might have already finished):", e);
    }
    currentAudioSource = null;
  }

  try {
    // Decode the audio data (assuming WAV format from your TTS)
    console.log("Decoding audio data...");
    const decodedData = await audioContext.decodeAudioData(audioBuffer);
    console.log("Audio data decoded successfully.");

    // Create a buffer source
    const source = audioContext.createBufferSource();
    source.buffer = decodedData;

    // Connect the source to the context's destination (the speakers)
    source.connect(audioContext.destination);

    // Start playback
    console.log("Starting audio playback...");
    source.start(0);
    currentAudioSource = source; // Store the current source

    // Handle playback ending
    source.onended = () => {
      console.log('Audio playback finished.');
      currentAudioSource = null; // Clear the reference when done
      // Optional: Close context after inactivity
      // setTimeout(() => { if (audioContext && !currentAudioSource && audioContext.state === 'running') audioContext.close().then(() => { audioContext = null; console.log("AudioContext closed due to inactivity."); }); }, 5000);
    };

  } catch (error) {
    console.error('Error decoding or playing audio:', error);
    chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon48.png',
        title: '播放錯誤',
        message: `無法播放音訊： ${error.message}`
    });
  }
}

// --- Event Listeners ---

// Listen for clicks on the browser action icon
chrome.action.onClicked.addListener(async (tab) => {
  console.log('Browser action clicked for tab:', tab.id, 'URL:', tab.url);

  // Basic URL check
  if (!tab.url || (!tab.url.startsWith('http:') && !tab.url.startsWith('https:'))) {
    console.warn('Invalid URL for summarization:', tab.url);
    chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon48.png',
        title: '無法摘要',
        message: '此擴充功能無法摘要目前頁面 (URL 無效)。'
    });
    return;
  }

  // Indicate processing by changing the badge text
  await chrome.action.setBadgeText({ text: '...', tabId: tab.id });
  await chrome.action.setBadgeBackgroundColor({ color: '#FFA500', tabId: tab.id }); // Orange badge

  try {
    console.log(`Sending URL to server: ${tab.url}`);
    const response = await fetch(SERVER_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      // Sending URL and default summarizer choice
      // TODO: Add UI to select summarizer choice later if needed
      body: JSON.stringify({ url: tab.url, summarizer_choice: 'gemini' }),
    });

    if (!response.ok) {
      let errorMsg = `伺服器錯誤 ${response.status}`;
      try {
          const errorData = await response.json();
          errorMsg = errorData.error || errorMsg; // Use server's error message if available
      } catch (e) {
          errorMsg = `${errorMsg}: ${response.statusText}`; // Fallback if response is not JSON
      }
      console.error(`Server error: ${response.status}`, errorMsg);
      throw new Error(errorMsg);
    }

    const data = await response.json();

    if (data.error) {
      console.error('Server returned an error:', data.error);
      throw new Error(data.error);
    }

    if (data.audio_base64 && data.audio_base64.length > 0) {
      console.log('Received audio data from server.');
      const audioBuffer = base64ToArrayBuffer(data.audio_base64);
      await playAudio(audioBuffer);
    } else {
      console.warn('Server returned empty audio data.');
      chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icons/icon48.png',
          title: '摘要結果',
          message: '伺服器已處理，但未收到有效的音訊摘要。'
      });
    }

  } catch (error) {
    console.error('Error during summarization request or playback:', error);
    chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon48.png',
        title: '處理錯誤',
        message: `發生錯誤： ${error.message}`
    });
  } finally {
    // Clear the badge when done or on error
    await chrome.action.setBadgeText({ text: '', tabId: tab.id });
  }
});

// Optional: Log installation or update
chrome.runtime.onInstalled.addListener(() => {
  console.log('Webpage Summarizer extension installed/updated.');
  // You could potentially set default settings in storage here
});