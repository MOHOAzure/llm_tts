// Listen for clicks on the browser action icon
chrome.action.onClicked.addListener((tab) => {
  console.log('Browser action clicked, opening popup for tab:', tab.id);
  chrome.action.openPopup(); // Programmatically open the popup
});

// Optional: Log installation or update
chrome.runtime.onInstalled.addListener(() => {
  console.log('Webpage Summarizer extension installed/updated.');
  // You could potentially set default settings in storage here
});