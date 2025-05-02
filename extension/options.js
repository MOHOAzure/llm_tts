const rssFeedsTextArea = document.getElementById('rss-feeds');
const saveButton = document.getElementById('save-button');
const statusDiv = document.getElementById('status');

// --- Functions ---

// Function to save the list of RSS feeds to chrome.storage.sync
function saveOptions() {
    const feedsText = rssFeedsTextArea.value;
    // Split by newline, trim whitespace, filter out empty lines
    const feedsArray = feedsText.split('\n')
                                .map(feed => feed.trim())
                                .filter(feed => feed.length > 0);

    chrome.storage.sync.set(
        { rssFeedList: feedsArray },
        () => {
            // Update status message on successful save
            statusDiv.textContent = 'Options saved.';
            console.log('RSS Feeds saved:', feedsArray);
            // Clear status message after a few seconds
            setTimeout(() => {
                statusDiv.textContent = '';
            }, 2000);
        }
    );
}

// Function to restore/load the saved RSS feeds into the text area
function restoreOptions() {
    // Use default value of an empty array if 'rssFeedList' not found
    chrome.storage.sync.get(
        { rssFeedList: [] }, // Default value
        (items) => {
            if (chrome.runtime.lastError) {
                console.error("Error retrieving options:", chrome.runtime.lastError);
                statusDiv.textContent = 'Error loading options.';
                return;
            }
            // Join the array back into a string with newlines for the text area
            rssFeedsTextArea.value = items.rssFeedList.join('\n');
            console.log('RSS Feeds loaded:', items.rssFeedList);
        }
    );
}

// --- Event Listeners ---

// Load saved options when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', restoreOptions);

// Save options when the save button is clicked
saveButton.addEventListener('click', saveOptions);