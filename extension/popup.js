// --- DOM Elements ---
const statusDiv = document.getElementById('status');
const summaryContainer = document.getElementById('summary-container');
const controlsDiv = document.getElementById('controls'); // Get controls container
const replayButton = document.getElementById('replay-button');
const sourceSelect = document.getElementById('source-select');
const summarizeButton = document.getElementById('summarize-button');

// --- State & Configuration ---
let audioBuffer = null; // To store decoded audio data
const audioContext = new (window.AudioContext || window.webkitAudioContext)(); // Create AudioContext once
const SERVER_URL = 'http://127.0.0.1:5000/summarize';

// --- UI Update Functions ---
function updateStatus(message) {
    statusDiv.textContent = message;
    console.log("Status:", message);
}

function showSummaryArea(show = true) {
    summaryContainer.style.display = show ? 'block' : 'none';
    controlsDiv.style.display = show ? 'block' : 'none';
}

function resetUI() {
    updateStatus('Select source and click Summarize.');
    summaryContainer.textContent = '';
    showSummaryArea(false); // Hide summary and controls
    replayButton.disabled = true;
    audioBuffer = null;
}

// --- Audio Handling ---
async function decodeAudioData(base64String) {
    try {
        const binaryString = window.atob(base64String);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        return await audioContext.decodeAudioData(bytes.buffer);
    } catch (error) {
        console.error('Error decoding audio data:', error);
        updateStatus('Error: Could not decode audio.');
        throw error;
    }
}

function playAudio(buffer) {
    if (!buffer) {
        console.error("No audio buffer to play.");
        updateStatus('Error: No audio available.');
        return;
    }
    try {
        // Ensure context is running (might be needed after long inactivity)
        if (audioContext.state === 'suspended') {
            audioContext.resume();
        }
        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioContext.destination);
        source.start(0);
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

// --- Data Fetching & Processing ---
async function fetchSummaryAndPlay(requestBody) {
    updateStatus('Requesting summary from server...');
    console.log("Sending request to server:", requestBody);
    summarizeButton.disabled = true; // Disable button during request

    try {
        const response = await fetch(SERVER_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
            let errorMsg = `Server error (${response.status})`;
            try {
                const errData = await response.json();
                errorMsg = errData.error || errorMsg;
            } catch (e) { /* Ignore if response is not JSON */ }
            throw new Error(errorMsg);
        }

        const data = await response.json();
        console.log("Received data from server:", data);

        if (data.error) { throw new Error(data.error); }
        if (!data.summary_text || !data.audio_base64) {
            throw new Error('Server response missing summary or audio data.');
        }

        // Display summary and show area
        summaryContainer.textContent = data.summary_text;
        showSummaryArea(true);
        updateStatus('Decoding audio...');

        // Decode and store audio data
        audioBuffer = await decodeAudioData(data.audio_base64);
        replayButton.disabled = false; // Enable replay button
        playAudio(audioBuffer); // Play automatically

    } catch (error) {
        console.error('Error fetching or processing summary:', error);
        updateStatus(`Error: ${error.message}`);
        resetUI(); // Reset UI on error, but keep status message
        updateStatus(`Error: ${error.message}`); // Show error status again
    } finally {
        summarizeButton.disabled = false; // Re-enable button
    }
}

// --- Initialization ---
function loadRssFeeds() {
    chrome.storage.sync.get({ rssFeedList: [] }, (items) => {
        if (chrome.runtime.lastError) {
            console.error("Error loading RSS feeds:", chrome.runtime.lastError);
            updateStatus('Error loading RSS feeds.');
            return;
        }
        const feeds = items.rssFeedList;
        console.log('Loaded RSS Feeds:', feeds);
        feeds.forEach(feedUrl => {
            if (feedUrl) { // Ensure URL is not empty
                const option = document.createElement('option');
                option.value = feedUrl;
                // Try to extract a readable name from the URL
                try {
                     const urlParts = new URL(feedUrl);
                     option.textContent = urlParts.hostname; // Use hostname as label
                } catch (e) {
                     option.textContent = feedUrl; // Fallback to full URL
                }
                sourceSelect.appendChild(option);
            }
        });
    });
}

// --- Event Listeners ---
summarizeButton.addEventListener('click', async () => {
    const selectedValue = sourceSelect.value;
    let requestBody = { summarizer_choice: 'gemini' }; // Default summarizer

    resetUI(); // Clear previous results and hide area

    if (selectedValue === 'current_tab') {
        updateStatus('Getting current tab URL...');
        try {
            const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
            const currentTab = tabs[0];
            if (!currentTab || !currentTab.url || (!currentTab.url.startsWith('http:') && !currentTab.url.startsWith('https:'))) {
                throw new Error('Invalid URL for current tab.');
            }
            requestBody.url = currentTab.url;
            fetchSummaryAndPlay(requestBody);
        } catch (error) {
            console.error("Error getting current tab:", error);
            updateStatus(`Error: ${error.message}`);
        }
    } else {
        // Assume selectedValue is an RSS URL
        requestBody.rss_url = selectedValue;
        fetchSummaryAndPlay(requestBody);
    }
});

replayButton.addEventListener('click', () => {
    console.log("Replay button clicked.");
    playAudio(audioBuffer);
});

// Load RSS feeds when the popup opens
document.addEventListener('DOMContentLoaded', loadRssFeeds);