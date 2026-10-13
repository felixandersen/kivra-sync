// DOM elements
const statusElement = document.getElementById('status');
const statusTextElement = document.getElementById('status-text');
const runButton = document.getElementById('runButton');
const qrContainer = document.getElementById('qrContainer');
const qrImage = document.getElementById('qrImage');
const spinner = document.getElementById('spinner');
const resultsElement = document.getElementById('results');
const settingsForm = document.getElementById('settings');
const ssnInput = document.getElementById('ssnInput');
const ssnHint = document.getElementById('ssnHint');
const modeInputs = document.querySelectorAll('input[name="accountMode"]');

// Settings are kept in this browser only
const STORAGE_KEYS = { ssn: 'kivraSync.ssn', accountMode: 'kivraSync.accountMode' };
let serverConfig = { ssn_configured: false, default_account_mode: 'personal' };

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
    loadSettings();
    initializeSSE();
    setupEventListeners();
});

// Storage access can throw (private browsing, blocked site data)
function readSetting(key) {
    try {
        return localStorage.getItem(key);
    } catch (error) {
        return null;
    }
}

function writeSetting(key, value) {
    try {
        if (value) {
            localStorage.setItem(key, value);
        } else {
            localStorage.removeItem(key);
        }
    } catch (error) {
        console.warn('Could not save setting:', error);
    }
}

// Load saved settings, falling back to the server defaults
function loadSettings() {
    ssnInput.value = readSetting(STORAGE_KEYS.ssn) || '';
    setAccountMode(readSetting(STORAGE_KEYS.accountMode));

    fetch('/config')
        .then(response => response.ok ? response.json() : null)
        .then(config => {
            if (!config) {
                return;
            }
            serverConfig = config;
            if (!readSetting(STORAGE_KEYS.accountMode)) {
                setAccountMode(config.default_account_mode);
            }
            updateSsnHint();
        })
        .catch(error => console.warn('Could not load server config:', error));
}

function setAccountMode(mode) {
    modeInputs.forEach(input => {
        if (input.value === mode) {
            input.checked = true;
        }
    });
}

function getAccountMode() {
    const checked = document.querySelector('input[name="accountMode"]:checked');
    return checked ? checked.value : 'personal';
}

// Accept YYYYMMDDXXXX, optionally with a dash or spaces
function normalizeSsn(value) {
    const ssn = value.replace(/[\s-]/g, '');
    return /^\d{12}$/.test(ssn) ? ssn : null;
}

function updateSsnHint(invalidMessage = null) {
    ssnInput.classList.toggle('invalid', !!invalidMessage);
    ssnHint.classList.toggle('invalid', !!invalidMessage);
    if (invalidMessage) {
        ssnHint.textContent = invalidMessage;
    } else if (!ssnInput.value && serverConfig.ssn_configured) {
        ssnHint.textContent = 'Leave empty to use the number configured on the server.';
    } else {
        ssnHint.textContent = 'Saved in this browser only.';
    }
}

function setSettingsEnabled(enabled) {
    settingsForm.classList.toggle('disabled', !enabled);
    ssnInput.disabled = !enabled;
    modeInputs.forEach(input => input.disabled = !enabled);
}

// Set up event listeners
function setupEventListeners() {
    runButton.addEventListener('click', triggerSync);

    settingsForm.addEventListener('submit', event => {
        event.preventDefault();
        triggerSync();
    });

    ssnInput.addEventListener('input', () => updateSsnHint());

    ssnInput.addEventListener('change', () => {
        const value = ssnInput.value.trim();
        if (!value) {
            writeSetting(STORAGE_KEYS.ssn, null);
            updateSsnHint();
            return;
        }
        const ssn = normalizeSsn(value);
        if (ssn) {
            ssnInput.value = ssn;
            writeSetting(STORAGE_KEYS.ssn, ssn);
            updateSsnHint();
        } else {
            updateSsnHint('Enter 12 digits: YYYYMMDDXXXX');
        }
    });

    modeInputs.forEach(input => input.addEventListener('change', () => {
        writeSetting(STORAGE_KEYS.accountMode, getAccountMode());
    }));
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
    let updated = false;

    className = `status ${status}`;
    // Update status class
    if (className != statusElement.className) {
        updated = true;
        statusElement.className = className;
    }
    
    // Update status text
    if (message != statusTextElement.innerHTML) {
        updated = true;
        statusTextElement.innerHTML = message;
    }
    
    // Add fade-in animation
    if (updated) {
        statusElement.classList.add('fade-in');
        setTimeout(() => statusElement.classList.remove('fade-in'), 300);
    }
}

// Handle idle state
function handleIdleState() {
    setSettingsEnabled(true);
    runButton.disabled = false;
    runButton.innerHTML = 'Run sync now';
    hideElement(qrContainer);
    hideElement(spinner);
    hideElement(resultsElement);
}

// Handle processing state
function handleProcessingState() {
    setSettingsEnabled(false);
    runButton.disabled = true;
    runButton.innerHTML = 'Processing...';
    hideElement(qrContainer);
    showElement(spinner, 'flex');
    hideElement(resultsElement);
}

// Handle QR ready state
function handleQRReadyState(qrUrl) {
    setSettingsEnabled(false);
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
    setSettingsEnabled(false);
    runButton.disabled = true;
    runButton.innerHTML = 'Syncing data...';
    hideElement(qrContainer);
    showElement(spinner, 'flex');
    hideElement(resultsElement);
}

// Handle completion state
function handleCompleteState(stats, message) {
    setSettingsEnabled(true);
    runButton.disabled = false;
    runButton.innerHTML = 'Run sync now';
    hideElement(qrContainer);
    hideElement(spinner);
    
    // Show results
    showResults(true, message, stats);
}

// Handle error state
function handleErrorState(message) {
    setSettingsEnabled(true);
    runButton.disabled = false;
    runButton.innerHTML = 'Run sync now';
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

    const options = { account_mode: getAccountMode() };
    const value = ssnInput.value.trim();
    if (value) {
        const ssn = normalizeSsn(value);
        if (!ssn) {
            updateSsnHint('Enter 12 digits: YYYYMMDDXXXX');
            ssnInput.focus();
            return;
        }
        options.ssn = ssn;
    } else if (!serverConfig.ssn_configured) {
        updateSsnHint('Enter your personal identity number to sync');
        ssnInput.focus();
        return;
    }
    
    fetch('/trigger', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(options)
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
    // only show fade if we're actually changing the display value
    if (element.style.display === value) {
        return;
    }
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
