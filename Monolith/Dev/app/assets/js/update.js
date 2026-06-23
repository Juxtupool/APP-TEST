/**
 * Update System - Frontend Logic
 * Handles the dark overlay and update flow
 */

const UpdateOverlay = {
    overlayId: 'update-overlay',
    destroyTimeout: null,

    // Change button text if update available
    setUpdateIndicator(visible) {
        const btn = document.getElementById('btn-check-updates');
        if (btn) {
            if (visible) {
                // Change text and style to indicate update
                btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> Update Available';
                btn.classList.add('update-available-btn'); // defined in CSS
            } else {
                // Revert to default
                btn.innerHTML = '<i class="fa-solid fa-rotate"></i> Check for Updates';
                btn.classList.remove('update-available-btn');
            }
        }
    },

    create() {
        const existing = document.getElementById(this.overlayId);

        // If overlay exists, just revive it
        if (existing) {
            // Cancel any pending destroy
            if (this.destroyTimeout) {
                clearTimeout(this.destroyTimeout);
                this.destroyTimeout = null;
            }
            existing.classList.add('active');
            // Ensure z-index is correct
            existing.style.zIndex = '20000';
            return;
        }

        const overlay = document.createElement('div');
        overlay.id = this.overlayId;
        // Styles now in update-status-modal.css under #update-overlay

        overlay.innerHTML = `
            <div class="update-overlay-container">
                <div class="update-overlay-icon">
                    <i class="fa-solid fa-cloud-arrow-down"></i>
                </div>
                <h2 id="update-title" class="update-overlay-title">Updating...</h2>
                <p id="update-status-text" class="update-overlay-status">Preparing...</p>
                
                <div class="update-progress-track">
                    <div id="update-progress-bar" class="update-progress-bar"></div>
                </div>
                
                <div id="update-actions" class="update-overlay-actions">
                    <button id="btn-restart-now">
                        Restart Now
                    </button>
                    <button id="btn-restart-later">Later</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        // Force reflow
        overlay.offsetHeight;
        overlay.classList.add('active');
    },

    setTitle(text) {
        const el = document.getElementById('update-title');
        if (el) el.innerText = text;
    },

    setStatus(text) {
        const el = document.getElementById('update-status-text');
        if (el) el.innerText = text;
    },

    setProgress(percent) {
        const bar = document.getElementById('update-progress-bar');
        if (bar) bar.style.width = `${percent}%`;
    },

    showRestartButton(onRestart) {
        const actions = document.getElementById('update-actions');
        if (actions) actions.style.display = 'flex';

        document.getElementById('btn-restart-now').onclick = onRestart;
        document.getElementById('btn-restart-later').onclick = () => {
            this.destroy(); // Just close overlay
        };
    },

    destroy() {
        const overlay = document.getElementById(this.overlayId);
        if (overlay) {
            overlay.classList.remove('active');
            this.destroyTimeout = setTimeout(() => {
                overlay.remove();
                this.destroyTimeout = null;
            }, 300);
        }
    }
};

// Main Update Flow
async function startAppUpdate(downloadUrl, version) {
    // Removed native confirm
    // if (!confirm(`An update to version ${version} is available. Download and install now?`)) return;

    UpdateOverlay.create();
    UpdateOverlay.setTitle("Updating Application");
    UpdateOverlay.setStatus("Downloading update package...");
    UpdateOverlay.setProgress(10); // Fake start

    try {
        // 1. Download
        // Note: For now we don't have streaming progress from python to JS for this specific call 
        // unless we add a callback. But download_app_update waits until finished.
        // We can fake progress or use an interval.
        let progress = 10;
        const interval = setInterval(() => {
            progress += 5;
            if (progress > 90) progress = 90;
            UpdateOverlay.setProgress(progress);
        }, 200);

        const res = await pywebview.api.download_app_update(downloadUrl);

        clearInterval(interval);
        UpdateOverlay.setProgress(100);

        if (res.status === 'success') {
            UpdateOverlay.setStatus("Download complete. Ready to install.");
            UpdateOverlay.showRestartButton(async () => {
                UpdateOverlay.setStatus("Restarting application... Hold tight!");
                // 2. Restart
                await pywebview.api.trigger_app_restart();
                // We expect the app to close shortly.
            });
        } else {
            UpdateOverlay.setStatus("Download failed: " + res.message);
            setTimeout(() => UpdateOverlay.destroy(), 3000);
        }

    } catch (e) {
        console.error(e);
        UpdateOverlay.setStatus("Error during update.");
        setTimeout(() => UpdateOverlay.destroy(), 3000);
    }
}


// Firmware Update Logic

// Global callbacks for Python
window.onFlashProgress = (msg, pct) => {
    // Parse message if it comes as stringified JSON
    let statusText = msg;
    try {
        if (typeof msg === 'string' && (msg.startsWith('{') || msg.startsWith('"'))) {
            statusText = JSON.parse(msg);
        }
    } catch (e) { }

    UpdateOverlay.setStatus(statusText);
    if (pct !== undefined && pct !== null) {
        UpdateOverlay.setProgress(pct);
    }
};

window.flashPromiseResolver = null;
window.flashPromiseRejecter = null;

window.onFlashFinished = (success, msg) => {
    let statusText = msg;
    try {
        if (typeof msg === 'string' && (msg.startsWith('{') || msg.startsWith('"'))) {
            statusText = JSON.parse(msg);
        }
    } catch (e) { }

    if (window.flashPromiseResolver && window.flashPromiseRejecter) {
        if (success) {
            window.flashPromiseResolver(statusText);
        } else {
            window.flashPromiseRejecter(new Error(statusText));
        }
        window.flashPromiseResolver = null;
        window.flashPromiseRejecter = null;
    }
};

async function startFirmwareUpdate(downloadUrl) {
    if (!downloadUrl) {
        alert("No firmware download URL found.");
        return;
    }

    // Removed native confirm
    // if (!confirm("About to flash new firmware. Device will disconnect. Continue?")) {
    //    throw new Error("User cancelled");
    // }

    UpdateOverlay.create();
    UpdateOverlay.setTitle("Updating Firmware");
    UpdateOverlay.setStatus("Downloading firmware binary...");
    UpdateOverlay.setProgress(5);

    try {
        // 1. Download
        const res = await pywebview.api.download_firmware_update(downloadUrl);
        if (res.status !== 'success') {
            throw new Error("Download failed: " + res.message);
        }

        const firmwarePath = res.path;
        UpdateOverlay.setStatus("Flashing firmware... DO NOT UNPLUG!");
        UpdateOverlay.setProgress(10);

        // 2. Flash
        await new Promise((resolve, reject) => {
            window.flashPromiseResolver = resolve;
            window.flashPromiseRejecter = reject;

            // Trigger flash (port=null to auto-detect active port)
            pywebview.api.flash_firmware(null, firmwarePath).then(r => {
                if (r.status === 'error') {
                    reject(new Error(r.message));
                }
                // If success, we wait for window.onFlashFinished
            });
        });

        UpdateOverlay.setStatus("Firmware Update Success!");
        UpdateOverlay.setProgress(100);
        await new Promise(r => setTimeout(r, 1500));

        // Hide overlay so next update can start fresh or clean up
        UpdateOverlay.destroy();

        // Close the update status modal if it exists
        const updateStatusModal = document.getElementById('update-status-modal');
        if (updateStatusModal) {
            updateStatusModal.classList.remove('active');
            setTimeout(() => {
                updateStatusModal.style.display = 'none';
            }, 300);
        }

    } catch (e) {
        console.error("Firmware Update Error", e);
        UpdateOverlay.setStatus("Firmware Update Failed: " + e.message);
        // Keep error visible for a bit
        await new Promise(r => setTimeout(r, 4000));
        UpdateOverlay.destroy();
    }
}

// Background Update Check Mechanism
async function checkUpdatesInBackground() {
    // Wait a bit not to block startup
    setTimeout(async () => {
        try {

            // Parallel checks
            const [fwResult, appResult] = await Promise.all([
                pywebview.api.check_firmware_updates().catch(e => ({ status: 'error' })),
                pywebview.api.check_app_updates().catch(e => ({ status: 'error' }))
            ]);

            let hasUpdate = false;

            // Check Firmware
            if (fwResult && fwResult.status === 'success' && fwResult.data && fwResult.data.update_available) {
                hasUpdate = true;
            }

            // Check App
            if (appResult && appResult.status === 'success' && appResult.data && appResult.data.update_available) {
                hasUpdate = true;
            }

            // [DEBUG] Force update indicator to test visibility of NEW BUTTON STYLE
            // hasUpdate = true; // REMOVED DEBUG FORCE

            // Set indicator
            UpdateOverlay.setUpdateIndicator(hasUpdate);

            // If settings page is open, we can also update the version text logic here if needed,
            // but usually the specific page logic handles its own display. 
            // The badge is the global indicator.

        } catch (e) {
            console.error("Background update check failed:", e);
        }
    }, 3000);
}

// Expose to window so other scripts can call it
window.checkUpdatesInBackground = checkUpdatesInBackground;
