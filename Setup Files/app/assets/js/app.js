// Global State
let currentProfile = "Default Profile";
let profiles = {};
let currentControl = { type: "key", id: 1 }; // Default to Key 1
let isConnected = false;
let isRecording = false;
let recordedKeys = [];
let actLastEventTime = 0;
let editingMacroName = null;
let flashProgressInterval = null; // Interval for simulated progress
let profileSaveTimeout = null; // For debouncing saves
const PROFILE_NAME_MAX_LENGTH = 30;

// Helper for Custom Dialogs
const Dialog = {
    modal: document.getElementById('generic-modal'),
    title: document.getElementById('generic-modal-title'),
    message: document.getElementById('generic-modal-message'),
    input: document.getElementById('generic-modal-input'),
    btnOk: document.getElementById('generic-modal-ok'),
    btnCancel: document.getElementById('generic-modal-cancel'),
    btnClose: null, // Generic modal doesn't have a close button
    icon: document.querySelector('.generic-modal-icon'),

    show(options) {
        return new Promise((resolve) => {
            // clear any pending hide
            if (this.hideTimeout) {
                clearTimeout(this.hideTimeout);
                this.hideTimeout = null;
            }

            this.title.innerText = options.title || "Alert";
            this.message.innerHTML = options.message || "";
            this.input.value = options.defaultValue || "";
            this.input.style.display = options.hasInput ? "block" : "none";
            this.btnOk.innerText = options.confirmText || "OK";

            // Hide progress bar by default (reset state)
            const progContainer = document.getElementById('generic-modal-progress-container');
            if (progContainer) progContainer.style.display = 'none';

            // Reset classes
            this.modal.classList.remove('modal-type-danger', 'modal-type-success');
            this.icon.style.display = "none";
            this.icon.className = "modal-icon generic-modal-icon"; // Reset

            // Apply Type
            if (options.type) {
                this.modal.classList.add(`modal-type-${options.type}`);
                this.icon.style.display = "block";

                if (options.type === 'danger') {
                    this.icon.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';
                    // For danger dialogs, swap button styles: cancel becomes primary (blue), OK becomes danger (red)
                    this.btnCancel.className = 'btn-primary';
                    this.btnOk.className = 'btn-danger';
                } else if (options.type === 'success') {
                    this.icon.innerHTML = '<i class="fa-solid fa-check-circle"></i>';
                    // Reset to default styles
                    this.btnCancel.className = 'btn-cancel';
                    this.btnOk.className = 'btn-primary';
                } else {
                    this.icon.innerHTML = '<i class="fa-solid fa-info-circle"></i>';
                    // Reset to default styles
                    this.btnCancel.className = 'btn-cancel';
                    this.btnOk.className = 'btn-primary';
                }
            } else {
                // No type specified, use default styles
                this.btnCancel.className = 'btn-cancel';
                this.btnOk.className = 'btn-primary';
            }

            // Focus input if present
            if (options.hasInput) {
                setTimeout(() => this.input.focus(), 100);
            }

            this.modal.style.display = "flex";
            // Force reflow for transition
            setTimeout(() => this.modal.classList.add('active'), 10);

            const close = (value) => {
                this.modal.classList.remove('active');
                this.hideTimeout = setTimeout(() => {
                    this.modal.style.display = "none";
                    this.cleanup();
                    resolve(value);
                }, 200); // Match CSS transition
            };

            this.onOk = () => {
                const val = options.hasInput ? this.input.value.trim() : true;
                close(val);
            };

            this.onCancel = () => close(null);

            // Bind events
            this.btnOk.onclick = this.onOk;
            this.btnCancel.onclick = this.onCancel;
            if (this.btnClose) this.btnClose.onclick = this.onCancel;

            // Handle Enter key in input
            if (options.hasInput) {
                this.input.onkeydown = (e) => {
                    if (e.key === "Enter") this.onOk();
                    if (e.key === "Escape") this.onCancel();
                };
            }
        });
    },

    cleanup() {
        this.btnOk.onclick = null;
        this.btnCancel.onclick = null;
        if (this.btnClose) this.btnClose.onclick = null;
        this.input.onkeydown = null;
    }
};

async function showPrompt(title, message, defaultValue = "", confirmText = "OK") {
    return await Dialog.show({ title, message, hasInput: true, defaultValue, confirmText });
}

async function showConfirm(title, message, type = "info", confirmText = "OK") {
    return await Dialog.show({ title, message, hasInput: false, type, confirmText });
}

async function showAlert(title, message, type = "info") {
    return await Dialog.show({ title, message, hasInput: false, type });
}


// Initialize
window.addEventListener('DOMContentLoaded', async () => {
    // console.log("App loaded");  // [DEBUG - Disabled in production]

    // Navigation
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const pageId = btn.dataset.page;
            showPage(pageId);
        });
    });

    // Profile Actions
    document.getElementById('profile-select').addEventListener('change', (e) => {
        switchProfile(e.target.value);
    });

    document.getElementById('btn-new-profile').addEventListener('click', createProfile);
    document.getElementById('btn-edit-profile').addEventListener('click', editProfile);
    document.getElementById('btn-delete-profile').addEventListener('click', deleteProfile);

    // Link App Button
    const btnLinkApp = document.getElementById('btn-link-app');
    if (btnLinkApp) {
        btnLinkApp.addEventListener('click', () => {
            if (btnLinkApp.disabled) return;
            showLinkAppModal();
        });
    }

    // Initialize Link App button state
    updateLinkAppButtonState();

    // Connection
    document.getElementById('connection-toggle').addEventListener('change', async (e) => {
        const toggle = e.target;
        toggle.disabled = true; // Prevent multiple clicks

        try {
            if (toggle.checked) {
                await connectSerial();
            } else {
                await disconnectSerial();
            }
        } finally {
            toggle.disabled = false;
        }
    });

    // Key Grid
    document.querySelectorAll('.key-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            selectKey(parseInt(btn.dataset.id));
        });
    });

    // Knob Actions
    document.getElementById('knob-mode-select').addEventListener('change', async (e) => {
        await handleKnobModeChange(e.target.value);
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
            if (row.classList.contains('readonly')) return;
            selectKnobAction(row.dataset.action);
        });
    });


    // New Macro Button (Fixed Footer)
    document.querySelectorAll('.action-create-macro').forEach(btn => {
        btn.addEventListener('click', () => openMacroEditor());
    });

    // Search Functionality with Debounce
    const setupSearch = (inputId, clearBtnId, countId, legacyListId, userListId) => {
        const input = document.getElementById(inputId);
        const clearBtn = document.getElementById(clearBtnId);
        const countEl = document.getElementById(countId);
        if (!input) return;

        let debounceTimer;

        const doSearch = (query) => {
            const results = filterList(legacyListId, query) + filterList(userListId, query);

            // Update result count
            if (query && countEl) {
                countEl.textContent = `${results} result${results !== 1 ? 's' : ''}`;
                countEl.style.display = 'block';
            } else if (countEl) {
                countEl.style.display = 'none';
            }

            // Show/hide clear button
            if (clearBtn) {
                clearBtn.classList.toggle('visible', query.length > 0);
            }
        };

        input.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            const query = e.target.value.toLowerCase();
            debounceTimer = setTimeout(() => doSearch(query), 200);
        });

        // Clear button functionality
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                input.value = '';
                doSearch('');
                input.focus();
            });
        }
    };

    setupSearch('macro-search-keys', 'search-clear-keys', 'search-count-keys', 'macro-list-legacy', 'macro-list-user');
    setupSearch('macro-search-knob', 'search-clear-knob', 'search-count-knob', 'knob-macro-list-legacy', 'knob-macro-list-user');

    // Macro Tabs
    // Macro Tabs - Scoped
    document.querySelectorAll('.macro-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const panel = tab.closest('.macro-panel');
            if (!panel) return;

            // Remove active class from all tabs and contents in THIS panel
            panel.querySelectorAll('.macro-tab').forEach(t => t.classList.remove('active'));
            panel.querySelectorAll('.macro-tab-content').forEach(c => c.classList.remove('active'));

            // Add active class to clicked tab
            tab.classList.add('active');

            // Show corresponding content: support data-target or fallback to data-tab logic
            let targetId = tab.dataset.target;
            if (!targetId && tab.dataset.tab) {
                targetId = `tab-${tab.dataset.tab}`;
            }

            if (targetId) {
                const el = document.getElementById(targetId);
                if (el) el.classList.add('active');
            }
        });
    });

    // Settings Listeners
    document.getElementById('chk-startup').addEventListener('change', async (e) => {
        const enabled = e.target.checked;
        await pywebview.api.set_startup_status(enabled);
    });

    document.getElementById('chk-tray').addEventListener('change', async (e) => {
        const enabled = e.target.checked;
        await pywebview.api.set_tray_status(enabled);
    });

    document.getElementById('btn-reset-defaults').addEventListener('click', async () => {
        const confirmReset = await showConfirm("Reset to Defaults", "Are you sure? This will delete all profiles and macros. This action cannot be undone.", "danger", "Reset Everything");
        if (confirmReset) {
            await pywebview.api.reset_to_defaults();
            window.location.reload();
        }
    });


    // Theme Selector (Visual)
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

    // Check Updates
    document.getElementById('btn-check-updates').addEventListener('click', async () => {
        const btn = document.getElementById('btn-check-updates');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Checking...';
        btn.disabled = true;

        try {
            const res = await pywebview.api.check_for_updates();

            if (res.status === 'success') {
                const fw = res.firmware;
                const app = res.app;

                let msg = "";

                // Firmware Status
                if (fw.error) {
                    msg += `<strong>Firmware:</strong> Error - ${fw.error}<br>`;
                } else if (fw.update_available) {
                    msg += `<strong>Firmware:</strong> Update Available (v${fw.latest_version})<br>`;
                    msg += `<small><a href="#" onclick="startFirmwareUpdate()">Update Now</a></small><br>`;
                } else {
                    msg += `<strong>Firmware:</strong> Up to date (v${fw.current_version})<br>`;
                }

                msg += "<br>";

                // App Status
                if (app.status === 'error' || app.error) {
                    const errMsg = app.message || app.error;
                    msg += `<strong>App:</strong> Error - ${errMsg}`;
                } else if (app.update_available) {
                    msg += `<strong>App:</strong> Update Available (v${app.latest_version})<br>`;
                    // NEW: Use UpdateManager flow
                    const downloadUrl = app.download_url || app.zipball_url || ""; // fallback
                    msg += `<small><a href="#" onclick="startAppUpdate('${downloadUrl}', '${app.latest_version}')">Update Now</a></small><br>`;

                    if (app.html_url) {
                        msg += `<small>or <a href="#" onclick="pywebview.api.generate_macro_submission_url({'url': '${app.html_url}'})">view on GitHub</a></small>`;
                    }
                } else {
                    msg += `<strong>App:</strong> Up to date (v${app.current_version})`;
                }

                await showAlert("Update Status", msg); // Use showAlert which supports HTML

            } else {
                await showAlert("Error", res.message, "error");
            }
        } catch (e) {
            await showAlert("Error", "Failed to check updates", "error");
        } finally {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    });




    // Initial Load
    // Wait for pywebview to be ready
    if (window.pywebview) {
        init();
    } else {
        window.addEventListener('pywebviewready', init);
    }
});

async function init() {
    await loadProfiles();
    await loadSettings();
    // Sync initial profile
    await pywebview.api.set_active_profile(currentProfile);
    // Don't pre-select any key - let user choose

    // Auto-connect silently
    connectSerial(true);
}

// --- Navigation ---
function showPage(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(`page-${pageId}`).classList.add('active');

    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.querySelector(`.nav-item[data-page="${pageId}"]`).classList.add('active');

    const titles = {
        'keys': 'Key Configuration',
        'knob': 'Knob Configuration',
        'settings': 'Settings',
        'community': 'Macro Hub'
    };
    document.getElementById('page-title').innerText = titles[pageId];

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
async function loadProfiles() {
    try {
        const data = await pywebview.api.get_profiles();
        profiles = data.profiles;

        // Check for persistent active profile
        if (data.active_profile && profiles[data.active_profile]) {
            currentProfile = data.active_profile;
        }

        const select = document.getElementById('profile-select');
        select.innerHTML = '';
        Object.keys(profiles).forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.innerText = name;
            select.appendChild(option);
        });

        // Set current profile
        if (profiles[currentProfile]) {
            select.value = currentProfile;
        } else {
            currentProfile = Object.keys(profiles)[0];
            select.value = currentProfile;
        }

        updateUIForProfile();
    } catch (e) {
        console.error("Error loading profiles:", e);
    }
}

function switchProfile(name) {
    currentProfile = name;
    pywebview.api.set_active_profile(name);
    updateUIForProfile();
}

async function createProfile() {
    const name = await showPrompt("New Profile", "Enter profile name (max 30 characters):");
    if (!name) return;

    // Validate name
    if (name.length > PROFILE_NAME_MAX_LENGTH) {
        await showAlert("Error", `Profile name must be ${PROFILE_NAME_MAX_LENGTH} characters or less`);
        return;
    }

    if (!/^[a-zA-Z0-9\s_-]+$/.test(name)) {
        await showAlert("Error", "Profile name can only contain letters, numbers, spaces, hyphens, and underscores");
        return;
    }

    if (profiles[name]) {
        await showAlert("Error", "Profile already exists");
        return;
    }

    profiles[name] = { macros: {}, keys: {}, knobs: {} };
    await saveProfiles(true); // Immediate save
    await loadProfiles();
    switchProfile(name);
}

async function deleteProfile() {
    if (currentProfile === "Default Profile") {
        await showAlert("Error", "Cannot delete Default Profile", "danger");
        return;
    }
    const confirmDelete = await showConfirm("Delete Profile", `Are you sure you want to delete "${currentProfile}"?`, "danger", "Delete");
    if (confirmDelete) {
        delete profiles[currentProfile];
        currentProfile = "Default Profile";
        await saveProfiles(true); // Immediate save
        await loadProfiles();
    }
}

async function editProfile() {
    if (currentProfile === "Default Profile") {
        await showAlert("Error", "Cannot rename Default Profile");
        return;
    }
    const newName = await showPrompt("Rename Profile", "Enter new profile name (max 30 characters):", currentProfile);
    if (!newName) return;

    if (newName === currentProfile) return; // No change

    // Validate name
    if (newName.length > PROFILE_NAME_MAX_LENGTH) {
        await showAlert("Error", `Profile name must be ${PROFILE_NAME_MAX_LENGTH} characters or less`);
        return;
    }

    if (!/^[a-zA-Z0-9\s_-]+$/.test(newName)) {
        await showAlert("Error", "Profile name can only contain letters, numbers, spaces, hyphens, and underscores");
        return;
    }

    if (profiles[newName]) {
        await showAlert("Error", "Profile already exists");
        return;
    }

    // Copy data to new key
    profiles[newName] = profiles[currentProfile];
    delete profiles[currentProfile];
    currentProfile = newName;

    await saveProfiles(true); // Immediate save
    await loadProfiles();
    switchProfile(newName);
}

async function saveProfiles(immediate = false) {
    if (immediate) {
        // For critical operations (rename, delete), save immediately without debouncing
        if (profileSaveTimeout) {
            clearTimeout(profileSaveTimeout);
            profileSaveTimeout = null;
        }
        await pywebview.api.save_profiles({ profiles: profiles });
        return;
    }

    // Debounce saves to reduce file I/O for regular operations
    if (profileSaveTimeout) {
        clearTimeout(profileSaveTimeout);
    }

    profileSaveTimeout = setTimeout(async () => {
        await pywebview.api.save_profiles({ profiles: profiles });
    }, 500);
}

function updateUIForProfile() {
    document.getElementById('active-profile-name').innerText = currentProfile;
    document.getElementById('profile-select').value = currentProfile;

    // Update Link App Button State for the new profile
    updateLinkAppButtonState();

    const profileData = profiles[currentProfile];
    if (!profileData.keys) profileData.keys = {};
    if (!profileData.knobs) profileData.knobs = {};

    // Update Keys
    document.querySelectorAll('.key-btn').forEach(btn => {
        const id = btn.dataset.id;
        const macroName = profileData.keys[id];
        const label = btn.querySelector('.key-label');
        const icon = btn.querySelector('.key-cap i');

        if (macroName) {
            label.innerText = macroName;
            icon.className = "fa-solid fa-check"; // Placeholder
        } else {
            label.innerText = `K${id}`;
            icon.className = "fa-solid fa-plus";
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



async function loadSettings() {
    try {
        const startup = await pywebview.api.get_startup_status();
        document.getElementById('chk-startup').checked = startup.enabled;

        const tray = await pywebview.api.get_tray_status();
        document.getElementById('chk-tray').checked = tray.enabled;

        const themeRes = await pywebview.api.get_theme();
        if (themeRes.status === "success") {
            // Update visual selector
            document.querySelectorAll('.theme-card').forEach(c => {
                c.classList.remove('active');
                if (c.dataset.theme === themeRes.theme) c.classList.add('active');
            });
            applyTheme(themeRes.theme);
        }

        // Load firmware version
        const versionRes = await pywebview.api.get_firmware_version();
        if (versionRes.status === "success") {
            updateFirmwareVersionDisplay(versionRes.version);
        }
    } catch (e) {
        console.error("Error loading settings:", e);
    }
}

function applyTheme(theme) {
    if (theme === "light") {
        document.documentElement.setAttribute('data-theme', 'light');
    } else {
        document.documentElement.removeAttribute('data-theme');
    }
}

function updateFirmwareVersionDisplay(version) {
    const display = document.getElementById('firmware-version-display');
    if (display) {
        display.innerText = `Firmware: v${version}`;
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
                await showAlert("Error", "Invalid port selection");
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

            titleEl.innerText = "Success";
            titleEl.style.display = "none"; // Hide the Success title

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
        // Media
        "Volume Up",
        "Volume Down",
        "Mute",
        "Play/Pause",
        "Next Track",
        "Previous Track"
    ];
    const customMacros = Object.keys(profiles[currentProfile].macros || {});

    // -- LEGACY TAB CONTENT --
    systemMacros.forEach(macroName => {
        const item = document.createElement('div');
        item.className = 'macro-item';
        item.setAttribute('role', 'button');
        item.setAttribute('tabindex', '0');
        item.setAttribute('aria-label', `Assign ${macroName} macro`);

        // check for no macro
        if (macroName === "No Macro") {
            item.innerHTML = `<i class="fa-solid fa-ban"></i> <span>${macroName}</span>`;
        } else {
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
            const item = document.createElement('div');
            item.className = 'macro-item';
            item.setAttribute('role', 'button');
            item.setAttribute('tabindex', '0');
            item.setAttribute('aria-label', `Assign ${macroName} macro`);

            // Item content wrapper for alignment
            const content = document.createElement('div');
            content.style.display = 'flex';
            content.style.alignItems = 'center';
            content.style.gap = '10px';
            content.style.flex = '1';
            content.innerHTML = `<i class="fa-solid fa-keyboard"></i> <span>${macroName}</span>`;
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
        if (profiles[currentProfile].macros && profiles[currentProfile].macros[macroName]) {
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
        document.getElementById('connection-toggle').checked = false;
        return;
    }

    // Auto connect to first port for now
    const port = ports[0][0];
    const result = await pywebview.api.connect_serial(port);

    if (result.connected) {
        setConnected(true, port);
    } else {
        if (!silent) await showAlert("Connection", "Failed to connect");
        document.getElementById('connection-toggle').checked = false;
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
    const statusText = document.getElementById('status-text');
    const indicator = document.querySelector('.status-indicator');
    const toggle = document.getElementById('connection-toggle');

    if (connected) {
        statusText.innerText = `Connected to ${portName}`;
        indicator.classList.add('connected');
        toggle.checked = true;
    } else {
        statusText.innerText = "Disconnected";
        indicator.classList.remove('connected');
        toggle.checked = false;
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

window.addEventListener('keydown', (e) => handleRecordingKey(e, 'down'));
window.addEventListener('keyup', (e) => handleRecordingKey(e, 'up'));

function openMacroEditor(macroName = null) {
    macroModal.style.display = "flex";
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
        }
    } else {
        nameInput.value = "";
    }
}

// Specific cancel button handler
document.getElementById('btn-cancel-macro-editor').addEventListener('click', () => {
    closeMacroEditor();
});

function closeMacroEditor() {
    macroModal.style.display = "none";
    if (isRecording) {
        toggleRecording();
    }
}

function toggleRecording() {
    isRecording = !isRecording;
    if (isRecording) {
        // Reset or appending? The logic clears on open, but here we might append.
        // Let's keep appending.
        if (recordedKeys.length === 0) actLastEventTime = Date.now();
        else actLastEventTime = Date.now(); // Reset delta base on start
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
        await showAlert("Error", "Please enter a macro name");
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

    if (activeTab === "launch") {
        const path = document.getElementById('launch-path-input').value.trim();
        if (!path) {
            await showAlert("Error", "Please enter a path or URL");
            return;
        }
        macroData.type = "launch";
        macroData.path = path;
    } else if (activeTab === "command") { // New
        const cmd = document.getElementById('command-input').value.trim();
        if (!cmd) {
            await showAlert("Error", "Please enter a command");
            return;
        }
        macroData.type = "command";
        macroData.command = cmd;
    } else {
        // Keystrokes
        if (recordedKeys.length === 0) {
            await showAlert("Error", "Please record at least one key");
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
// LINK APP MODAL LOGIC
// ====================

async function showLinkAppModal() {
    const modal = document.getElementById('link-app-modal');
    const list = document.getElementById('active-apps-list');
    const input = document.getElementById('manual-app-input');
    const btnConfirm = document.getElementById('link-modal-confirm');
    const btnCancel = document.getElementById('link-modal-cancel');
    const btnClose = document.getElementById('link-modal-close');
    const btnRefresh = document.getElementById('btn-refresh-apps');

    // Clear prev state
    input.value = "";

    // Fetch currently linked app to pre-fill
    try {
        const result = await pywebview.api.get_linked_app(currentProfile);
        if (result.status === 'success' && result.apps.length > 0) {
            input.value = result.apps[0];
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

        try {
            const res = await pywebview.api.link_app_to_profile(currentProfile, appExe);
            if (res.status === 'success') {
                showToast(`Linked ${appExe} to ${currentProfile}`, "success");
                closeModal();
                // Update button state to show green color
                await updateLinkAppButtonState();
            } else {
                showToast(res.message, "error");
            }
        } catch (e) {
            showToast("Failed to link app", "error");
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

        if (res.status === 'success' && res.apps.length > 0) {
            res.apps.forEach(app => {
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

// Update Link App button state based on settings
async function updateLinkAppButtonState() {
    const btn = document.getElementById('btn-link-app');
    if (!btn) return;

    try {
        const status = await pywebview.api.get_auto_switch_status();
        if (status && status.enabled) {
            btn.disabled = false;
            btn.style.opacity = '1';
            btn.style.cursor = 'pointer';

            // Check if current profile has linked apps
            try {
                const linkedApps = await pywebview.api.get_linked_app(currentProfile);
                if (linkedApps.status === 'success' && linkedApps.apps && linkedApps.apps.length > 0) {
                    btn.classList.add('linked');
                } else {
                    btn.classList.remove('linked');
                }
            } catch (e) {
                console.error("Error checking linked apps:", e);
                btn.classList.remove('linked');
            }
        } else {
            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.style.cursor = 'not-allowed';
            btn.classList.remove('linked');
        }
    } catch (e) {
        console.error("Error updating Link App button:", e);
    }
}
