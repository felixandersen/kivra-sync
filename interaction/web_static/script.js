// DOM elements
const statusElement = document.getElementById('status');
const statusTextElement = document.getElementById('status-text');
const runButton = document.getElementById('runButton');
const qrContainer = document.getElementById('qrContainer');
const qrImage = document.getElementById('qrImage');
const spinner = document.getElementById('spinner');
const resultsElement = document.getElementById('results');

// Connection management
let connectionState = {
    shouldReconnect: true,
    retryCount: 0,
    maxRetries: 10,
    baseDelay: 5000,
    maxDelay: 60000,
    currentDelay: 5000,
    reconnectTimeout: null
};

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeSSE();
    setupEventListeners();
});

// Set up event listeners
function setupEventListeners() {
    runButton.addEventListener('click', triggerSync);
}

// Initialize Server-Sent Events connection
function initializeSSE() {
    // Close existing connection if any
    if (window.eventSource) {
        window.eventSource.close();
        window.eventSource = null;
    }
    
    // Clear any pending reconnection timeout
    if (connectionState.reconnectTimeout) {
        clearTimeout(connectionState.reconnectTimeout);
        connectionState.reconnectTimeout = null;
    }
    
    // Don't reconnect if we shouldn't
    if (!connectionState.shouldReconnect) {
        console.log('SSE reconnection disabled');
        return;
    }
    
    // Check if we've exceeded max retries
    if (connectionState.retryCount >= connectionState.maxRetries) {
        console.log('Max SSE reconnection attempts reached, giving up');
        updateStatus('error', 'Connection lost - server may be down');
        return;
    }
    
    console.log(`Initializing SSE connection (attempt ${connectionState.retryCount + 1}/${connectionState.maxRetries})`);
    
    const eventSource = new EventSource('/events');
    
    eventSource.onopen = function(event) {
        console.log('SSE connection opened');
        // Reset connection state on successful connection
        connectionState.retryCount = 0;
        connectionState.currentDelay = connectionState.baseDelay;
    };
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            // Skip heartbeat messages
            if (data.heartbeat) {
                return;
            }
            
            console.log('Received SSE message:', data);
            updateUI(data);
        } catch (error) {
            console.error('Error parsing SSE message:', error);
        }
    };
    
    eventSource.onerror = function(event) {
        console.error('SSE connection error:', event);
        
        // Close the current connection
        eventSource.close();
        
        // Don't reconnect if we shouldn't
        if (!connectionState.shouldReconnect) {
            console.log('SSE reconnection disabled, not retrying');
            return;
        }
        
        // Increment retry count
        connectionState.retryCount++;
        
        // Check if we've exceeded max retries
        if (connectionState.retryCount >= connectionState.maxRetries) {
            console.log('Max SSE reconnection attempts reached, giving up');
            updateStatus('error', 'Connection lost - server may be down');
            return;
        }
        
        // Calculate delay with exponential backoff
        connectionState.currentDelay = Math.min(
            connectionState.baseDelay * Math.pow(2, connectionState.retryCount - 1),
            connectionState.maxDelay
        );
        
        console.log(`SSE connection failed, retrying in ${connectionState.currentDelay}ms (attempt ${connectionState.retryCount}/${connectionState.maxRetries})`);
        
        // Schedule reconnection
        connectionState.reconnectTimeout = setTimeout(() => {
            initializeSSE();
        }, connectionState.currentDelay);
    };
    
    // Store reference for potential cleanup
    window.eventSource = eventSource;
}

// Update the UI based on received data
function updateUI(data) {
    const status = data.status;
    const message = data.message || '';
    
    // Update status display
    updateStatus(status, message.replace(/\n/g, '<br>'));
    
    // Handle different states
    switch (status) {
        case 'idle':
            handleIdleState();
            break;
        case 'processing':
            handleProcessingState();
            break;
        case 'qr_ready':
            handleQRReadyState(data.qr_url);
            break;
        case 'authenticated':
            handleAuthenticatedState();
            break;
        case 'complete':
            handleCompleteState(data.stats, message);
            break;
        case 'error':
            handleErrorState(message);
            break;
    }
}

// Update status indicator
function updateStatus(status, message) {
    // Update status class
    statusElement.className = `status ${status}`;
    
    // Update status text
    statusTextElement.innerHTML = message;
    
    // Add fade-in animation
    statusElement.classList.add('fade-in');
    setTimeout(() => statusElement.classList.remove('fade-in'), 300);
}

// Handle idle state
function handleIdleState() {
    runButton.disabled = false;
    runButton.innerHTML = 'Run sync now<br>(be ready with BankID app)';
    hideElement(qrContainer);
    hideElement(spinner);
    hideElement(resultsElement);
}

// Handle processing state
function handleProcessingState() {
    runButton.disabled = true;
    runButton.innerHTML = 'Processing...';
    hideElement(qrContainer);
    showElement(spinner, 'flex');
    hideElement(resultsElement);
}

// Handle QR ready state
function handleQRReadyState(qrUrl) {
    runButton.disabled = true;
    runButton.innerHTML = 'Scan QR code';
    
    if (qrUrl) {
        qrImage.src = qrUrl;
        showElement(qrContainer);
    }
    
    hideElement(spinner);
    hideElement(resultsElement);
}

// Handle authenticated state
function handleAuthenticatedState() {
    runButton.disabled = true;
    runButton.innerHTML = 'Syncing data...';
    hideElement(qrContainer);
    showElement(spinner, 'flex');
    hideElement(resultsElement);
}

// Handle completion state
function handleCompleteState(stats, message) {
    runButton.disabled = false;
    runButton.innerHTML = 'Run sync now<br>(be ready with BankID app)';
    hideElement(qrContainer);
    hideElement(spinner);
    
    // Show results
    showResults(true, message, stats);
}

// Handle error state
function handleErrorState(message) {
    runButton.disabled = false;
    runButton.innerHTML = 'Run sync now<br>(be ready with BankID app)';
    hideElement(qrContainer);
    hideElement(spinner);
    
    // Show error results
    showResults(false, message);
}

// Show results section
function showResults(isSuccess, message, stats = null) {
    resultsElement.className = `results ${isSuccess ? 'success' : 'error'}`;
    
    let content = `<h3>${isSuccess ? 'Sync completed' : 'Sync failed'}</h3>`;
    content += `<pre>${message}</pre>`;
    
    if (stats && isSuccess) {
        content += '<div class="stats">';
        content += `<div class="stats-item">
            <span class="stats-label">Receipts found:</span>
            <span class="stats-value">${stats.receipts_total || 0}</span>
        </div>`;
        content += `<div class="stats-item">
            <span class="stats-label">Receipts fetched:</span>
            <span class="stats-value">${stats.receipts_fetched || 0}</span>
        </div>`;
        content += `<div class="stats-item">
            <span class="stats-label">New receipts:</span>
            <span class="stats-value">${stats.receipts_stored || 0}</span>
        </div>`;
        content += `<div class="stats-item">
            <span class="stats-label">Letters found:</span>
            <span class="stats-value">${stats.letters_total || 0}</span>
        </div>`;
        content += `<div class="stats-item">
            <span class="stats-label">Letters fetched:</span>
            <span class="stats-value">${stats.letters_fetched || 0}</span>
        </div>`;
        content += `<div class="stats-item">
            <span class="stats-label">New letters:</span>
            <span class="stats-value">${stats.letters_stored || 0}</span>
        </div>`;
        content += '</div>';
    }
    
    resultsElement.innerHTML = content;
    showElement(resultsElement);
}

// Trigger sync process
function triggerSync() {
    if (runButton.disabled) {
        return;
    }
    
    fetch('/trigger', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Sync triggered successfully:', data);
    })
    .catch(error => {
        console.error('Error triggering sync:', error);
        updateStatus('error', 'Failed to start sync process');
    });
}

// Utility functions
function showElement(element, value = 'block') {
    element.style.display = value;
    element.classList.add('fade-in');
    setTimeout(() => element.classList.remove('fade-in'), 300);
}

function hideElement(element) {
    element.style.display = 'none';
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    console.log('Page unloading, disabling SSE reconnection');
    
    // Disable reconnection
    connectionState.shouldReconnect = false;
    
    // Clear any pending reconnection timeout
    if (connectionState.reconnectTimeout) {
        clearTimeout(connectionState.reconnectTimeout);
        connectionState.reconnectTimeout = null;
    }
    
    // Close existing connection
    if (window.eventSource) {
        window.eventSource.close();
        window.eventSource = null;
    }
});

// Handle visibility change (tab switching)
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        // Page is hidden, could pause some operations
        console.log('Page hidden');
    } else {
        // Page is visible again
        console.log('Page visible');
        
        // Re-enable reconnection if it was disabled
        if (!connectionState.shouldReconnect) {
            connectionState.shouldReconnect = true;
            connectionState.retryCount = 0; // Reset retry count
        }
        
        // Reconnect SSE if needed
        if (!window.eventSource || window.eventSource.readyState === EventSource.CLOSED) {
            console.log('Reconnecting SSE after page became visible');
            initializeSSE();
        }
    }
});

// Add a function to manually reset connection (useful for debugging)
function resetSSEConnection() {
    console.log('Manually resetting SSE connection');
    connectionState.retryCount = 0;
    connectionState.shouldReconnect = true;
    initializeSSE();
}

// Expose reset function globally for debugging
window.resetSSEConnection = resetSSEConnection;
