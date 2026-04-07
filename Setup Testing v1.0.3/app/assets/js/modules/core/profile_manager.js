// Profile Management Module
// Handles loading, saving, creating, deleting, and switching profiles
// Depends on: state.js (for global state), dialogs.js (for UI), app.js (for updateUIForProfile)

let profileSaveTimeout = null;

async function loadProfiles() {
    try {
        const data = await pywebview.api.get_profiles();
        // Update global state
        window.profiles = data.profiles;
        if (window.State) window.State.profiles = window.profiles;

        // Check for persistent active profile
        if (data.active_profile && window.profiles[data.active_profile]) {
            window.currentProfile = data.active_profile;
        }

        // Sync State
        if (window.State) window.State.currentProfile = window.currentProfile;

        const select = document.getElementById('profile-select');
        const dropdownMenu = document.getElementById('profile-dropdown-menu'); // Custom Dropdown

        if (select) select.innerHTML = '';
        if (dropdownMenu) dropdownMenu.innerHTML = '';

        Object.keys(window.profiles).forEach(name => {
            // Native Option
            if (select) {
                const option = document.createElement('option');
                option.value = name;
                option.innerText = name;
                select.appendChild(option);
            }

            // Custom Item
            if (dropdownMenu) {
                const item = document.createElement('div');
                item.className = 'dropdown-item';
                item.dataset.value = name;
                item.innerText = name;

                item.addEventListener('click', () => {
                    switchProfile(name);

                    // Update Dropdown UI
                    document.querySelectorAll('#profile-dropdown-menu .dropdown-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                    const btn = document.getElementById('btn-profile-dropdown');
                    if (btn) {
                        btn.classList.remove('active');
                        const label = document.getElementById('profile-label');
                        if (label) label.innerText = name;
                    }
                    dropdownMenu.classList.remove('show');
                });

                dropdownMenu.appendChild(item);
            }
        });

        // Set current profile
        if (window.profiles[window.currentProfile]) {
            if (select) select.value = window.currentProfile;
        } else {
            // Fallback if current profile doesn't exist
            window.currentProfile = Object.keys(window.profiles)[0] || "Default Profile";
            if (window.State) window.State.currentProfile = window.currentProfile;
            if (select) select.value = window.currentProfile;
        }

        if (window.updateUIForProfile) window.updateUIForProfile();

    } catch (e) {
        console.error("Error loading profiles:", e);
    }
}

function switchProfile(name) {
    window.currentProfile = name;

    // Sync State
    if (window.State) {
        window.State.currentProfile = window.currentProfile;
    }

    pywebview.api.set_active_profile(name);
    if (window.updateUIForProfile) window.updateUIForProfile();
}

async function createProfile() {
    const name = await window.showPrompt("New Profile", "Enter profile name (max 30 characters):");
    if (!name) return;

    // Validate name
    if (window.CONSTANTS && name.length > window.CONSTANTS.PROFILE_NAME_MAX_LENGTH) {
        await window.showAlert("", `Profile name must be ${window.CONSTANTS.PROFILE_NAME_MAX_LENGTH} characters or less`, "danger");
        return;
    }

    if (!/^[a-zA-Z0-9\s_-]+$/.test(name)) {
        await window.showAlert("", "Profile name can only contain letters, numbers, spaces, hyphens, and underscores", "danger");
        return;
    }

    if (window.profiles[name]) {
        await window.showAlert("", "Profile already exists", "danger");
        return;
    }

    window.profiles[name] = { macros: {}, keys: {}, knobs: {} };
    await saveProfiles(true); // Immediate save
    await loadProfiles();
    switchProfile(name);
}

async function deleteProfile() {

    if (window.currentProfile === "Default Profile") {
        await window.showAlert("", "Cannot delete Default Profile", "danger");
        return;
    }
    const confirmDelete = await window.showConfirm("Delete Profile", `Are you sure you want to delete "${window.currentProfile}"?`, "danger", "Delete");

    if (confirmDelete) {
        if (window.profiles[window.currentProfile]) {
            delete window.profiles[window.currentProfile];

            // Sync State before saving
            if (window.State) window.State.profiles = window.profiles;

            window.currentProfile = "Default Profile";
            if (window.State) window.State.currentProfile = window.currentProfile;

            await saveProfiles(true); // Immediate save
            await loadProfiles();
        } else {
            console.error("Profile not found in object:", window.currentProfile);
        }
    }
}

async function editProfile() {
    if (window.currentProfile === "Default Profile") {
        await window.showAlert("", "Cannot rename Default Profile", "danger");
        return;
    }
    const newName = await window.showPrompt("Rename Profile", "Enter new profile name (max 30 characters):", window.currentProfile);
    if (!newName) return;

    if (newName === window.currentProfile) return; // No change

    // Validate name
    if (window.CONSTANTS && newName.length > window.CONSTANTS.PROFILE_NAME_MAX_LENGTH) {
        await window.showAlert("", `Profile name must be ${window.CONSTANTS.PROFILE_NAME_MAX_LENGTH} characters or less`, "danger");
        return;
    }

    if (!/^[a-zA-Z0-9\s_-]+$/.test(newName)) {
        await window.showAlert("", "Profile name can only contain letters, numbers, spaces, hyphens, and underscores", "danger");
        return;
    }

    if (window.profiles[newName]) {
        await window.showAlert("", "Profile already exists", "danger");
        return;
    }

    // Copy data to new key
    window.profiles[newName] = window.profiles[window.currentProfile];
    delete window.profiles[window.currentProfile];
    window.currentProfile = newName;

    if (window.State) {
        window.State.profiles = window.profiles;
        window.State.currentProfile = window.currentProfile;
    }

    await saveProfiles(true); // Immediate save
    await loadProfiles();
    switchProfile(newName);
}

async function saveProfiles(immediate = false) {
    // console.log("Saving profiles...", Object.keys(window.profiles));

    const doSave = async () => {
        try {
            const result = await pywebview.api.save_profiles({ profiles: window.profiles });
            // console.log("Save result:", result);
            if (result && result.status === "error") {
                console.error("Failed to save profiles:", result.message);
                await window.showAlert("Save Error", "Failed to save changes: " + result.message, "danger");
                return false;
            }
            return true;
        } catch (e) {
            console.error("Save API Exception:", e);
            return false;
        }
    };

    if (immediate) {
        if (profileSaveTimeout) {
            clearTimeout(profileSaveTimeout);
            profileSaveTimeout = null;
        }
        return await doSave();
    }

    if (profileSaveTimeout) {
        clearTimeout(profileSaveTimeout);
    }

    profileSaveTimeout = setTimeout(doSave, 500);
}

// Expose to Global Scope for legacy compatibility
window.loadProfiles = loadProfiles;
window.switchProfile = switchProfile;
window.createProfile = createProfile;
window.deleteProfile = deleteProfile;
window.editProfile = editProfile;
window.saveProfiles = saveProfiles;
