/**
 * Update System - Frontend Logic
 * Handles the dark overlay and update flow
 */

const UpdateOverlay = {
    overlayId: 'update-overlay',

    create() {
        // Create overlay if it doesn't exist
        if (document.getElementById(this.overlayId)) return;

        const overlay = document.createElement('div');
        overlay.id = this.overlayId;
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background-color: rgba(18, 18, 18, 0.95);
            backdrop-filter: blur(10px);
            z-index: 9999;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: white;
            opacity: 0;
            transition: opacity 0.3s ease;
        `;

        overlay.innerHTML = `
            <div style="text-align: center; max-width: 500px; padding: 40px;">
                <div style="font-size: 3rem; margin-bottom: 20px; color: #3b82f6;">
                    <i class="fa-solid fa-cloud-arrow-down"></i>
                </div>
                <h2 style="font-size: 2rem; margin-bottom: 10px;">Updating Application</h2>
                <p id="update-status-text" style="color: #a3a3a3; margin-bottom: 30px;">Preparing...</p>
                
                <div class="progress-track" style="
                    width: 100%;
                    height: 6px;
                    background: rgba(255,255,255,0.1);
                    border-radius: 3px;
                    overflow: hidden;
                    margin-bottom: 20px;
                ">
                    <div id="update-progress-bar" style="
                        width: 0%;
                        height: 100%;
                        background: #3b82f6;
                        transition: width 0.3s ease;
                        box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
                    "></div>
                </div>
                
                <div id="update-actions" style="display: none; gap: 10px; justify-content: center;">
                    <button id="btn-restart-now" class="btn-primary" style="
                        padding: 12px 30px; 
                        font-size: 1.1rem;
                        background: linear-gradient(135deg, #10b981, #059669);
                    ">
                        Restart Now
                    </button>
                    <button id="btn-restart-later" class="btn-secondary" style="margin-left: 10px;">Later</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        // Force reflow
        overlay.offsetHeight;
        overlay.style.opacity = '1';
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
            overlay.style.opacity = '0';
            setTimeout(() => overlay.remove(), 300);
        }
    }
};

// Main Update Flow
async function startAppUpdate(downloadUrl, version) {
    if (!confirm(`An update to version ${version} is available. Download and install now?`)) return;

    UpdateOverlay.create();
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
