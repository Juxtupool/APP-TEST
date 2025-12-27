// ====================
// COMMUNITY MACRO HUB
// ====================

let currentFilter = 'all';
let currentSort = 'recent';
let communityMacros = [];

// Initialize Community features
async function initCommunity() {
    // Load auto-switch status
    try {
        const status = await pywebview.api.get_auto_switch_status();
        document.getElementById('chk-auto-switch').checked = status.enabled;
    } catch (e) {
        console.error("Error loading auto-switch status:", e);
    }

    // Auto-switch toggle listener
    document.getElementById('chk-auto-switch').addEventListener('change', async (e) => {
        const enabled = e.target.checked;
        await pywebview.api.set_auto_switch_enabled(enabled);

        // Update Link App button if available
        if (typeof updateLinkAppButtonState === 'function') {
            await updateLinkAppButtonState();
        }
    });

    // Community search
    const communitySearch = document.getElementById('community-search');
    if (communitySearch) {
        let debounceTimer;
        communitySearch.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => searchCommunityMacros(e.target.value), 300);
        });
    }

    // Filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            currentFilter = btn.dataset.filter;
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            displayCommunityMacros();
        });
    });

    // Sort dropdown
    const sortDropdown = document.getElementById('community-sort');
    if (sortDropdown) {
        sortDropdown.addEventListener('change', (e) => {
            currentSort = e.target.value;
            displayCommunityMacros();
        });
    }

    // Submit button
    const submitBtn = document.querySelector('.community-btn-submit');
    if (submitBtn) {
        submitBtn.addEventListener('click', showSubmitMacroModal);
    }

    // Check for firmware updates automatically
    checkFirmwareUpdatesInBackground();
}

// Load community macros
async function loadCommunityMacros() {
    const grid = document.getElementById('community-macros-grid');
    if (!grid) return;

    grid.innerHTML = '<div class="community-loading"><i class="fa-solid fa-spinner"></i><p>Loading community macros...</p></div>';

    try {
        const result = await pywebview.api.get_community_macros();

        if (result.status === 'success') {
            communityMacros = result.macros;
            displayCommunityMacros();
        } else {
            grid.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-exclamation-triangle"></i>
                    <h4>Could not load macros</h4>
                    <p>${result.message || 'Configure GitHub repository in config.json'}</p>
                </div>
            `;
        }
    } catch (e) {
        console.error("Error loading community macros:", e);
        grid.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-cloud-arrow-down"></i>
                <h4>No Community Macros</h4>
                <p>Configure GitHub repository in config.json to browse community macros</p>
            </div>
        `;
    }
}

// Display filtered macros
function displayCommunityMacros() {
    const grid = document.getElementById('community-macros-grid');
    if (!grid) return;

    let filtered = communityMacros;

    // Apply filter
    if (currentFilter !== 'all') {
        filtered = communityMacros.filter(m => {
            const metadata = m._metadata || {};
            return metadata.category === currentFilter;
        });
    }

    // Apply sorting
    filtered = [...filtered]; // Create a copy to avoid mutating original
    // Sorting logic (and Type filtering if via Sort menu)
    if (currentSort === 'recent') {
        // Assume recent is default order or based on upload date if available
        filtered.sort((a, b) => {
            const dateA = new Date(a.uploaded_at || 0);
            const dateB = new Date(b.uploaded_at || 0);
            return dateB - dateA;
        });
    } else if (currentSort === 'downloads') {
        filtered.sort((a, b) => (b.downloads || 0) - (a.downloads || 0));
    } else if (currentSort === 'likes') {
        filtered.sort((a, b) => (b.likes || 0) - (a.likes || 0));
    } else if (currentSort === 'profiles_only') {
        filtered = filtered.filter(m => m.type === 'profile');
    } else if (currentSort === 'macros_only') {
        filtered = filtered.filter(m => m.type === 'macro' || !m.type);
    }

    if (filtered.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-filter"></i>
                <h4>No macros found</h4>
                <p>Try a different filter or search term</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = filtered.map(macro => createMacroCard(macro)).join('');

    // Add event listeners
    grid.querySelectorAll('.macro-card-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const macroData = JSON.parse(btn.dataset.macro);
            await installCommunityMacro(macroData);
        });
    });
}

// Search community macros
async function searchCommunityMacros(query) {
    if (!query || query.trim() === '') {
        displayCommunityMacros();
        return;
    }

    const grid = document.getElementById('community-macros-grid');
    grid.innerHTML = '<div class="community-loading"><i class="fa-solid fa-spinner"></i><p>Searching...</p></div>';

    try {
        const result = await pywebview.api.get_community_macros(null, query);

        if (result.status === 'success') {
            communityMacros = result.macros;
            currentFilter = 'all';
            displayCommunityMacros();
        } else {
            grid.innerHTML = `<div class="empty-state"><i class="fa-solid fa-search"></i><h4>No results</h4></div>`;
        }
    } catch (e) {
        console.error("Search error:", e);
    }
}

// Create macro card HTML
function createMacroCard(macro) {
    const metadata = macro._metadata || {};
    const category = metadata.category || 'other';
    const tags = (macro.tags || []).slice(0, 3);
    const isProfile = macro.type === 'profile';

    // Icon based on type/category
    let iconClass = 'fa-solid fa-bolt';
    if (isProfile) {
        iconClass = 'fa-solid fa-layer-group';
    } else {
        if (category === 'productivity') iconClass = 'fa-solid fa-briefcase';
        else if (category === 'creative') iconClass = 'fa-solid fa-palette';
        else if (category === 'gaming') iconClass = 'fa-solid fa-gamepad';
        else if (category === 'entertainment') iconClass = 'fa-solid fa-music';
    }

    const macroJson = JSON.stringify(macro).replace(/"/g, '&quot;');
    const cardClass = isProfile ? 'macro-card community-origin is-profile' : 'macro-card community-origin';
    const buttonText = isProfile ? 'Add Profile' : 'Add Macro';
    const buttonIcon = isProfile ? 'fa-download' : 'fa-plus';

    const dateStr = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

    return `
        <div class="${cardClass}">
            <div class="community-badge" ${isProfile ? 'style="background: rgba(245, 158, 11, 0.15); color: #F59E0B;"' : ''}>${isProfile ? 'Profile' : 'Macro'}</div>
            <div class="macro-card-header">
                <div class="macro-card-icon" ${isProfile ? 'style="background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%); box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);"' : ''}>
                    <i class="${iconClass}"></i>
                </div>
                <div class="macro-card-info">
                    <h3 class="macro-card-title">${escapeHtml(macro.name || 'Unnamed')}</h3>
                    <div class="macro-card-author">
                        <i class="fa-solid fa-user"></i>
                        ${escapeHtml(macro.author || 'Anonymous')}
                    </div>
                </div>
            </div>
            <p class="macro-card-description">${escapeHtml(macro.description || 'No description provided')}</p>
            ${tags.length > 0 ? `
                <div class="macro-card-tags">
                    ${tags.map(tag => `<span class="macro-tag">#${escapeHtml(tag)}</span>`).join('')}
                </div>
            ` : ''}
            <div class="macro-card-footer">
                <div class="macro-card-stats">
                    <div class="macro-stat">
                        <i class="fa-solid fa-download"></i>
                        <span>${macro.downloads || 0}</span>
                    </div>
                    <div class="macro-stat" style="margin-left: 12px;">
                        <i class="fa-solid fa-calendar" style="font-size: 0.7rem;"></i>
                        <span style="font-size: 0.75rem;">${dateStr}</span>
                    </div>
                </div>
                <button class="macro-card-btn ${isProfile ? 'btn-profile' : ''}" data-macro="${macroJson}" ${isProfile ? 'style="background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%);"' : ''}>
                    <i class="fa-solid ${buttonIcon}"></i>
                    ${buttonText}
                </button>
            </div>
        </div>
    `;
}

// Install community macro
async function installCommunityMacro(macroData) {
    try {
        const result = await pywebview.api.install_community_macro(macroData);

        if (result.status === 'success') {
            if (result.type === 'profile') {
                await showAlert("Success", `Installed profile "${result.name}" and switched to it!`, "success");
                // Refresh profiles
                if (typeof loadProfiles === 'function') {
                    await loadProfiles();
                } else {
                    location.reload(); // Fallback if loadProfiles isn't available in scope
                }
            } else {
                await showAlert("Success", `Installed "${result.name}" to your library!`, "success");
                // Refresh macro list
                if (typeof updateMacroList === 'function') {
                    updateMacroList();
                }
            }
        } else {
            await showAlert("Error", result.message || "Failed to install item");
        }
    } catch (e) {
        console.error("Install error:", e);
        await showAlert("Error", "Failed to install item");
    }
}

// Show submit macro modal
async function showSubmitMacroModal() {
    const modal = document.getElementById('submit-macro-modal');
    const macroSelectGroup = document.getElementById('macro-select-group');
    const profileSelectGroup = document.getElementById('profile-select-group');
    const macroSelect = document.getElementById('submit-macro-select');
    const profileSelect = document.getElementById('submit-profile-select');

    // Populate macro dropdown from current profile
    macroSelect.innerHTML = '<option value="">-- Choose a macro --</option>';
    const currentProfileData = profiles[currentProfile];
    if (currentProfileData && currentProfileData.macros) {
        Object.keys(currentProfileData.macros).forEach(macroName => {
            const option = document.createElement('option');
            option.value = macroName;
            option.textContent = macroName;
            macroSelect.appendChild(option);
        });
    }

    // Populate profile dropdown
    profileSelect.innerHTML = '<option value="">-- Choose a profile --</option>';
    Object.keys(profiles).forEach(profileName => {
        const option = document.createElement('option');
        option.value = profileName;
        option.textContent = profileName;
        profileSelect.appendChild(option);
    });

    // Radio button toggle logic
    const radioButtons = modal.querySelectorAll('input[name="submit-type"]');
    radioButtons.forEach(radio => {
        radio.addEventListener('change', (e) => {
            if (e.target.value === 'macro') {
                macroSelectGroup.style.display = 'block';
                profileSelectGroup.style.display = 'none';
            } else {
                macroSelectGroup.style.display = 'none';
                profileSelectGroup.style.display = 'block';
            }
        });
    });

    // Show modal
    modal.style.display = 'flex';
    setTimeout(() => modal.classList.add('active'), 10);

    // Handle close
    const closeModal = () => {
        modal.classList.remove('active');
        setTimeout(() => modal.style.display = 'none', 200);
    };

    // Note: submit-modal-close button removed from HTML
    document.getElementById('submit-modal-cancel').onclick = closeModal;

    // Handle submit
    document.getElementById('submit-modal-confirm').onclick = async () => {
        const type = modal.querySelector('input[name="submit-type"]:checked').value;
        const creator = document.getElementById('submit-creator').value.trim();
        const description = document.getElementById('submit-description').value.trim();
        const tags = document.getElementById('submit-tags').value.trim();
        const category = document.getElementById('submit-category').value;

        // Validation
        if (!creator) {
            await showAlert("Error", "Please enter your name");
            return;
        }
        if (!description) {
            await showAlert("Error", "Please provide a description");
            return;
        }

        let submissionData;

        if (type === 'macro') {
            const selectedMacro = macroSelect.value;
            if (!selectedMacro) {
                await showAlert("Error", "Please select a macro");
                return;
            }

            const macroData = currentProfileData.macros[selectedMacro];
            submissionData = {
                name: selectedMacro,
                author: creator,
                description: description,
                category: category,
                tags: tags.split(',').map(t => t.trim()).filter(t => t),
                type: 'macro',
                macro: macroData
            };
        } else {
            const selectedProfile = profileSelect.value;
            if (!selectedProfile) {
                await showAlert("Error", "Please select a profile");
                return;
            }

            const profileData = profiles[selectedProfile];
            submissionData = {
                name: selectedProfile,
                author: creator,
                description: description,
                category: category,
                tags: tags.split(',').map(t => t.trim()).filter(t => t),
                type: 'profile',
                profile: {
                    macros: profileData.macros || {},
                    keys: profileData.keys || {},
                    knobs: profileData.knobs || {},
                    knob_mode: profileData.knob_mode || 'Standard'
                }
            };
        }

        // Close modal
        closeModal();

        // Submit Macro directly
        try {
            const result = await pywebview.api.submit_community_macro(submissionData);
            if (result.status === 'success') {
                await showAlert("Success", "Macro submitted to Community Library!", "success");
                // Refresh to show it
                currentFilter = 'all'; // Reset filter to show all
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                document.querySelector('.filter-btn[data-filter="all"]').classList.add('active');
                setTimeout(() => loadCommunityMacros(), 1000); // Small delay for GitHub API propagation
            } else {
                await showAlert("Error", result.message || "Failed to submit macro");
            }
        } catch (e) {
            console.error("Submission error:", e);
            await showAlert("Error", "Failed to submit macro");
        }
    };
}

// ====================
// FIRMWARE UPDATES
// ====================

async function checkFirmwareUpdatesInBackground() {
    // Don't block page load
    setTimeout(async () => {
        try {
            const result = await pywebview.api.check_firmware_updates();

            if (result.status === 'success' && result.data.update_available) {
                showUpdateNotification(result.data);
            }
        } catch (e) {
            // console.log("Update check failed:", e);  // [DEBUG - Disabled in production]
        }
    }, 5000); // Check 5 seconds after load
}

function showUpdateNotification(updateData) {
    // Show notification badge on Settings
    const settingsNav = document.querySelector('.nav-item[data-page="settings"]');
    if (settingsNav && !settingsNav.querySelector('.update-badge')) {
        const badge = document.createElement('span');
        badge.className = 'update-badge';
        badge.style.cssText = `
            position: absolute;
            top: 8px;
            right: 8px;
            width: 8px;
            height: 8px;
            background: #ef4444;
            border-radius: 50%;
            box-shadow: 0 0 0 2px var(--sidebar-bg);
        `;
        settingsNav.style.position = 'relative';
        settingsNav.appendChild(badge);
    }

    // Show toast notification
    // console.log(`Firmware update available: ${updateData.latest_version}`);  // [DEBUG - Disabled in production]
}

// ====================
// AUTO-PROFILE SWITCH CALLBACK
// ====================

// Called from Python when profile auto-switches
window.onAutoProfileSwitch = function (profileName) {
    // console.log("Auto-switched to profile:", profileName);  // [DEBUG - Disabled in production]

    // Show toast notification
    showToast(`Switched to "${profileName}" profile`, "info");

    // Reload profiles to update UI
    loadProfiles();
};

// ====================
// HELPER FUNCTIONS
// ====================

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function showToast(message, type = "info") {
    // Simple toast notification (you can enhance this)
    // console.log(`[${type.toUpperCase()}] ${message}`);  // [DEBUG - Disabled in production]

    // Optional: Create visual toast
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        background: var(--card-bg);
        color: var(--text-primary);
        padding: 16px 24px;
        border-radius: 12px;
        box-shadow: var(--shadow-md);
        border: 1px solid var(--border-color);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Add CSS for toast animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Initialize on page load
window.addEventListener('DOMContentLoaded', () => {
    initCommunity();
});

// Load macros when navigating to community page
window.addEventListener('pageshow', (e) => {
    const communityPage = document.getElementById('page-community');
    if (communityPage && communityPage.classList.contains('active')) {
        loadCommunityMacros();
    }
});
