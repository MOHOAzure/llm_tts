const statusDiv = document.getElementById('status');
const summaryContainer = document.getElementById('summary-container');
const replayButton = document.getElementById('replay-button');

let audioBuffer = null; // To store decoded audio data
const audioContext = new (window.AudioContext || window.webkitAudioContext)(); // Create AudioContext once
const SERVER_URL = 'http://127.0.0.1:5000/summarize';

// Function to update status message
function updateStatus(message) {
    statusDiv.textContent = message;
    console.log("Status:", message); // Log status to console for debugging
}

// Function to decode Base64 audio data
async function decodeAudioData(base64String) {
    try {
        // Convert Base64 string to ArrayBuffer
        const binaryString = window.atob(base64String);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        // Decode ArrayBuffer into AudioBuffer
        return await audioContext.decodeAudioData(bytes.buffer);
    } catch (error) {
        console.error('Error decoding audio data:', error);
        updateStatus('Error: Could not decode audio.');
        throw error; // Re-throw the error to be caught later
    }
}

// Function to play the decoded audio buffer
function playAudio(buffer) {
    if (!buffer) {
        console.error("No audio buffer to play.");
        updateStatus('Error: No audio available.');
        return;
    }
    try {
        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioContext.destination);
        source.start(0); // Play immediately
        updateStatus('Playing summary...');

        source.onended = () => {
            updateStatus('Summary finished.');
            console.log("Audio playback finished.");
        };
    } catch (error) {
        console.error('Error playing audio:', error);
        updateStatus('Error: Could not play audio.');
    }
}

// --- Main Logic ---

// Get current tab URL and fetch summary/audio when popup opens
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const currentTab = tabs[0];
    if (!currentTab || !currentTab.url) {
        updateStatus('Error: Could not get current tab URL.');
        return;
    }

    const pageUrl = currentTab.url;
    updateStatus(`Fetching summary for: ${pageUrl.substring(0, 50)}...`); // Show truncated URL
    console.log("Requesting summary for:", pageUrl);

    // Fetch summary and audio from the local server
    fetch(SERVER_URL, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        // TODO: Add summarizer_choice if needed, e.g., from user settings
        body: JSON.stringify({ url: pageUrl, summarizer_choice: 'gemini' }),
    })
    .then(response => {
        if (!response.ok) {
            // Try to get error message from server response body
            return response.json().then(errData => {
                throw new Error(errData.error || `HTTP error! status: ${response.status}`);
            }).catch(() => {
                // Fallback if response body is not JSON or empty
                throw new Error(`HTTP error! status: ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        console.log("Received data from server:", data);
        if (data.error) {
            throw new Error(data.error);
        }
        if (!data.summary_text || !data.audio_base64) {
             throw new Error('Server response missing summary or audio data.');
        }

        // Display summary text
        summaryContainer.textContent = data.summary_text;
        updateStatus('Decoding audio...');

        // Decode audio data
        return decodeAudioData(data.audio_base64);
    })
    .then(decodedBuffer => {
        audioBuffer = decodedBuffer; // Store for replay
        replayButton.disabled = false; // Enable replay button after successful decode
        updateStatus('Playing summary...');
        playAudio(audioBuffer); // Play automatically
    })
    .catch(error => {
        replayButton.disabled = true;
        console.error('Error fetching or processing summary:', error);
        updateStatus(`Error: ${error.message}`);
        summaryContainer.textContent = ''; // Clear summary on error
        replayButton.disabled = true;
    });
});

// Event listener for the replay button
replayButton.addEventListener('click', () => {
    console.log("Replay button clicked.");
    playAudio(audioBuffer);
});