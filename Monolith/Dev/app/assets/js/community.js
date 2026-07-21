// ====================
// COMMUNITY MACRO HUB
// ====================

let currentFilter = 'all';
let currentSort = 'recent';
let communityMacros = [];
let fullCommunityMacrosCache = []; // Cache for client-side search/reset
let userStarredMacros = [];

async function syncStarredMacros() {
    try {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.get_starred_macros) {
            const res = await window.pywebview.api.get_starred_macros();
            if (res && res.status === 'success' && Array.isArray(res.starred)) {
                userStarredMacros = res.starred;
                try {
                    localStorage.setItem('starred_macros', JSON.stringify(userStarredMacros));
                } catch (e) {}
                return;
            }
        }
    } catch (e) {
        console.error("Error syncing starred macros:", e);
    }
    try {
        userStarredMacros = JSON.parse(localStorage.getItem('starred_macros') || '[]');
    } catch (e) {
        userStarredMacros = [];
    }
}

// Initialize Community features
async function initCommunity() {

    // Community search
    const communitySearch = document.getElementById('community-search');
    if (communitySearch) {
        // Use standard debounce from app.js if available, or local
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

    // Refresh button
    const refreshBtn = document.getElementById('btn-community-refresh');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            // Add spinning animation
            const icon = refreshBtn.querySelector('i');
            icon.classList.add('fa-spin');
            loadCommunityMacros(true).then(() => {
                setTimeout(() => icon.classList.remove('fa-spin'), 500);
            });
        });
    }

    // Check for firmware updates automatically - REMOVED (Moved to app.js central check)
    // checkFirmwareUpdatesInBackground();
}

// Load community macros
async function loadCommunityMacros(forceRefresh = false) {
    const grid = document.getElementById('community-macros-grid');
    if (!grid) return;

    await syncStarredMacros();

    // Only show loading if we don't have a cache yet, or if forced
    if (fullCommunityMacrosCache.length === 0 || forceRefresh) {
        grid.innerHTML = '<div class="community-loading"><i class="fa-solid fa-spinner"></i><p>Loading community macros...</p></div>';
    }

    try {
        // Pass forceRefresh to API (requires update in api.py)
        const result = await pywebview.api.get_community_macros(null, null, forceRefresh);

        if (result.status === 'success') {
            communityMacros = result.macros;
            fullCommunityMacrosCache = result.macros; // Update Cache
            displayCommunityMacros();
        } else {
            grid.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-exclamation-triangle"></i>
                    <h4>Could not load macros</h4>
                    <p>${result.message || 'Unable to connect to community library'}</p>
                </div>
            `;
        }
    } catch (e) {
        console.error("Error loading community macros:", e);
        grid.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-cloud-arrow-down"></i>
                <h4>No Community Macros</h4>
                <p>Unable to connect to community library</p>
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
            // Check top-level category first (from JSON content), then metadata (folder name)
            // Convert to lowercase to be safe
            const cat = (m.category || (m._metadata && m._metadata.category) || '').toLowerCase();
            return cat === currentFilter.toLowerCase();
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
        filtered = filtered.filter(m => m.type !== 'profile');
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
            try {
                const macroData = JSON.parse(decodeURIComponent(btn.dataset.macro));
                await installCommunityMacro(macroData);
            } catch (err) {
                console.error("Error parsing macro data:", err);
                showAlert("", "Corrupted macro data", "danger");
            }
        });
    });

    // Add event listeners for stars
    grid.querySelectorAll('.clickable-star-btn').forEach(starBtn => {
        starBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const macroId = starBtn.dataset.id;
            if (!macroId) return;

            const isStarred = starBtn.classList.contains('starred');
            let starred = [];
            try {
                starred = JSON.parse(localStorage.getItem('starred_macros') || '[]');
            } catch (err) {
                starred = [];
            }

            const card = starBtn.closest('.macro-card');
            const countEl = card ? card.querySelector('.like-count') : null;
            const macroObj = communityMacros.find(m => m.id === macroId);

            if (isStarred) {
                // Toggle OFF: unstar and decrement count
                starBtn.classList.remove('starred');
                starBtn.title = "Star macro";
                userStarredMacros = userStarredMacros.filter(id => id !== macroId);
                try {
                    localStorage.setItem('starred_macros', JSON.stringify(userStarredMacros));
                } catch (err) {}

                let newLikes = Math.max(0, (macroObj ? macroObj.likes : parseInt(countEl ? countEl.textContent : '1')) - 1);
                if (countEl) countEl.textContent = newLikes;
                if (macroObj) macroObj.likes = newLikes;

                try {
                    if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_star_macro_state) {
                        window.pywebview.api.toggle_star_macro_state(macroId, false);
                    }
                    const result = await pywebview.api.unlike_community_macro(macroId);
                    if (result && result.status === 'success') {
                        if (countEl) countEl.textContent = result.likes;
                        if (macroObj) macroObj.likes = result.likes;
                    }
                } catch (err) {
                    console.error("Unstar error:", err);
                }
            } else {
                // Toggle ON: star and increment count
                starBtn.classList.add('starred');
                starBtn.title = "Starred";
                if (!userStarredMacros.includes(macroId)) {
                    userStarredMacros.push(macroId);
                    try {
                        localStorage.setItem('starred_macros', JSON.stringify(userStarredMacros));
                    } catch (err) {}
                }

                let newLikes = (macroObj ? macroObj.likes : parseInt(countEl ? countEl.textContent : '0')) + 1;
                if (countEl) countEl.textContent = newLikes;
                if (macroObj) macroObj.likes = newLikes;

                try {
                    if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_star_macro_state) {
                        window.pywebview.api.toggle_star_macro_state(macroId, true);
                    }
                    const result = await pywebview.api.like_community_macro(macroId);
                    if (result && result.status === 'success') {
                        if (countEl) countEl.textContent = result.likes;
                        if (macroObj) macroObj.likes = result.likes;
                    } else {
                        starBtn.classList.remove('starred');
                        starBtn.title = "Star macro";
                    }
                } catch (err) {
                    console.error("Star error:", err);
                    starBtn.classList.remove('starred');
                    starBtn.title = "Star macro";
                }
            }
        });
    });


}

// Search community macros (Client-Side)
async function searchCommunityMacros(query) {
    if (!query || query.trim() === '') {
        // Reset to full cache
        communityMacros = [...fullCommunityMacrosCache];
        displayCommunityMacros();
        return;
    }

    // Client-side Filter
    const lowerQ = query.toLowerCase();

    communityMacros = fullCommunityMacrosCache.filter(m => {
        const name = (m.name || '').toLowerCase();
        const desc = (m.description || '').toLowerCase();
        const author = (m.author || '').toLowerCase();

        return name.includes(lowerQ) || desc.includes(lowerQ) || author.includes(lowerQ);
    });

    displayCommunityMacros();
}



// Create macro card HTML
function createMacroCard(macro) {
    const metadata = macro._metadata || {};
    const category = (macro.category || metadata.category || 'other').toLowerCase();
    const isProfile = macro.type === 'profile';
    const macroName = macro.name || 'Unnamed';

    // Check if already installed
    let isInstalled = false;
    if (isProfile) {
        isInstalled = window.profiles && window.profiles[macroName] !== undefined;
    } else {
        if (typeof window.getUserMacroData === 'function') {
            isInstalled = window.getUserMacroData(macroName) !== null;
        } else {
            const activeProfile = window.currentProfile;
            if (window.profiles && activeProfile && window.profiles[activeProfile]) {
                const profileMacros = window.profiles[activeProfile].macros || {};
                isInstalled = profileMacros[macroName] !== undefined;
            }
        }
    }

    // Icon based on type/category
    let iconClass = 'fa-solid fa-bolt';
    if (isProfile) {
        iconClass = 'fa-solid fa-layer-group';
    } else {
        if (category === 'productivity') iconClass = 'fa-solid fa-briefcase';
        else if (category === 'creative') iconClass = 'fa-solid fa-palette';
        else if (category === 'gaming') iconClass = 'fa-solid fa-gamepad';
        else if (category === 'entertainment') iconClass = 'fa-solid fa-music';
        else if (category === 'office') iconClass = 'fa-solid fa-folder-open';
    }

    // Safe encoding for data attribute
    const macroJson = encodeURIComponent(JSON.stringify(macro));

    const cardClass = isProfile ? 'macro-card community-origin is-profile' : 'macro-card community-origin';
    const buttonText = isProfile ? 'Add Profile' : 'Add Macro';
    const buttonIcon = isProfile ? 'fa-download' : 'fa-plus';

    const uploadDate = macro.uploaded_at || macro.created_at || null;
    let dateStr = "Unknown";
    if (uploadDate) {
        dateStr = new Date(uploadDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }
    const likes = macro.likes || 0;
    const downloads = macro.downloads || 0;

    // Check if user has already starred this macro
    let starredMacros = userStarredMacros;
    if (!starredMacros || starredMacros.length === 0) {
        try {
            starredMacros = JSON.parse(localStorage.getItem('starred_macros') || '[]');
        } catch (e) {
            starredMacros = [];
        }
    }
    const isStarred = macro.id && starredMacros.includes(macro.id);

    let buttonHtml = '';
    if (isInstalled) {
        buttonHtml = `
            <button class="macro-card-btn installed" disabled>
                <i class="fa-solid fa-check"></i> Installed
            </button>
        `;
    } else {
        buttonHtml = `
            <button class="macro-card-btn ${isProfile ? 'btn-profile' : ''}" data-macro="${macroJson}">
                <i class="fa-solid ${buttonIcon}"></i>
                ${buttonText}
            </button>
        `;
    }

    return `
        <div class="${cardClass}">
            <div class="community-badge ${isProfile ? 'badge-profile' : ''}">${isProfile ? 'Profile' : 'Macro'}</div>
            <div class="macro-card-header">
                <div class="macro-card-icon ${isProfile ? 'profile' : category}">
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
            <div class="macro-card-stats">
                <span class="stat-item">
                    <i class="fa-solid fa-star"></i> <span class="like-count">${likes}</span>
                </span>
                <span class="stat-item"><i class="fa-solid fa-download"></i> ${downloads}</span>
                <span class="stat-item date"><i class="fa-solid fa-calendar"></i> ${dateStr}</span>
            </div>
            <div class="macro-card-footer">
                ${buttonHtml}
                <button class="macro-star-btn clickable-star-btn ${isStarred ? 'starred' : ''}" data-id="${macro.id || ''}" title="${isStarred ? 'Starred' : 'Star macro'}">
                    <i class="fa-solid fa-star"></i>
                </button>
            </div>
        </div>
    `;
}

// Install community macro
async function installCommunityMacro(macroData) {
    try {
        let downloadedMacros = [];
        try {
            downloadedMacros = JSON.parse(localStorage.getItem('downloaded_macros') || '[]');
        } catch (e) {}
        const isAlreadyDownloaded = macroData.id && downloadedMacros.includes(macroData.id);

        const result = await pywebview.api.install_community_macro(macroData, !isAlreadyDownloaded);

        if (result.status === 'success') {
            if (macroData.id && !isAlreadyDownloaded) {
                try {
                    downloadedMacros.push(macroData.id);
                    localStorage.setItem('downloaded_macros', JSON.stringify(downloadedMacros));
                } catch (e) {}
            }
            // Refresh profiles first to load into memory
            if (typeof window.loadProfiles === 'function') {
                await window.loadProfiles();
            } else if (typeof loadProfiles === 'function') {
                await loadProfiles();
            }
            
            // Update macro list UI if on settings screen
            if (typeof window.updateMacroList === 'function') {
                window.updateMacroList();
            } else if (typeof updateMacroList === 'function') {
                updateMacroList();
            }
            
            // Re-render community grid to show checkmarks
            displayCommunityMacros();
        } else {
            await showAlert("", result.message || "Failed to install item", "danger");
        }
    } catch (e) {
        console.error("Install error:", e);
        await showAlert("", "Failed to install item", "danger");
    }
}

// Show submit macro modal
async function showSubmitMacroModal() {
    const modal = document.getElementById('submit-macro-modal');
    const macroSelectGroup = document.getElementById('macro-select-group');
    const profileSelectGroup = document.getElementById('profile-select-group');
    const macroSelect = document.getElementById('submit-macro-select');
    const profileSelect = document.getElementById('submit-profile-select');

    // Populate macro dropdown from all profiles
    macroSelect.innerHTML = '<option value="">-- Choose a macro --</option>';
    const allUserMacrosMap = (typeof window.getAllUserMacros === 'function') ? window.getAllUserMacros() : (currentProfileData && currentProfileData.macros ? currentProfileData.macros : {});
    Object.keys(allUserMacrosMap).forEach(macroName => {
        const option = document.createElement('option');
        option.value = macroName;
        option.textContent = macroName;
        macroSelect.appendChild(option);
    });

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
        const category = document.getElementById('submit-category').value;

        // Validation
        if (!creator) {
            await showAlert("", "Please enter your name", "danger");
            return;
        }
        if (!description) {
            await showAlert("", "Please provide a description", "danger");
            return;
        }

        let submissionData;

        if (type === 'macro') {
            const selectedMacro = macroSelect.value;
            if (!selectedMacro) {
                await showAlert("", "Please select a macro", "danger");
                return;
            }

            const macroData = (typeof window.getUserMacroData === 'function') ? window.getUserMacroData(selectedMacro) : (currentProfileData && currentProfileData.macros ? currentProfileData.macros[selectedMacro] : null);
            submissionData = {
                name: selectedMacro,
                author: creator,
                description: description,
                category: category,
                type: 'macro',
                macro: macroData
            };
        } else {
            const selectedProfile = profileSelect.value;
            if (!selectedProfile) {
                await showAlert("", "Please select a profile", "danger");
                return;
            }

            const profileData = profiles[selectedProfile];
            submissionData = {
                name: selectedProfile,
                author: creator,
                description: description,
                category: category,
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
                const successMsg = submissionData.type === 'profile' ? "Profile submitted to Community Library!" : "Macro submitted to Community Library!";
                await showAlert("", successMsg, "success");
                // Refresh to show it
                currentFilter = 'all';
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                document.querySelector('.filter-btn[data-filter="all"]').classList.add('active');
                setTimeout(() => loadCommunityMacros(), 1000);
            } else {
                await showAlert("", result.message || "Failed to submit macro", "danger");
            }
        } catch (e) {
            console.error("Submission error:", e);
            await showAlert("", "Failed to submit macro", "danger");
        }
    };
}

// ====================
// FIRMWARE UPDATES
// ====================

// update check logic moved to update.js and app.js central handler

// ====================
// HELPER FUNCTIONS
// ====================

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

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
