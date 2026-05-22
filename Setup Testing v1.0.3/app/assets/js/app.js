// Imports removed - loaded via script tags


// Global State
// State variables (currentProfile, profiles, etc.) are now managed by state.js
// which exposes them to window for legacy compatibility.
// In this module (strict mode checks removed), we access them as globals.

// Internal Globals
let flashProgressInterval = null;
// profileSaveTimeout moved to profile_manager.js

// ... (Legacy Icon Map) ...

// --- Profiles ---
// Logic moved to modules/core/profile_manager.js
// Calls are now global: loadProfiles(), switchProfile(), etc.

const legacyIconMap = {
    "No Macro": "System/prohibited-line.svg",
    "Copy": "Document/file-copy-line.svg",
    "Paste": "Document/clipboard-line.svg",
    "Cut": "Design/scissors-cut-line.svg",
    "Select All": "System/checkbox-multiple-line.svg",
    "Undo": "System/reset-left-line.svg",
    "Redo": "System/reset-right-line.svg",
    "Save": "Device/save-line.svg",
    "Find": "System/search-line.svg",
    "Replace": "System/find-replace-line.svg",
    "New Tab": "System/add-line.svg",
    "Close Tab": "System/close-line.svg",
    "Switch Tab": "Arrows/arrow-left-right-line.svg",
    "Refresh": "System/refresh-line.svg",
    "Minimize Window": "System/subtract-line.svg",
    "Restore Windows": "System/reset-left-line.svg",
    "Volume Up": "Media/volume-up-line.svg",
    "Volume Down": "Media/volume-down-line.svg",
    "Mute": "Media/volume-mute-line.svg",
    "Play/Pause": "Media/play-line.svg",
    "Next Track": "Media/skip-forward-line.svg",
    "Previous Track": "Media/skip-back-line.svg"
};



// Initialize
window.addEventListener('DOMContentLoaded', async () => {
    initApp();
});

async function initApp() {
    setupNavigation();
    setupProfileActions();
    setupConnectionToggle();
    setupKeyGrid();
    setupKnobActions();
    setupWindowControls();
    setupSearchBars();
    setupMacroTabs();
    setupSettingsListeners();
    setupThemeSelector();
    setupUpdateChecker();

    // Initial Load
    if (window.pywebview) {
        init();
    } else {
        window.addEventListener('pywebviewready', init);
    }

    // Check for updates (App & Firmware) - Run independently
    if (window.checkUpdatesInBackground) {
        setTimeout(window.checkUpdatesInBackground, 100);
    }
}

function setupNavigation() {
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const pageId = btn.dataset.page;
            showPage(pageId);
        });
    });
}

function setupProfileActions() {
    document.getElementById('profile-select').addEventListener('change', (e) => {
        switchProfile(e.target.value);
    });

    document.getElementById('btn-new-profile').addEventListener('click', createProfile);
    document.getElementById('btn-edit-profile').addEventListener('click', editProfile);
    document.getElementById('btn-delete-profile').addEventListener('click', deleteProfile);

    const btnLinkApp = document.getElementById('btn-link-app');
    if (btnLinkApp) {
        btnLinkApp.addEventListener('click', () => {
            if (!btnLinkApp.disabled) showLinkAppModal();
        });
    }
    updateLinkAppButtonState();
}

function setupConnectionToggle() {
    const toggle = document.getElementById('connection-toggle');
    toggle.addEventListener('click', async () => {
        toggle.disabled = true;
        try {
            if (isConnected) await disconnectSerial();
            else await connectSerial();
        } finally {
            toggle.disabled = false;
        }
    });
}

function setupKeyGrid() {
    document.querySelectorAll('.key-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            selectKey(parseInt(btn.dataset.id));
        });
    });
}

function setupKnobActions() {
    document.getElementById('knob-mode-select').addEventListener('change', (e) => {
        handleKnobModeChange(e.target.value);
    });

    const speedSlider = document.getElementById('knob-speed-slider');
    const speedValue = document.getElementById('knob-speed-value');

    speedSlider.addEventListener('input', (e) => {
        speedValue.innerText = `${e.target.value}x`;
    });

    speedSlider.addEventListener('change', async (e) => {
        const speed = parseInt(e.target.value);
        profiles[currentProfile].knob_speed = speed;
        await pywebview.api.set_knob_speed(speed);
    });

    document.querySelectorAll('.knob-action-card').forEach(row => {
        row.addEventListener('click', () => {
            if (!row.classList.contains('readonly')) {
                selectKnobAction(row.dataset.action);
            }
        });
    });

    document.querySelectorAll('.action-create-macro').forEach(btn => {
        btn.addEventListener('click', () => openMacroEditor());
    });
}

function setupWindowControls() {
    document.getElementById('btn-minimize')?.addEventListener('click', () => {
        pywebview.api.window_minimize();
    });

    document.getElementById('btn-close')?.addEventListener('click', () => {
        pywebview.api.window_close();
    });
}

function setupSearchBars() {
    setupSearch('macro-search-keys', 'search-clear-keys', 'search-count-keys', 'macro-list-legacy', 'macro-list-user');
    setupSearch('macro-search-knob', 'search-clear-knob', 'search-count-knob', 'knob-macro-list-legacy', 'knob-macro-list-user');
}

function setupSearch(inputId, clearBtnId, countId, legacyListId, userListId) {
    const input = document.getElementById(inputId);
    const clearBtn = document.getElementById(clearBtnId);
    const countDisplay = document.getElementById(countId);

    if (!input) return;

    let debounceTimer;
    input.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        if (clearBtn) clearBtn.style.display = query ? "flex" : "none";

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            const countLegacy = filterList(legacyListId, query);
            const countUser = filterList(userListId, query);
            if (countDisplay) {
                countDisplay.innerText = query ? `${countLegacy + countUser} matches` : "";
            }
        }, 150);
    });

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            input.value = "";
            clearBtn.style.display = "none";
            filterList(legacyListId, "");
            filterList(userListId, "");
            if (countDisplay) countDisplay.innerText = "";
            input.focus();
        });
    }
}

function setupMacroTabs() {
    document.querySelectorAll('.macro-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            const group = btn.closest('.macro-tabs');
            const target = btn.dataset.tab;
            const container = btn.closest('.macro-panel');

            if (!group || !container) return; // Ensure elements exist

            group.querySelectorAll('.macro-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            container.querySelectorAll('.macro-tab-content').forEach(c => c.classList.remove('active'));
            const targetContent = container.querySelector(`.macro-tab-content[data-tab="${target}"]`);
            if (targetContent) targetContent.classList.add('active');
        });
    });
}

function setupSettingsListeners() {
    document.getElementById('chk-startup').addEventListener('change', async (e) => {
        await pywebview.api.set_startup_status(e.target.checked);
    });

    document.getElementById('chk-tray').addEventListener('change', async (e) => {
        await pywebview.api.set_tray_status(e.target.checked);
    });

    document.getElementById('btn-reset-defaults').addEventListener('click', async () => {
        const confirmReset = await showConfirm("Reset to Defaults", "Are you sure? This will delete all profiles and macros. This action cannot be undone.", "danger", "Reset Everything");
        if (confirmReset) {
            await pywebview.api.reset_to_defaults();
            window.location.reload();
        }
    });
}

function setupThemeSelector() {
    document.querySelectorAll('.theme-card').forEach(card => {
        card.addEventListener('click', async () => {
            const theme = card.dataset.theme;

            // Visual update
            document.querySelectorAll('.theme-card').forEach(c => c.classList.remove('active'));
            card.classList.add('active');

            applyTheme(theme);
            await pywebview.api.set_theme(theme);
        });
    });
}
function setupUpdateChecker() {
    const btn = document.getElementById('btn-check-updates');
    if (!btn) return;

    btn.addEventListener('click', async () => {
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Checking...';
        btn.disabled = true;

        try {
            const res = await pywebview.api.check_for_updates();
            
            // Check if any updates are actually available
            const firmwareUpdate = res && res.status === 'success' && res.firmware && res.firmware.update_available;
            const appUpdate = res && res.status === 'success' && res.app && res.app.update_available;

            if (firmwareUpdate || appUpdate) {
                // Show modal if updates are found
                showUpdateStatusModal(res.firmware, res.app);
                btn.innerHTML = originalText;
                btn.disabled = false;
            } else {
                // Success but no updates - show green tick inline
                btn.innerHTML = '<i class="fa-solid fa-check" style="color: #4ade80;"></i> Up to Date';
                setTimeout(() => {
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }, 30000);
            }
        } catch (e) {
            console.error('Update check failed:', e);
            // On error, just reset the button
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    });
}


// Show Update Status Modal with simplified design
/**
 * Displays the Update Status Modal with firmware and application update information.
 * Handles the logic for showing/hiding specific update sections based on available data.
 * 
 * @param {Object} firmwareData - Object containing firmware version and update status
 * @param {Object} appData - Object containing application version and update status
 */
function showUpdateStatusModal(firmwareData, appData) {
    const modal = document.getElementById('update-status-modal');
    const subtitle = document.getElementById('update-subtitle');
    const firmwareItem = document.getElementById('firmware-update-item');
    const appItem = document.getElementById('app-update-item');
    const noUpdatesMsg = document.getElementById('no-updates-message');
    const unifiedBtn = document.getElementById('unified-update-btn');
    const btnText = document.getElementById('update-btn-text');

    // Reset visibility
    firmwareItem.style.display = 'none';
    appItem.style.display = 'none';
    noUpdatesMsg.style.display = 'none';
    unifiedBtn.style.display = 'none';

    let firmwareUpdateAvailable = false;
    let appUpdateAvailable = false;

    const currentFirmwareVer = (firmwareData && firmwareData.current_version) ? firmwareData.current_version : "Unknown";
    const currentAppVer = (appData && appData.current_version) ? appData.current_version : "Unknown";

    // Set fallback headers if update checked but nothing found
    if (document.getElementById('firmware-current')) document.getElementById('firmware-current').textContent = `v${currentFirmwareVer}`;
    if (document.getElementById('app-current')) document.getElementById('app-current').textContent = `v${currentAppVer}`;

    // Check firmware (ignore errors, only show if update available)
    if (firmwareData && !firmwareData.error && firmwareData.update_available) {
        firmwareUpdateAvailable = true;
        document.getElementById('firmware-current').textContent = `v${firmwareData.current_version}`;
        document.getElementById('firmware-latest').textContent = `v${firmwareData.latest_version}`;
        firmwareItem.style.display = 'flex';
    }

    // Check app (ignore errors, only show if update available)
    if (appData && !appData.error && appData.update_available) {
        appUpdateAvailable = true;
        document.getElementById('app-current').textContent = `v${appData.current_version}`;
        document.getElementById('app-latest').textContent = `v${appData.latest_version}`;
        appItem.style.display = 'flex';
    }

    // Update subtitle and button based on what's available
    if (firmwareUpdateAvailable && appUpdateAvailable) {
        subtitle.textContent = 'Updates available for firmware and app';
        btnText.textContent = 'Download & Flash';
        unifiedBtn.style.display = 'block';

        // Handle both updates
        unifiedBtn.onclick = async () => {
            unifiedBtn.disabled = true;
            unifiedBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Updating...';

            // Start both updates
            const firmwareUrl = firmwareData.download_url || '';
            try {
                await startFirmwareUpdate(firmwareUrl);
            } catch (e) {
                console.error("Firmware update aborted");
                unifiedBtn.disabled = false;
                unifiedBtn.innerHTML = '<i class="fa-solid fa-download"></i> <span>Download & Flash</span>';
                return;
            }

            const downloadUrl = appData.download_url || appData.zipball_url || '';
            await startAppUpdate(downloadUrl, appData.latest_version);

            unifiedBtn.disabled = false;
            unifiedBtn.innerHTML = '<i class="fa-solid fa-download"></i> <span>Download & Flash</span>';
        };
    } else if (firmwareUpdateAvailable) {
        subtitle.textContent = 'Firmware update available';
        btnText.textContent = 'Update Firmware';
        unifiedBtn.style.display = 'block';
        const firmwareUrl = firmwareData.download_url || '';
        unifiedBtn.onclick = () => startFirmwareUpdate(firmwareUrl);
    } else if (appUpdateAvailable) {
        subtitle.textContent = 'Application update available';
        btnText.textContent = 'Update Application';
        unifiedBtn.style.display = 'block';
        const downloadUrl = appData.download_url || appData.zipball_url || '';
        unifiedBtn.onclick = () => startAppUpdate(downloadUrl, appData.latest_version);
    } else {
        // No updates available
        subtitle.textContent = 'All systems up to date';
        noUpdatesMsg.style.display = 'flex';
    }

    // Show modal with animation
    modal.style.display = 'flex';
    setTimeout(() => modal.classList.add('active'), 10);

    // Setup close handlers
    const closeBtn = document.getElementById('update-status-close');
    const okBtn = document.getElementById('update-status-ok');

    const closeModal = () => {
        modal.classList.remove('active');
        setTimeout(() => modal.style.display = 'none', 300);
    };

    closeBtn.onclick = closeModal;
    okBtn.onclick = closeModal;

    // Close on background click
    modal.onclick = (e) => {
        if (e.target === modal) closeModal();
    };

    // Close on ESC key
    const escHandler = (e) => {
        if (e.key === 'Escape') {
            closeModal();
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);
}




async function init() {
    await loadProfiles();
    await loadSettings();
    // Sync initial profile
    await pywebview.api.set_active_profile(currentProfile);
    // Don't pre-select any key - let user choose

    // Auto-connect silently
    connectSerial(true);

    // Initialize Community Features
    if (typeof initCommunity === 'function') {
        initCommunity();
    }
}

// --- Navigation ---
function showPage(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

    const targetPage = document.getElementById(`page-${pageId}`);
    if (targetPage) targetPage.classList.add('active');

    // Handle Layout: Hide Main Content when on Community/Hub page to allow full width
    const mainContent = document.querySelector('.main-content');
    if (pageId === 'community') {
        if (mainContent) mainContent.style.display = 'none';
        // Ensure community page is visible (it is outside main now)
        if (targetPage) targetPage.style.display = 'flex';
    } else {
        if (mainContent) mainContent.style.display = 'flex';
        // Ensure standard pages are visible (they are inside main)
        // But community page should be hidden
        const communityPage = document.getElementById('page-community');
        if (communityPage) communityPage.style.display = 'none';
    }

    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.querySelector(`.nav-item[data-page="${pageId}"]`).classList.add('active');

    const titles = {
        'keys': 'Key Configuration',
        'knob': 'Knob Configuration',
        'settings': 'Settings',
        'community': 'Macro Hub'
    };
    const titleEl = document.getElementById('page-title');
    if (titleEl) titleEl.innerText = titles[pageId] || 'OVERCONTROL';

    // Load community macros when navigating to that page
    if (pageId === 'community') {
        if (typeof loadCommunityMacros === 'function') {
            loadCommunityMacros();
        }
    }

    // Clear selections on page switch
    currentControl = null;
    document.querySelectorAll('.key-btn').forEach(b => b.classList.remove('selected'));
    document.querySelectorAll('.knob-action-card').forEach(r => r.classList.remove('selected'));
}

// --- Profiles ---
// Logic moved to modules/core/profile_manager.js
// Calls are now global: loadProfiles(), switchProfile(), etc.

// Note: updateUIForProfile remains here as it is deeply coupled with DOM elements in this file.

function updateUIForProfile() {
    document.getElementById('active-profile-name').innerText = currentProfile;
    // Update Community Page Profile Display
    const commProfile = document.getElementById('active-profile-name-community');
    if (commProfile) commProfile.innerText = currentProfile;

    document.getElementById('profile-select').value = currentProfile;
    updateMacroList();

    // Sync Custom Profile Dropdown
    const profileLabel = document.getElementById('profile-label');
    const profileDropdownItems = document.querySelectorAll('#profile-dropdown-menu .dropdown-item');

    if (profileLabel && profileDropdownItems) {
        profileLabel.innerText = currentProfile;
        profileDropdownItems.forEach(item => {
            if (item.dataset.value === currentProfile) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    // Update Link App Button State for the new profile
    updateLinkAppButtonState();

    // Update app icon display
    updateProfileAppIcon();

    const profileData = profiles[currentProfile];
    if (!profileData.keys) profileData.keys = {};
    if (!profileData.knobs) profileData.knobs = {};

    // Update Keys
    document.querySelectorAll('.key-btn').forEach(btn => {
        const id = btn.dataset.id;
        const macroName = profileData.keys[id];
        const label = btn.querySelector('.key-label');
        const keyCap = btn.querySelector('.key-cap');

        if (macroName) {
            label.innerText = macroName;

            // Check for icon
            let customIcon = null;
            if (profiles[currentProfile].macros && profiles[currentProfile].macros[macroName]) {
                customIcon = profiles[currentProfile].macros[macroName].icon;
            }

            if (customIcon) {
                keyCap.innerHTML = `<img src="${customIcon}">`;
            } else if (legacyIconMap[macroName]) {
                keyCap.innerHTML = `<img src="icons/${legacyIconMap[macroName]}">`;
            } else {
                keyCap.innerHTML = `<i class="fa-solid fa-bolt"></i>`;
            }
        } else {
            label.innerText = `K${id}`;
            keyCap.innerHTML = `<i class="fa-solid fa-plus"></i>`;
        }
    });

    // Update Knob
    const knobMode = profileData.knob_mode || "Standard";
    const knobSpeed = profileData.knob_speed || 1;
    const modeSelect = document.getElementById('knob-mode-select');
    const modeDesc = document.getElementById('knob-mode-desc');

    // Update Speed Slider
    document.getElementById('knob-speed-slider').value = knobSpeed;
    document.getElementById('knob-speed-value').innerText = `${knobSpeed}x`;

    // Select correct value
    modeSelect.value = knobMode;

    // Sync Custom Dropdown UI
    const knobLabel = document.getElementById('knob-mode-label');
    const knobDropdownItems = document.querySelectorAll('#knob-mode-dropdown .dropdown-item');

    if (knobLabel && knobDropdownItems) {
        // Find matching item text
        let matchedText = knobMode;
        knobDropdownItems.forEach(item => {
            if (item.dataset.value === knobMode) {
                item.classList.add('active');
                matchedText = item.innerText;
            } else {
                item.classList.remove('active');
            }
        });
        knobLabel.innerText = matchedText;
    }

    const cards = document.querySelectorAll('.knob-action-card');

    // Clear previous states
    cards.forEach(card => card.classList.remove('readonly', 'selected'));

    if (knobMode === "Custom") {
        modeDesc.innerText = "Custom Mode: Assign any macro to knob actions.";

        cards.forEach(card => {
            const action = card.dataset.action;
            const macroName = profileData.knobs[action];
            const display = card.querySelector('.assigned-macro');
            display.innerText = macroName || "None";
            display.style.opacity = "1";
        });
    } else if (knobMode === "Timeline Scrubber") {
        modeDesc.innerText = "Timeline Scrubber: Frame-by-frame navigation for video editing.";

        cards.forEach(card => {
            const action = card.dataset.action;
            const macroName = profileData.knobs[action];
            const display = card.querySelector('.assigned-macro');
            display.innerText = macroName || "None";
            display.style.opacity = "1";
        });
    } else {
        // Read-only modes
        cards.forEach(card => card.classList.add('readonly'));

        if (knobMode === "Standard") {
            modeDesc.innerText = "Standard Preset: Volume Control.";

            // Hardcode display for visual feedback
            document.querySelector('.knob-action-card[data-action="knob_rotate_left"] .assigned-macro').innerText = "Volume Down";
            document.querySelector('.knob-action-card[data-action="knob_rotate_right"] .assigned-macro').innerText = "Volume Up";
            document.querySelector('.knob-action-card[data-action="knob_press"] .assigned-macro').innerText = "Mute";

        } else if (knobMode.includes("Alt+Tab")) {
            modeDesc.innerText = "App Switcher: Rotate to navigate apps, stop to select.";

            document.querySelector('.knob-action-card[data-action="knob_rotate_left"] .assigned-macro').innerText = "Prev App";
            document.querySelector('.knob-action-card[data-action="knob_rotate_right"] .assigned-macro').innerText = "Next App";
            document.querySelector('.knob-action-card[data-action="knob_press"] .assigned-macro').innerText = "Select";

        } else {
            modeDesc.innerText = "Window Switcher: Instant window switching.";

            document.querySelector('.knob-action-card[data-action="knob_rotate_left"] .assigned-macro').innerText = "Prev Window";
            document.querySelector('.knob-action-card[data-action="knob_rotate_right"] .assigned-macro').innerText = "Next Window";
            document.querySelector('.knob-action-card[data-action="knob_press"] .assigned-macro').innerText = "-";
        }
    }

    // Update Macro List
    updateMacroList();
}

// --- Knob Mode Handling ---
async function handleKnobModeChange(mode) {
    // Update knob mode via API
    await pywebview.api.set_knob_mode(mode);

    // Update local state immediately for UI responsiveness
    profiles[currentProfile].knob_mode = mode;

    updateUIForProfile();
}

// --- Link App Button State ---
async function updateLinkAppButtonState(forceState = null) {
    const btn = document.getElementById('btn-link-app');
    if (!btn) return;

    // Check if pywebview is available
    if (!window.pywebview || !window.pywebview.api) {
        btn.disabled = true;
        btn.style.opacity = '0.5';
        btn.style.cursor = 'not-allowed';
        return;
    }

    btn.disabled = false;
    btn.style.opacity = '1';
    btn.style.cursor = 'pointer';

    // Optimistic Update
    if (forceState !== null) {
        if (forceState) {
            btn.classList.add('linked');
        } else {
            btn.classList.remove('linked');
        }
        return;
    }

    // Use global profiles object for state (refreshed by loadProfiles)
    const profileData = profiles[currentProfile];
    if (profileData && profileData.linked_apps && profileData.linked_apps.length > 0) {
        btn.classList.add('linked');
    } else {
        btn.classList.remove('linked');
    }
}

// --- Profile App Icon Display ---
async function updateProfileAppIcon() {
    const iconEl = document.getElementById('profile-app-icon');
    if (!iconEl) {
        console.error("Profile app icon element not found");
        return;
    }

    try {
        // Check if current profile has linked apps
        const profileData = profiles[currentProfile];

        const linkedApps = profileData.linked_apps || [];

        if (linkedApps.length > 0) {
            // Get icon for the first linked app
            const appName = linkedApps[0];

            const result = await pywebview.api.get_app_icon(appName);

            if (result.status === 'success' && result.icon) {
                iconEl.src = result.icon;
                iconEl.title = `Linked to ${appName}`;
                iconEl.style.display = 'inline';
            } else {
                console.warn("Icon fetch success but no icon data or status error");
                iconEl.style.display = 'none';
            }
        } else {
            iconEl.style.display = 'none';
        }
    } catch (e) {
        console.error('Error updating profile app icon:', e);
        iconEl.style.display = 'none';
    }
}


async function loadSettings() {
    try {
        const startup = await pywebview.api.get_startup_status();
        document.getElementById('chk-startup').checked = startup.enabled;

        const tray = await pywebview.api.get_tray_status();
        document.getElementById('chk-tray').checked = tray.enabled;

        // Load Saved Custom Colors
        await loadSavedAccentColors();

        // Load Accent Color
        try {
            const colorRes = await pywebview.api.get_accent_color();
            if (colorRes.status === "success" && colorRes.accent_color) {
                applyAccentColor(colorRes.accent_color);

                // Update picker and presets
                const picker = document.getElementById('accent-color-picker');
                if (picker) picker.value = colorRes.accent_color;

                document.querySelectorAll('.color-preset').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.color === colorRes.accent_color);
                });
            }
        } catch (e) {
            console.error("Error loading accent color", e);
        }

        // Initialize Accent Color Listeners
        initAccentColorListeners();

        // Load firmware version if connected
        try {
            const res = await pywebview.api.get_firmware_version();
            if (res.status === 'success') {
                updateFirmwareVersionDisplay(res.version);
            }
        } catch (e) {
            console.error("Error loading firmware version:", e);
            const el = document.getElementById('firmware-version-display');
            if (el) el.innerText = 'Firmware: Error';
        }

        // Load App Version
        try {
            const res = await pywebview.api.get_app_version();
            if (res.status === 'success') {
                const el = document.getElementById('app-version-display');
                if (el) el.innerText = `App: v${res.version}`;
            }
        } catch (e) {
            console.error("Error loading app version:", e);
        }
    } catch (e) {
        console.error("Error loading settings:", e);
    }
}

async function loadSavedAccentColors() {
    try {
        const res = await pywebview.api.get_saved_colors();
        if (res.status === "success" && res.colors) {
            const addButton = document.getElementById('btn-add-accent');
            const container = document.querySelector('.color-presets');

            // Remove existing custom buttons (optional, to avoid dupes on reload)
            document.querySelectorAll('.color-preset.custom-saved').forEach(el => el.remove());

            res.colors.forEach(color => {
                createSavedColorButton(color, container, addButton);
            });

            // Check initial limit
            if (res.colors.length >= 10) {
                addButton.style.display = 'none';
            } else {
                addButton.style.display = 'flex';
            }
        }
    } catch (e) {
        console.error("Error loading saved colors", e);
    }
}

function createSavedColorButton(color, container, addButton) {
    const wrapper = document.createElement('div');
    wrapper.className = 'color-preset-wrapper';

    const btn = document.createElement('button');
    btn.className = 'color-preset custom-saved';
    btn.dataset.color = color;
    btn.style.backgroundColor = color;

    btn.addEventListener('click', () => {
        setAccentColor(color);
    });

    // Edit Pencil
    const editBtn = document.createElement('div');
    editBtn.className = 'preset-edit-icon';
    editBtn.innerHTML = '<i class="fa-solid fa-pencil"></i>';
    editBtn.title = "Edit Color";

    // Hidden picker for editing
    const slotPicker = document.createElement('input');
    slotPicker.type = 'color';
    // Style to overlay the edit button so popup appears near it
    slotPicker.style.position = 'absolute';
    slotPicker.style.top = '0';
    slotPicker.style.left = '0';
    slotPicker.style.width = '100%';
    slotPicker.style.height = '100%';
    slotPicker.style.opacity = '0';
    slotPicker.style.cursor = 'pointer';
    slotPicker.value = color;

    // Append picker INSIDE editBtn so clicking editBtn clicks picker
    editBtn.style.position = 'absolute'; // Ensure relative context works if needed, but preset-edit-icon is absolute
    // actually preset-edit-icon is absolute.

    // We append slotPicker to editBtn
    editBtn.appendChild(slotPicker);

    // No need for explicit click listener on editBtn anymore since input covers it
    // But we need to stop propagation on the input click so it doesn't trigger the circle click?
    slotPicker.addEventListener('click', (e) => {
        e.stopPropagation();
    });

    slotPicker.addEventListener('change', async (e) => {
        const newColor = e.target.value.trim().toLowerCase();
        const oldColor = btn.dataset.color;

        // Update Backend
        await pywebview.api.remove_saved_color(oldColor);
        await pywebview.api.add_saved_color(newColor);

        // Update DOM
        btn.style.backgroundColor = newColor;
        btn.dataset.color = newColor;
        slotPicker.value = newColor;

        // If active, update theme
        if (btn.classList.contains('active')) {
            setAccentColor(newColor);
        }
    });

    // Right click delete
    wrapper.addEventListener('contextmenu', async (e) => {
        e.preventDefault();
        if (confirm("Delete this saved color?")) {
            await pywebview.api.remove_saved_color(btn.dataset.color);
            wrapper.remove();

            // Re-show add button if below limit
            const count = document.querySelectorAll('.color-preset.custom-saved').length;
            if (count < 10) {
                addButton.style.display = 'flex';
            }
        }
    });

    wrapper.appendChild(btn);
    wrapper.appendChild(editBtn);
    // wrapper.appendChild(slotPicker); // Moved inside editBtn

    container.insertBefore(wrapper, addButton);
}

function applyAccentColor(color) {
    document.documentElement.style.setProperty('--accent-color', color);
    document.documentElement.style.setProperty('--accent-hover', color);

    const rgb = hexToRgb(color);
    document.documentElement.style.setProperty('--accent-rgb', rgb);
    document.documentElement.style.setProperty('--accent-glow', `rgba(${rgb}, 0.5)`);
}

function hexToRgb(hex) {
    // Expand shorthand form (e.g. "03F") to full form (e.g. "0033FF")
    var shorthandRegex = /^#?([a-f\d])([a-f\d])([a-f\d])$/i;
    hex = hex.replace(shorthandRegex, function (m, r, g, b) {
        return r + r + g + g + b + b;
    });

    var result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}` : "37, 99, 235";
}

function initAccentColorListeners() {
    // Preset Buttons (exclude add-new)
    document.querySelectorAll('.color-preset:not(.add-new)').forEach(btn => {
        btn.addEventListener('click', () => {
            const color = btn.dataset.color;
            if (color) setAccentColor(color);
        });
    });

    // Add Button
    const addBtn = document.getElementById('btn-add-accent');
    if (addBtn) {
        // Create hidden picker for the Add button
        const addPicker = document.createElement('input');
        addPicker.type = 'color';
        addPicker.style.position = 'absolute';
        addPicker.style.top = '0';
        addPicker.style.left = '0';
        addPicker.style.width = '100%';
        addPicker.style.height = '100%';
        addPicker.style.opacity = '0';
        addPicker.style.cursor = 'pointer';

        // Ensure relative positioning on the button so absolute child works
        addBtn.style.position = 'relative';
        addBtn.appendChild(addPicker);

        addPicker.addEventListener('change', async (e) => {
            let color = e.target.value;
            // Reset value so same color can be selected again if needed (optional)

            if (!color) return;
            color = color.trim().toLowerCase(); // Normalize

            // Safety check
            if (addBtn.style.display === 'none') return;


            // Save to backend
            const result = await pywebview.api.add_saved_color(color);

            if (result.status === "success") {
                // Check if button already exists in custom list to avoid duplicates in UI
                const existing = Array.from(document.querySelectorAll('.color-preset.custom-saved'))
                    .find(btn => btn.dataset.color === color);

                if (!existing) {
                    // Add to UI
                    const container = document.querySelector('.color-presets');
                    createSavedColorButton(color, container, addBtn);

                    // Hide add button if limit reached
                    if (document.querySelectorAll('.color-preset.custom-saved').length >= 10) {
                        addBtn.style.display = 'none';
                    }
                }
                // Select it
                setAccentColor(color);
            }
        });
    }

    // Old Color Picker removed
}

async function setAccentColor(color) {
    applyAccentColor(color);

    // Update UI selection
    const picker = document.getElementById('accent-color-picker');
    if (picker) picker.value = color;

    document.querySelectorAll('.color-preset').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.color === color);
    });

    await pywebview.api.set_accent_color(color);
}

function updateFirmwareVersionDisplay(version) {
    const display = document.getElementById('firmware-version-display');
    if (display) {
        if (!version || version === 'Unknown') {
            display.innerText = 'Firmware: Unknown';
        } else {
            display.innerText = `Firmware: v${version}`;
        }
    }
}

// --- Firmware Update ---

// --- Firmware Update ---
async function startFirmwareUpdate() {
    // console.log("=== FIRMWARE UPDATE STARTED ===");  // [DEBUG - Disabled in production]

    try {
        // 1. Check connections
        // console.log("Step 1: Checking serial ports...");  // [DEBUG - Disabled in production]
        const ports = await pywebview.api.get_serial_ports();
        // console.log("Found ports:", ports);  // [DEBUG - Disabled in production]

        if (ports.length === 0) {
            // console.log("No ports found, showing alert");  // [DEBUG - Disabled in production]
            await showAlert("Firmware Update", "No device found. Please connect your device.");
            return;
        }

        // Let user select port if multiple available
        let port;
        if (ports.length === 1) {
            port = ports[0][0];
        } else {
            // Show port selection dialog
            const portOptions = ports.map((p, i) => `${i + 1}. ${p[0]} - ${p[1]}`).join('\n');
            const portChoice = await showPrompt(
                "Select Port",
                `Multiple ports found:\n${portOptions}\n\nEnter port number:`,
                "1"
            );
            if (!portChoice) return;

            const portIndex = parseInt(portChoice) - 1;
            if (portIndex < 0 || portIndex >= ports.length) {
                await showAlert("", "Invalid port selection", "danger");
                return;
            }
            port = ports[portIndex][0];
        }
        // console.log("Selected port:", port);  // [DEBUG - Disabled in production]

        // 2. Select File
        // console.log("Step 2: Opening file dialog...");  // [DEBUG - Disabled in production]
        const fileRes = await pywebview.api.select_firmware_file();
        // console.log("File selection result:", fileRes);  // [DEBUG - Disabled in production]

        if (fileRes.status !== "success") {
            // console.log("File selection cancelled");  // [DEBUG - Disabled in production]
            return;
        }

        const filePath = fileRes.path;
        // console.log("Selected file:", filePath);  // [DEBUG - Disabled in production]

        // Validate file type
        const validExtensions = ['.hex', '.bin', '.ino.hex'];
        const hasValidExtension = validExtensions.some(ext =>
            filePath.toLowerCase().endsWith(ext)
        );

        if (!hasValidExtension) {
            await showAlert(
                "Invalid File",
                `Please select a valid firmware file (${validExtensions.join(', ')})`
            );
            return;
        }

        // 3. Confirm
        // console.log("Step 3: Showing confirmation dialog...");  // [DEBUG - Disabled in production]
        const confirm = await showConfirm("Update Firmware", `Ready to flash to ${port}?\nDo not disconnect device.`);
        // console.log("User confirmed:", confirm);  // [DEBUG - Disabled in production]

        if (!confirm) {
            // console.log("User cancelled confirmation");  // [DEBUG - Disabled in production]
            return;
        }

        // console.log("Step 4: Showing progress modal...");  // [DEBUG - Disabled in production]
        // 4. Show progress modal (Before disconnecting)
        Dialog.show({ title: "Updating Firmware...", message: "Disconnecting device...", hasInput: false });
        // console.log("Progress modal shown");  // [DEBUG - Disabled in production]

        // Force hide buttons
        Dialog.btnOk.style.display = "none";
        Dialog.btnCancel.style.display = "none";
        // console.log("Buttons hidden");  // [DEBUG - Disabled in production]

        // Show Progress Bar
        const progContainer = document.getElementById('generic-modal-progress-container');
        const progBar = document.getElementById('generic-modal-progress-bar');
        if (progContainer) {
            progContainer.style.display = "block";
            // console.log("Progress container displayed");  // [DEBUG - Disabled in production]
        }
        if (progBar) {
            progBar.style.width = "0%";
            // console.log("Progress bar initialized to 0%");  // [DEBUG - Disabled in production]
        }

        // 5. Disconnect serial
        // console.log("Step 5: Disconnecting serial...");  // [DEBUG - Disabled in production]
        await disconnectSerial();
        // console.log("Serial disconnected");  // [DEBUG - Disabled in production]

        // 6. Update status
        // console.log("Step 6: Updating status message...");  // [DEBUG - Disabled in production]
        const msgEl = document.getElementById('generic-modal-message');
        if (msgEl) {
            msgEl.innerText = "Initializing Flash...";
            // console.log("Status updated to: Initializing Flash...");  // [DEBUG - Disabled in production]
        }

        // 7. Start simulated progress animation
        // console.log("Step 7: Starting simulated progress...");  // [DEBUG - Disabled in production]
        startSimulatedProgress();

        // 8. Start Flash
        // console.log("Step 8: Calling flash_firmware API...");  // [DEBUG - Disabled in production]
        const result = await pywebview.api.flash_firmware(port, filePath);
        // console.log("Flash firmware result:", result);  // [DEBUG - Disabled in production]

        if (result.status === "error") {
            console.error("Flash returned error:", result.message);
            window.onFlashFinished(false, result.message);
        } else {
            // console.log("Flash started successfully");  // [DEBUG - Disabled in production]
        }
    } catch (e) {
        console.error("=== FIRMWARE UPDATE EXCEPTION ===");
        console.error("Error type:", e.constructor.name);
        console.error("Error message:", e.message);
        console.error("Error stack:", e.stack);
        window.onFlashFinished(false, "Error: " + e.message);
    }
}

// Simulated progress animation
function startSimulatedProgress() {
    const msgEl = document.getElementById('generic-modal-message');
    const progBar = document.getElementById('generic-modal-progress-bar');

    let progress = 0;
    const duration = 30000; // Simulate 30 seconds total
    const interval = 100; // Update every 100ms
    const increment = (95 / (duration / interval)); // Go to 95%, save 5% for actual completion

    if (flashProgressInterval) {
        clearInterval(flashProgressInterval);
    }

    flashProgressInterval = setInterval(() => {
        progress += increment;

        if (progress >= 95) {
            progress = 95; // Cap at 95% until actual completion
            clearInterval(flashProgressInterval);
            flashProgressInterval = null;
        }

        if (progBar) {
            progBar.style.width = `${Math.floor(progress)}%`;
        }

        if (msgEl) {
            msgEl.innerText = `Flashing firmware... ${Math.floor(progress)}%`;
        }
    }, interval);
}

window.onFlashProgress = (message) => {
    // Backend just signals start - frontend handles animation
    // console.log("Flash progress:", message);  // [DEBUG - Disabled in production]
};

window.onFlashFinished = (success, message) => {
    // Stop simulated progress
    if (flashProgressInterval) {
        clearInterval(flashProgressInterval);
        flashProgressInterval = null;
    }

    const msgEl = document.getElementById('generic-modal-message');
    const titleEl = document.getElementById('generic-modal-title');
    const progContainer = document.getElementById('generic-modal-progress-container');
    const progBar = document.getElementById('generic-modal-progress-bar');
    const icon = document.querySelector('.generic-modal-icon');

    if (success) {
        // Animate to 100% before hiding
        if (progBar) {
            progBar.style.width = "100%";
            if (msgEl) msgEl.innerText = "Flashing firmware... 100%";
        }

        // Wait a moment to show 100%, then show success
        setTimeout(() => {
            // Hide progress bar and show success message with checkmark
            if (progContainer) progContainer.style.display = "none";

            titleEl.innerText = "";
            titleEl.style.display = "none";
            if (titleEl.parentElement) titleEl.parentElement.style.display = "none";

            msgEl.innerText = "Firmware updated Successfully";

            // Force center alignment with inline styles
            msgEl.style.textAlign = "center";

            // Show success checkmark icon and lower it
            if (icon) {
                icon.style.display = "block";
                icon.style.marginTop = "60px"; // Center the tick vertically
                icon.innerHTML = '<i class="fa-solid fa-check-circle"></i>';
            }

            // Add success styling
            Dialog.modal.classList.remove('modal-type-danger');
            Dialog.modal.classList.add('modal-type-success');

            // Restore OK button
            Dialog.btnOk.style.display = "initial";
            Dialog.btnCancel.style.display = "none";

            // Auto-reconnect after delay
            setTimeout(() => {
                connectSerial(true);
            }, 2000);
        }, 500); // Wait 500ms to show 100%
    } else {
        // Show error state
        if (progContainer) progContainer.style.display = "none";

        titleEl.innerText = "Error";
        msgEl.innerText = message;

        // Show error icon
        if (icon) {
            icon.style.display = "block";
            icon.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';
        }

        Dialog.modal.classList.remove('modal-type-success');
        Dialog.modal.classList.add('modal-type-danger');

        // Restore buttons
        Dialog.btnOk.style.display = "initial";
        Dialog.btnCancel.style.display = "none";
    }
};


// --- Selection ---
function selectKey(id) {
    currentControl = { type: "key", id: id };

    document.querySelectorAll('.key-btn').forEach(b => b.classList.remove('selected'));
    document.querySelector(`.key-btn[data-id="${id}"]`).classList.add('selected');

    // Deselect knob
    document.querySelectorAll('.knob-action-card').forEach(r => r.classList.remove('selected'));
}

function selectKnobAction(action) {
    currentControl = { type: "knob", id: action };

    document.querySelectorAll('.knob-action-card').forEach(r => r.classList.remove('selected'));
    document.querySelector(`.knob-action-card[data-action="${action}"]`).classList.add('selected');

    // Deselect keys
    document.querySelectorAll('.key-btn').forEach(b => b.classList.remove('selected'));

    // Trigger appropriate knob animation based on action
    const knobVisual = document.querySelector('.knob-visual-large');
    if (knobVisual) {
        // Remove any existing animation classes
        knobVisual.classList.remove('rotating-left', 'rotating-right', 'rotating-press');

        // Add the correct animation based on action
        if (action === 'knob_rotate_left') {
            knobVisual.classList.add('rotating-left');
            setTimeout(() => knobVisual.classList.remove('rotating-left'), 500);
        } else if (action === 'knob_rotate_right') {
            knobVisual.classList.add('rotating-right');
            setTimeout(() => knobVisual.classList.remove('rotating-right'), 500);
        } else if (action === 'knob_press') {
            knobVisual.classList.add('rotating-press');
            setTimeout(() => knobVisual.classList.remove('rotating-press'), 300);
        }
    }
}

function updateMacroList() {
    // Render Keys Page Lists
    renderSpecificMacroList('macro-list-legacy', 'macro-list-user');
    // Render Knob Page Lists
    renderSpecificMacroList('knob-macro-list-legacy', 'knob-macro-list-user');
}

function renderSpecificMacroList(legacyId, userId) {
    const listLegacy = document.getElementById(legacyId);
    const listUser = document.getElementById(userId);

    if (!listLegacy || !listUser) return;

    listLegacy.innerHTML = '';
    listUser.innerHTML = '';

    const systemMacros = [
        "No Macro",
        // Clipboard
        "Copy",
        "Paste",
        "Cut",
        "Select All",
        // Editing
        "Undo",
        "Redo",
        "Save",
        "Find",
        "Replace",
        // Navigation
        "New Tab",
        "Close Tab",
        "Switch Tab",
        "Refresh",
        // Window Management
        "Minimize Window",
        "Restore Windows",
        // Media
        "Volume Up",
        "Volume Down",
        "Mute",
        "Play/Pause",
        "Next Track",
        "Previous Track"
    ];
    if (!profiles[currentProfile]) {
        console.warn("Profile not found:", currentProfile);
        return;
    }
    const customMacros = Object.keys(profiles[currentProfile].macros || {});

    // -- LEGACY TAB CONTENT --
    systemMacros.forEach(macroName => {
        const item = document.createElement('div');
        item.className = 'macro-item';
        item.setAttribute('role', 'button');
        item.setAttribute('tabindex', '0');
        item.setAttribute('aria-label', `Assign ${macroName} macro`);

        if (legacyIconMap[macroName]) {
            item.innerHTML = `<img src="icons/${legacyIconMap[macroName]}" style="width: 20px; height: 20px; object-fit: contain; filter: invert(1);"> <span>${macroName}</span>`;
        } else {
            // Fallback
            item.innerHTML = `<i class="fa-solid fa-bolt"></i> <span>${macroName}</span>`;
        }

        item.addEventListener('click', () => assignMacro(macroName));

        // Keyboard support
        item.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                assignMacro(macroName);
            }
        });

        listLegacy.appendChild(item);
    });

    // -- USER TAB CONTENT --
    if (customMacros.length === 0) {
        // Show empty state
        const emptyState = document.createElement('div');
        emptyState.className = 'empty-state';
        emptyState.innerHTML = `
            <i class="fa-solid fa-keyboard"></i>
            <h4>No custom macros yet</h4>
            <p>Click "New Macro" below to create one</p>
        `;
        listUser.appendChild(emptyState);
    } else {
        // List Custom Macros
        customMacros.forEach(macroName => {
            const macroData = (profiles[currentProfile] && profiles[currentProfile].macros) ? profiles[currentProfile].macros[macroName] : null;
            const item = document.createElement('div');
            item.className = 'macro-item';
            item.setAttribute('role', 'button');
            item.setAttribute('tabindex', '0');
            item.setAttribute('aria-label', `Assign ${macroName} macro`);

            // Icon logic
            let iconHtml = '<i class="fa-solid fa-keyboard"></i>';
            if (macroData && macroData.icon) {
                iconHtml = `<img src="${macroData.icon}" style="width: 20px; height: 20px; object-fit: contain; filter: invert(1);">`;
            } else if (macroData && macroData.type === 'launch') {
                iconHtml = '<i class="fa-solid fa-rocket"></i>';
            } else if (macroData && macroData.type === 'command') {
                iconHtml = '<i class="fa-solid fa-terminal"></i>';
            }

            // Item content wrapper for alignment
            const content = document.createElement('div');
            content.style.display = 'flex';
            content.style.alignItems = 'center';
            content.style.gap = '10px';
            content.style.flex = '1';
            content.innerHTML = `${iconHtml} <span>${macroName}</span>`;
            item.appendChild(content);

            // Actions
            const actions = document.createElement('div');
            actions.className = 'macro-actions';

            // Edit Btn
            const editBtn = document.createElement('button');
            editBtn.className = 'macro-action-btn';
            editBtn.innerHTML = '<i class="fa-solid fa-pen"></i>';
            editBtn.title = "Edit";
            editBtn.setAttribute('aria-label', `Edit ${macroName}`);
            editBtn.onclick = (e) => {
                e.stopPropagation();
                openMacroEditor(macroName);
            };

            // Delete Btn
            const delBtn = document.createElement('button');
            delBtn.className = 'macro-action-btn delete';
            delBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
            delBtn.title = "Delete";
            delBtn.setAttribute('aria-label', `Delete ${macroName}`);
            delBtn.onclick = (e) => {
                e.stopPropagation();
                deleteMacro(macroName);
            };

            actions.appendChild(editBtn);
            actions.appendChild(delBtn);
            item.appendChild(actions);

            // Assign on click (body)
            item.addEventListener('click', () => assignMacro(macroName));

            // Keyboard support
            item.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    assignMacro(macroName);
                }
            });

            listUser.appendChild(item);
        });
    }
}

async function assignMacro(macroName) {
    if (!currentControl) return;

    const profileData = profiles[currentProfile];
    if (!profileData) return;

    // If "No Macro", we actually remove the key from the dictionary
    if (macroName === "No Macro") {
        if (currentControl.type === "key") {
            delete profileData.keys[currentControl.id];
        } else if (currentControl.type === "knob") {
            delete profileData.knobs[currentControl.id];
        }
    } else {
        if (currentControl.type === "key") {
            profileData.keys[currentControl.id] = macroName;
        } else if (currentControl.type === "knob") {
            profileData.knobs[currentControl.id] = macroName;
        }
    }

    await saveProfiles();
    updateUIForProfile();
}

async function deleteMacro(macroName) {
    const confirmDelete = await showConfirm("Delete Macro", `Delete macro "${macroName}"?`, "danger", "Delete");
    if (confirmDelete) {
        if (profiles[currentProfile] && profiles[currentProfile].macros && profiles[currentProfile].macros[macroName]) {
            delete profiles[currentProfile].macros[macroName];

            // Clean up assignments
            const p = profiles[currentProfile];
            // Keys
            Object.keys(p.keys).forEach(k => {
                if (p.keys[k] === macroName) delete p.keys[k];
            });
            // Knobs
            Object.keys(p.knobs).forEach(k => {
                if (p.knobs[k] === macroName) delete p.knobs[k];
            });

            await saveProfiles();
            updateUIForProfile();
        }
    }
}

// --- Serial ---
async function connectSerial(silent = false) {
    const ports = await pywebview.api.get_serial_ports();
    if (ports.length === 0) {
        if (!silent) await showAlert("Connection", "No ports found");
        setConnected(false);
        return;
    }

    // Auto connect to first port for now
    const port = ports[0][0];
    const result = await pywebview.api.connect_serial(port);

    if (result.connected) {
        setConnected(true, port);
    } else {
        if (!silent) await showAlert("Connection", "Failed to connect");
        setConnected(false);
    }
}

async function disconnectSerial() {
    await pywebview.api.disconnect_serial();
    setConnected(false);
}

// Firmware version callback
window.onFirmwareVersion = (version) => {
    // console.log("Firmware version received:", version);  // [DEBUG - Disabled in production]
    updateFirmwareVersionDisplay(version);
};

function setConnected(connected, portName = "") {
    isConnected = connected;
    const toggle = document.getElementById('connection-toggle');
    const dot = document.querySelector('.status-dot');

    if (connected) {
        toggle?.classList.add('connected');
        dot?.classList.add('connected');
    } else {
        toggle?.classList.remove('connected');
        dot?.classList.remove('connected');
    }
}

// --- Macro Editor ---
const macroModal = document.getElementById('macro-editor-modal');
const btnSaveMacro = document.getElementById('btn-save-macro');
const btnCloseModal = document.querySelectorAll('.close-modal');
const btnRecordToggle = document.getElementById('btn-record-toggle');
const btnClearMacro = document.getElementById('btn-clear-macro');
const keysDisplay = document.getElementById('keys-display');

const btnBrowseFile = document.getElementById('btn-browse-file');

// Modal Tabs Logic
document.querySelectorAll('.modal-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        // Remove active class
        document.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.modal-tab-content').forEach(c => c.classList.remove('active'));

        // Add active class
        tab.classList.add('active');
        const targetId = `modal-tab-${tab.dataset.tab}`;
        document.getElementById(targetId).classList.add('active');
    });
});

btnBrowseFile.addEventListener('click', async () => {
    try {
        const result = await pywebview.api.browse_file_or_app();
        if (result.status === "success") {
            document.getElementById('launch-path-input').value = result.path;
        }
    } catch (e) {
        console.error("Browse failed:", e);
    }
});

btnCloseModal.forEach(btn => {
    btn.addEventListener('click', () => {
        closeMacroEditor();
    });
});

btnRecordToggle.addEventListener('click', toggleRecording);
btnClearMacro.addEventListener('click', clearRecording);

const singleEventKeys = new Set([
    'AudioVolumeMute', 'AudioVolumeDown', 'AudioVolumeUp',
    'MediaTrackNext', 'MediaTrackPrevious', 'MediaStop', 'MediaPlayPause',
    'LaunchMail', 'LaunchMediaSelect', 'LaunchApp1', 'LaunchApp2',
    'BrowserSearch', 'BrowserHome', 'BrowserBack', 'BrowserForward', 'BrowserStop', 'BrowserRefresh', 'BrowserFavorites',
    'PrintScreen', 'Insert'
]);

// Global key listener for recording
const handleRecordingKey = (e, type) => {
    if (isRecording) {
        e.preventDefault();
        e.stopPropagation();

        // Debounce / Repeat filter for keydown?
        // If keydown is repeating (held down), e.repeat is true. 
        // We probably only want the initial press.
        if (type === 'down' && e.repeat) return;

        let keyName = e.key;
        if (keyName === " ") keyName = "Space";
        if (keyName === "Control") keyName = "Ctrl";
        if (keyName === "Shift") keyName = "Shift";
        if (keyName === "Alt") keyName = "Alt";
        if (keyName === "Meta") keyName = "Win";
        if (keyName === "Enter") keyName = "Enter";
        if (keyName === "Backspace") keyName = "Backspace";
        if (keyName === "Delete") keyName = "Del";
        if (keyName === "Escape") keyName = "Esc";
        if (keyName === "Tab") keyName = "Tab";

        // Special handling for Fn/Media keys (F1-F12 combos) - register as single Key Down event
        if (singleEventKeys.has(keyName)) {
            if (type === 'up') return; // Ignore Up event to prevent merging and keep as "Down"
        }

        // Ignore user delays for optimized execution speed
        /*
        const now = Date.now();
        let delay = 0;
        
        if (recordedKeys.length > 0) {
            delay = now - actLastEventTime;
        }
 
        if (delay > 10 && recordedKeys.length > 0) {
            recordedKeys.push({ type: 'delay', value: delay });
        }
        */

        // Logic: If UP event matches the very last DOWN event (ignoring delays if any), merge them into a single 'key' action.
        if (type === 'up') {
            if (recordedKeys.length > 0) {
                const lastAction = recordedKeys[recordedKeys.length - 1];
                if (lastAction.type === 'key_down' && lastAction.value === keyName) {
                    // Merge into single "key" (press)
                    lastAction.type = 'key'; // Change the existing last entry
                    updateRecorderDisplay();
                    return; // Done, don't push the 'up' event
                }
            }

            // Fallback: Check if there is ANY unclosed key_down for this key
            const hasPendingDown = recordedKeys.some(k => k.type === 'key_down' && k.value === keyName);

            if (!hasPendingDown) {
                // Orphan UP event (e.g. from OS interrupt or glitch) -> Treat as Press
                recordedKeys.push({ type: 'key', value: keyName });
                updateRecorderDisplay();
                return;
            }
        }

        recordedKeys.push({ type: type === 'down' ? 'key_down' : 'key_up', value: keyName });

        updateRecorderDisplay();
    }
};

// window.addEventListener('keydown', (e) => handleRecordingKey(e, 'down'));
// window.addEventListener('keyup', (e) => handleRecordingKey(e, 'up'));

// Backend Callback
window.onRecordedKey = (type, keyName) => {
    if (!isRecording) return;

    // Backend already handles mapping, so keyName is ready to use

    // Logic: If UP event matches the very last DOWN event, merge into "key"
    if (type === 'up') {
        if (recordedKeys.length > 0) {
            const lastAction = recordedKeys[recordedKeys.length - 1];
            if (lastAction.type === 'key_down' && lastAction.value === keyName) {
                lastAction.type = 'key'; // Merge
                updateRecorderDisplay();
                return;
            }
        }

        // Check pending
        const hasPendingDown = recordedKeys.some(k => k.type === 'key_down' && k.value === keyName);
        if (!hasPendingDown) {
            recordedKeys.push({ type: 'key', value: keyName });
            updateRecorderDisplay();
            return;
        }
    }

    recordedKeys.push({ type: type === 'down' ? 'key_down' : 'key_up', value: keyName });
    updateRecorderDisplay();
};

function openMacroEditor(macroName = null) {
    macroModal.style.display = "flex";
    setTimeout(() => macroModal.classList.add('active'), 10);
    const nameInput = document.getElementById('macro-name-input');
    const launchInput = document.getElementById('launch-path-input');
    const commandInput = document.getElementById('command-input'); // New

    editingMacroName = macroName; // Set tracking var

    // Reset state
    isRecording = false;
    recordedKeys = [];
    launchInput.value = "";
    commandInput.value = ""; // New
    updateRecorderDisplay();
    updateRecordButton();

    // Default to keystrokes tab
    document.querySelector('.modal-tab[data-tab="keystrokes"]').click();

    if (macroName && typeof macroName === 'string') {
        nameInput.value = macroName;
        // Load existing macro data
        if (profiles[currentProfile].macros && profiles[currentProfile].macros[macroName]) {
            const macroData = profiles[currentProfile].macros[macroName];

            if (macroData.type === "advanced") {
                recordedKeys = [...macroData.actions];
                updateRecorderDisplay();
            } else if (Array.isArray(macroData)) {
                // Convert legacy array to advanced for editing
                recordedKeys = [];
                macroData.forEach(k => {
                    recordedKeys.push({ type: 'key_down', value: k });
                    recordedKeys.push({ type: 'key_up', value: k });
                });
                updateRecorderDisplay();
            } else if (macroData.type === "launch") {
                // Switch to launch tab
                document.querySelector('.modal-tab[data-tab="launch"]').click();
                launchInput.value = macroData.path || "";
            } else if (macroData.type === "command") { // New
                // Switch to command tab
                document.querySelector('.modal-tab[data-tab="command"]').click();
                commandInput.value = macroData.command || "";
            } else {
                // Assume keystrokes (explicit object) legacy
                if (macroData.sequence) {
                    recordedKeys = [];
                    macroData.sequence.forEach(k => {
                        recordedKeys.push({ type: 'key_down', value: k });
                        recordedKeys.push({ type: 'key_up', value: k });
                    });
                    updateRecorderDisplay();
                }
            }

            // Set Icon
            currentMacroIcon = macroData.icon || null;
            updateIconPreview();
        }
    } else {
        nameInput.value = "";
        currentMacroIcon = null;
        updateIconPreview();
    }
}

// --- Icon Selection Logic ---
let currentMacroIcon = null;
const iconBrowserContainer = document.getElementById('icon-browser-container');
const btnMacroIcon = document.getElementById('btn-macro-icon');
const btnBackToEditor = document.getElementById('btn-back-to-editor');
const iconBrowserBody = document.getElementById('icon-browser-body');

btnMacroIcon.addEventListener('click', () => {
    // Hide Editor, Show Browser
    document.querySelector('.modal-tabs').style.display = 'none';
    document.querySelectorAll('.modal-tab-content').forEach(c => c.style.display = 'none');

    iconBrowserContainer.style.display = 'flex';

    // Load icons if empty
    if (iconBrowserBody.children.length === 0) {
        loadAllIcons();
    }
});

btnBackToEditor.addEventListener('click', () => {
    closeIconBrowser();
});

function closeIconBrowser() {
    iconBrowserContainer.style.display = 'none';

    // Show Editor 
    document.querySelector('.modal-tabs').style.display = 'flex';

    // Reset all tab contents to remove inline "display: none" set when opening browser
    // This allows the CSS class .active (display: block) to work again
    document.querySelectorAll('.modal-tab-content').forEach(c => {
        c.style.display = '';
    });

    // Show active tab content
    const activeTab = document.querySelector('.modal-tab.active');
    if (activeTab) {
        const targetId = `modal-tab-${activeTab.dataset.tab}`;
        // Ensure active class matches
        document.getElementById(targetId).classList.add('active');
    }
}

// Global cache for frontend to avoid re-fetching constantly
let cachedIconData = null;
let cachedIconFlatList = null; // Optimized search cache

async function loadAllIcons() {
    // If we have data, use it directly
    if (cachedIconData) {
        renderIconsDeferred(cachedIconData);
        // Ensure cache is built if it was missed previously
        if (!cachedIconFlatList) buildSearchCacheSync(cachedIconData);
        return;
    }

    iconBrowserBody.innerHTML = '<div style="padding:20px; color:var(--text-muted);">Loading icons...</div>';
    try {
        const res = await pywebview.api.get_all_icons_grouped();
        if (res.status === 'success') {
            cachedIconData = res.data; // Cache it

            // Build cache in next frame to allow UI update
            requestAnimationFrame(() => {
                buildSearchCacheSync(cachedIconData);
            });

            renderIconsDeferred(cachedIconData);
        }
    } catch (e) {
        console.error("Error loading all icons:", e);
        iconBrowserBody.innerHTML = '<div style="padding:20px; color:red;">Failed to load icons.</div>';
    }
}

// Simple synchronous build (fast enough for ~3000 icons)
function buildSearchCacheSync(data) {
    if (cachedIconFlatList) return;

    // console.time("BuildCache");
    cachedIconFlatList = [];
    Object.values(data).forEach(icons => {
        icons.forEach(path => {
            cachedIconFlatList.push({
                path: path,
                searchName: path.split('/').pop().toLowerCase()
            });
        });
    });
    // console.timeEnd("BuildCache");
}

function renderIconsDeferred(data) {
    iconBrowserBody.innerHTML = '';

    if (Object.keys(data).length === 0) {
        iconBrowserBody.innerHTML = '<div style="padding:20px;">No icons found.</div>';
        return;
    }

    const categories = Object.entries(data);
    let index = 0;

    // Render Function using recursive requestAnimationFrame for non-blocking UI
    function renderNextBatch() {
        // ... (existing render logic)
        const start = performance.now();
        // Render for up to 10ms per frame to keep UI responsive
        while (index < categories.length && performance.now() - start < 10) {
            const [category, icons] = categories[index];

            // Header
            const header = document.createElement('div');
            header.className = 'icon-category-header';
            header.innerText = category;
            iconBrowserBody.appendChild(header);

            // Grid
            const grid = document.createElement('div');
            grid.className = 'icon-grid-section';
            grid.style.display = 'grid';
            grid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(60px, 1fr))';
            grid.style.gap = '10px';
            grid.style.padding = '15px';

            // Optimized render with Fragment
            renderIconsToContainer(icons, grid);
            iconBrowserBody.appendChild(grid);

            index++;
        }

        if (index < categories.length) {
            requestAnimationFrame(renderNextBatch);
        }
    }

    renderNextBatch();
}

function renderIconsToContainer(iconList, container) {
    if (!iconList || iconList.length === 0) return;

    // Use DocumentFragment for batched DOM insertion
    const fragment = document.createDocumentFragment();

    iconList.forEach(iconPath => {
        const div = document.createElement('div');
        div.className = 'icon-grid-item';
        if (currentMacroIcon === iconPath) div.classList.add('selected');

        const img = document.createElement('img');
        img.src = iconPath;
        img.loading = "lazy"; // Native lazy loading
        div.appendChild(img);

        div.onclick = () => selectIcon(iconPath);
        fragment.appendChild(div);
    });

    container.appendChild(fragment);
}

// Search Filter Listener (Global Backend Search)
let iconSearchDebounce;
const iconSearchInput = document.getElementById('icon-search-input');
if (iconSearchInput) {
    iconSearchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        clearTimeout(iconSearchDebounce);

        iconSearchDebounce = setTimeout(async () => {
            if (!query) {
                // Restore all icons view
                loadAllIcons();
                return;
            }

            // Client-side search optimization
            if (cachedIconFlatList) {
                const queryLower = query.toLowerCase();

                // Fast filter on pre-processed list
                const matches = cachedIconFlatList
                    .filter(item => item.searchName.includes(queryLower))
                    .map(item => item.path); // Extract path only

                // Render Results
                renderSearchResults(matches, query);
                return;
            }

            // Fallback to Backend if cache missing (should rarely happen if browser opened)
            try {
                const res = await pywebview.api.search_icons(query);
                if (res.status === 'success') {
                    renderSearchResults(res.icons, query);
                }
            } catch (e) {
                console.error("Error searching icons:", e);
            }
        }, 150); // Lowered debounce to 150ms for snappier feel
    });
}

function renderSearchResults(icons, query) {
    iconBrowserBody.innerHTML = '';

    // Header for results
    const header = document.createElement('div');
    header.innerText = `Search Results: "${query}"`;
    header.style.padding = '10px 15px';
    header.style.color = '#eee';
    header.style.borderBottom = '1px solid #333';
    iconBrowserBody.appendChild(header);

    const grid = document.createElement('div');
    grid.style.display = 'grid';
    grid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(60px, 1fr))';
    grid.style.gap = '10px';
    grid.style.padding = '15px';

    if (icons.length > 0) {
        // Limit to 200 for performance
        const displayIcons = icons.slice(0, 200);
        renderIconsToContainer(displayIcons, grid);

        if (icons.length > 200) {
            const p = document.createElement('p');
            p.style.padding = "10px";
            p.style.color = "var(--text-muted)";
            p.innerText = `Showing first 200 of ${icons.length} results. Refine your search.`;
            iconBrowserBody.appendChild(p);
        }
    } else {
        grid.innerHTML = '<div style="color:var(--text-muted);">No matching icons found.</div>';
        grid.style.display = 'block';
    }
    iconBrowserBody.appendChild(grid);
}

function selectIcon(iconPath) {
    currentMacroIcon = iconPath;
    updateIconPreview();
    closeIconBrowser();
}

function updateIconPreview() {
    if (currentMacroIcon) {
        btnMacroIcon.innerHTML = `<img src="${currentMacroIcon}" alt="Icon">`;
    } else {
        btnMacroIcon.innerHTML = `<i class="fa-solid fa-bolt"></i>`;
    }
}

// Specific cancel button handler
document.getElementById('btn-cancel-macro-editor').addEventListener('click', () => {
    closeMacroEditor();
});

async function closeMacroEditor() {
    macroModal.classList.remove('active');
    setTimeout(async () => {
        macroModal.style.display = "none";
        if (isRecording) {
            // Stop recording logic locally and in backend
            isRecording = false;
            await pywebview.api.stop_macro_recording();
            updateRecordButton();
        }
    }, 300); // Wait for transition
}

// --- Custom Filter Dropdown Logic ---
const btnFilterToggle = document.getElementById('btn-community-filter');
const dropdownMenu = document.getElementById('community-filter-dropdown');
const hiddenSelect = document.getElementById('community-sort');
const dropdownItems = document.querySelectorAll('.dropdown-item');

if (btnFilterToggle && dropdownMenu && hiddenSelect) {
    // Toggle Dropdown
    btnFilterToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdownMenu.classList.toggle('show');
        btnFilterToggle.classList.toggle('active');
    });

    // Close on click outside
    document.addEventListener('click', (e) => {
        if (!dropdownMenu.contains(e.target) && !btnFilterToggle.contains(e.target)) {
            dropdownMenu.classList.remove('show');
            btnFilterToggle.classList.remove('active');
        }
    });

    // Handle Item Selection
    dropdownItems.forEach(item => {
        item.addEventListener('click', () => {
            const value = item.dataset.value;

            // UI Update
            dropdownItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            // Update Hidden Select
            hiddenSelect.value = value;

            // Trigger Change Event for App Logic
            const event = new Event('change');
            hiddenSelect.dispatchEvent(event);

            // Close Dropdown
            dropdownMenu.classList.remove('show');
            btnFilterToggle.classList.remove('active');
        });
    });
}

// --- Custom Knob Mode Dropdown Logic ---
const btnKnobMode = document.getElementById('btn-knob-mode');
const dropdownKnobMode = document.getElementById('knob-mode-dropdown');
const selectKnobMode = document.getElementById('knob-mode-select');
const knobFnDesc = document.getElementById('knob-mode-desc');
const knobLabel = document.getElementById('knob-mode-label');

if (btnKnobMode && dropdownKnobMode && selectKnobMode) {
    // Toggle
    btnKnobMode.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdownKnobMode.classList.toggle('show');
        btnKnobMode.classList.toggle('active');
    });

    // Close on click outside (shared logic could be cleaner, but this is safe)
    document.addEventListener('click', (e) => {
        if (!dropdownKnobMode.contains(e.target) && !btnKnobMode.contains(e.target)) {
            dropdownKnobMode.classList.remove('show');
            btnKnobMode.classList.remove('active');
        }
    });

    // Handle Selection
    const knobItems = dropdownKnobMode.querySelectorAll('.dropdown-item');
    knobItems.forEach(item => {
        item.addEventListener('click', () => {
            const value = item.dataset.value;

            // Sync UI
            knobItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            knobLabel.innerText = item.innerText; // Update button label

            // Sync Native Select
            selectKnobMode.value = value;

            // Trigger Change Logic
            // The logic for knob mode change is likely bound to the select 'change' event 
            // or we might need to call handleKnobModeChange directly? 
            // Let's check how the original select was used.
            // Looking at previous analysis, handleKnobModeChange(mode) exists.

            // Dispatch event to be safe if listeners exist
            const event = new Event('change');
            selectKnobMode.dispatchEvent(event);

            // Also explicitly call handler if needed (usually handled by listener on select)
            // But if the listener was on the select ID, dispatchEvent is enough.

            // Close
            dropdownKnobMode.classList.remove('show');
            btnKnobMode.classList.remove('active');

            // Update Description (redundant if change listener does it, but instant feedback)
            // Actually change listener should do it.
        });
    });

    // Sync initial state from select
    const initialVal = selectKnobMode.value;
    knobLabel.innerText = selectKnobMode.options[selectKnobMode.selectedIndex].text;
    knobItems.forEach(i => {
        if (i.dataset.value === initialVal) i.classList.add('active');
        else i.classList.remove('active');
    });
}

async function toggleRecording() {
    isRecording = !isRecording;
    if (isRecording) {
        if (recordedKeys.length === 0) actLastEventTime = Date.now();
        else actLastEventTime = Date.now();

        // Start Backend Recording
        await pywebview.api.start_macro_recording();
    } else {
        // Stop Backend Recording
        await pywebview.api.stop_macro_recording();
    }
    updateRecordButton();
}

function updateRecordButton() {
    if (isRecording) {
        btnRecordToggle.innerHTML = '<i class="fa-solid fa-circle-stop"></i> Stop Recording';
        btnRecordToggle.classList.add('recording');
    } else {
        btnRecordToggle.innerHTML = '<i class="fa-solid fa-circle"></i> Start Recording';
        btnRecordToggle.classList.remove('recording');
    }
}

function clearRecording() {
    recordedKeys = [];
    updateRecorderDisplay();
    if (isRecording) toggleRecording();
}

function updateRecorderDisplay() {
    keysDisplay.innerHTML = '';

    if (recordedKeys.length === 0) {
        keysDisplay.innerHTML = '<span class="placeholder-text">Press keys to record...</span>';
        return;
    }

    recordedKeys.forEach(action => {
        if (action.type === 'delay') {
            const span = document.createElement('span');
            span.className = 'delay-badge';
            span.innerHTML = `&rarr; ${action.value}ms &rarr;`;
            keysDisplay.appendChild(span);
        } else if (action.type === 'key') {
            // Merged single press
            const span = document.createElement('span');
            span.className = 'key-badge key-press'; // New class
            span.innerHTML = `${action.value}`; // No arrow
            keysDisplay.appendChild(span);
        } else {
            const span = document.createElement('span');
            span.className = `key-badge ${action.type === 'key_down' ? 'down' : 'up'}`;
            // Icon
            const icon = action.type === 'key_down' ? '<i class="fa-solid fa-caret-down"></i>' : '<i class="fa-solid fa-caret-up"></i>';
            span.innerHTML = `${action.value} <small>${icon}</small>`;
            keysDisplay.appendChild(span);
        }
    });

    // Auto scroll
    keysDisplay.scrollTop = keysDisplay.scrollHeight;
}

btnSaveMacro.addEventListener('click', async () => {
    const name = document.getElementById('macro-name-input').value.trim();
    if (!name) {
        await showAlert("", "Please enter a macro name", "danger");
        return;
    }

    if (!profiles[currentProfile].macros) profiles[currentProfile].macros = {};

    // Check if name exists (if new or renamed)
    if (name !== editingMacroName && profiles[currentProfile].macros[name]) {
        const confirmOverwrite = await showConfirm("Overwrite Macro", `Macro "${name}" already exists. Overwrite?`);
        if (!confirmOverwrite) {
            return;
        }
    }

    // Determine type based on active tab
    const activeTab = document.querySelector('.modal-tab.active').dataset.tab;
    let macroData = { name: name };
    if (currentMacroIcon) {
        macroData.icon = currentMacroIcon;
    }

    if (activeTab === "launch") {
        const path = document.getElementById('launch-path-input').value.trim();
        if (!path) {
            await showAlert("", "Please enter a path or URL", "danger");
            return;
        }
        macroData.type = "launch";
        macroData.path = path;
    } else if (activeTab === "command") { // New
        const cmd = document.getElementById('command-input').value.trim();
        if (!cmd) {
            await showAlert("", "Please enter a command", "danger");
            return;
        }
        macroData.type = "command";
        macroData.command = cmd;
    } else {
        // Keystrokes
        if (recordedKeys.length === 0) {
            await showAlert("", "Please record at least one key", "danger");
            return;
        }
        macroData.type = "advanced";
        macroData.actions = recordedKeys;
    }

    // If renaming, delete old one
    if (editingMacroName && name !== editingMacroName) {
        delete profiles[currentProfile].macros[editingMacroName];

        const p = profiles[currentProfile];
        Object.keys(p.keys).forEach(k => {
            if (p.keys[k] === editingMacroName) p.keys[k] = name;
        });
        Object.keys(p.knobs).forEach(k => {
            if (p.knobs[k] === editingMacroName) p.knobs[k] = name;
        });
    }

    // Save/Update
    profiles[currentProfile].macros[name] = macroData;

    await saveProfiles();
    updateUIForProfile();
    closeMacroEditor();
});

// --- Events from Python ---
window.onSerialMessage = (message) => {
    // console.log("Serial:", message);  // [DEBUG - Disabled in production]

    // Visual Feedback
    if (message.startsWith("KEY_") && message.endsWith("_PRESSED")) {
        const id = parseInt(message.split("_")[1]) + 1;
        const btn = document.querySelector(`.key-btn[data-id="${id}"]`);
        if (btn) {
            btn.classList.add('active-press');
            setTimeout(() => btn.classList.remove('active-press'), 200);
        }
    }
};

window.onSerialConnectionLost = () => {
    // console.log("Connection lost");  // [DEBUG - Disabled in production]
    setConnected(false);
};

window.onSerialConnected = (portName = "") => {
    // console.log("Connection established:", portName);  // [DEBUG - Disabled in production]
    setConnected(true, portName);
};

window.onAutoProfileSwitch = (profileName) => {
// No console log needed here

    currentProfile = profileName;
    updateUIForProfile();
    // Intentionally NOT showing in-app toast here, as system notification is used.
};


function filterList(listId, query) {
    const list = document.getElementById(listId);
    if (!list) return 0;

    const items = list.querySelectorAll('.macro-item');
    let visibleCount = 0;

    items.forEach(item => {
        // Skip filtering the "New Macro" button if it's still there (though we removed it)
        // Check text content
        const textSpan = item.querySelector('span');
        const text = textSpan ? textSpan.innerText.toLowerCase() : "";

        if (text.includes(query)) {
            item.style.display = "flex";
            visibleCount++;
        } else {
            item.style.display = "none";
        }
    });

    // Show empty state if no results and query exists
    const existingEmpty = list.querySelector('.empty-state');
    if (visibleCount === 0 && query) {
        if (!existingEmpty) {
            const emptyState = document.createElement('div');
            emptyState.className = 'empty-state';
            emptyState.innerHTML = `
                <i class="fa-solid fa-magnifying-glass"></i>
                <h4>No macros found</h4>
                <p>Try a different search term</p>
            `;
            list.appendChild(emptyState);
        }
    } else if (existingEmpty) {
        existingEmpty.remove();
    }

    return visibleCount;
}

// ====================
// GENERIC MODAL UTILS
// ====================

function showConfirm(title, message) {
    return new Promise((resolve) => {
        const modal = document.getElementById('generic-modal');
        const titleEl = document.getElementById('generic-modal-title');
        const msgEl = document.getElementById('generic-modal-message');
        const inputEl = document.getElementById('generic-modal-input');
        const progressEl = document.getElementById('generic-modal-progress-container');
        const btnCancel = document.getElementById('generic-modal-cancel');
        const btnOk = document.getElementById('generic-modal-ok');

        // Reset state
        titleEl.textContent = title;
        msgEl.textContent = message;
        inputEl.style.display = 'none';
        progressEl.style.display = 'none';
        btnCancel.style.display = 'inline-block';
        btnOk.textContent = 'OK';

        modal.style.display = 'flex';
        setTimeout(() => modal.classList.add('active'), 10);

        const close = (result) => {
            modal.classList.remove('active');
            setTimeout(() => modal.style.display = 'none', 200);
            // Remove listeners to prevent leaks/double firing if reused
            btnCancel.onclick = null;
            btnOk.onclick = null;
            resolve(result);
        };

        btnCancel.onclick = () => close(false);
        btnOk.onclick = () => close(true);
    });
}

// ====================
// LINK APP MODAL LOGIC
// ====================

async function showLinkAppModal() {
    const modal = document.getElementById('link-app-modal');
    const list = document.getElementById('active-apps-list');
    const input = document.getElementById('manual-app-input');
    const btnConfirm = document.getElementById('link-modal-confirm');
    const btnCancel = document.getElementById('link-modal-cancel');
    const btnUnlink = document.getElementById('link-modal-unlink');
    const btnClose = document.getElementById('link-modal-close');
    const btnRefresh = document.getElementById('btn-refresh-apps');

    // Clear prev state
    input.value = "";
    if (btnUnlink) btnUnlink.style.display = 'none';

    // Fetch currently linked app to pre-fill
    try {
        const result = await pywebview.api.get_linked_app(currentProfile);
        if (result.status === 'success' && result.data && result.data.length > 0) {
            input.value = result.data[0];
            // Show unlink button if apps are linked
            if (btnUnlink) {
                btnUnlink.style.display = 'block';
                // Optional: Update text to show count or specific app? Keep simple.
            }
        }
    } catch (e) { console.error(e); }

    // Load apps
    await loadActiveApps();

    // Show modal
    modal.style.display = 'flex';
    setTimeout(() => modal.classList.add('active'), 10);

    // Close handlers
    const closeModal = () => {
        modal.classList.remove('active');
        setTimeout(() => modal.style.display = 'none', 200);
    };

    btnClose.onclick = closeModal;
    btnCancel.onclick = closeModal;

    // Refresh handler
    btnRefresh.onclick = async () => {
        await loadActiveApps();
    };

    // Unlink handler
    if (btnUnlink) {
        btnUnlink.onclick = async () => {
            const confirmed = await showConfirm(
                "Unlink Applications",
                `Are you sure you want to unlink apps from "${currentProfile}"?`
            );

            if (!confirmed) return;

            // Proactively update local state for instant feel
            profiles[currentProfile].linked_apps = [];
            if (window.State) window.State.profiles = profiles;
            
            // Proactively hide unlink button and update UI
            btnUnlink.style.display = 'none';
            input.value = "";
            await updateLinkAppButtonState(false);
            await updateProfileAppIcon();

            try {
                const res = await pywebview.api.unlink_app_from_profile(currentProfile);
                if (res.status === 'success') {
                    showToast(res.message, "success");
                    closeModal();
                    
                    // Refresh from backend to ensure persistent sync
                    if (window.loadProfiles) {
                        await window.loadProfiles();
                    }
                } else {
                    showToast(res.message, "error");
                    // Revert local state and show button if failed
                    if (window.loadProfiles) await window.loadProfiles(); 
                    btnUnlink.style.display = 'block';
                }
            } catch (e) {
                console.error(e);
                showToast("Failed to unlink app", "error");
                if (window.loadProfiles) await window.loadProfiles();
                btnUnlink.style.display = 'block';
            }
        };
    }

    // Select handler
    list.onchange = () => {
        if (list.value) {
            input.value = list.value;
        }
    };

    // Confirm handler
    btnConfirm.onclick = async () => {
        const appExe = input.value.trim();
        if (!appExe) {
            showToast("Please select an app or enter name", "error");
            return;
        }

        // Proactively update local state for instant feel
        if (!profiles[currentProfile].linked_apps) profiles[currentProfile].linked_apps = [];
        profiles[currentProfile].linked_apps = [appExe];
        if (window.State) window.State.profiles = profiles;

        // Proactively update UI and close
        await updateLinkAppButtonState(true);
        await updateProfileAppIcon();
        closeModal();

        try {
            const res = await pywebview.api.link_app_to_profile(currentProfile, appExe);
            if (res.status === 'success') {
                showToast(`Linked ${appExe} to ${currentProfile}`, "success");
                
                // Refresh complete profile state from backend
                if (window.loadProfiles) {
                    await window.loadProfiles();
                }
            } else {
                showToast(res.message, "error");
                // Revert if failed
                if (window.loadProfiles) await window.loadProfiles();
            }
        } catch (e) {
            showToast("Failed to link app", "error");
            if (window.loadProfiles) await window.loadProfiles();
        }
    };
}

async function loadActiveApps() {
    const list = document.getElementById('active-apps-list');
    const btnRefresh = document.getElementById('btn-refresh-apps');

    list.innerHTML = '<option disabled>Loading...</option>';
    if (btnRefresh) btnRefresh.querySelector('i').classList.add('fa-spin');

    try {
        const res = await pywebview.api.get_active_processes();
        list.innerHTML = ''; // clear

        if (res.status === 'success' && res.data && res.data.length > 0) {
            res.data.forEach(app => {
                const opt = document.createElement('option');
                opt.value = app;
                opt.textContent = app;
                list.appendChild(opt);
            });
        } else {
            list.innerHTML = '<option disabled>No active windows found</option>';
        }
    } catch (e) {
        console.error("Error loading apps:", e);
        list.innerHTML = '<option disabled>Error loading apps</option>';
    } finally {
        if (btnRefresh) btnRefresh.querySelector('i').classList.remove('fa-spin');
    }
}

// Link App Button State implementation moved above

// --- Custom Profile Dropdown Toggle Logic ---
const btnProfileDropdown = document.getElementById('btn-profile-dropdown');
const dropdownProfile = document.getElementById('profile-dropdown-menu');

if (btnProfileDropdown && dropdownProfile) {
    btnProfileDropdown.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdownProfile.classList.toggle('show');
        btnProfileDropdown.classList.toggle('active');
    });

    document.addEventListener('click', (e) => {
        if (!dropdownProfile.contains(e.target) && !btnProfileDropdown.contains(e.target)) {
            dropdownProfile.classList.remove('show');
            btnProfileDropdown.classList.remove('active');
        }
    });
}

// Expose key UI functions to window for legacy scripts/modules
window.updateUIForProfile = updateUIForProfile;
window.updateMacroList = updateMacroList;

