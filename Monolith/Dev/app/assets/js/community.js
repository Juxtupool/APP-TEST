// ====================
// COMMUNITY MACRO HUB
// ====================

let currentFilter = 'all';
let currentSort = 'recent';
let communityMacros = [];
let fullCommunityMacrosCache = []; // Cache for client-side search/reset

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
            try {
                const macroData = JSON.parse(decodeURIComponent(btn.dataset.macro));
                await installCommunityMacro(macroData);
            } catch (err) {
                console.error("Error parsing macro data:", err);
                showAlert("", "Corrupted macro data", "danger");
            }
        });
    });

    // Star button listener (visual only for now)
    grid.querySelectorAll('.macro-card-btn-icon').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const icon = btn.querySelector('i');
            if (icon.classList.contains('fa-regular')) {
                icon.classList.remove('fa-regular');
                icon.classList.add('fa-solid');
                icon.style.color = '#F59E0B';
            } else {
                icon.classList.add('fa-regular');
                icon.classList.remove('fa-solid');
                icon.style.color = '';
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
        // Also check tags
        const tags = (m.tags || []).join(' ').toLowerCase();

        return name.includes(lowerQ) || desc.includes(lowerQ) || author.includes(lowerQ) || tags.includes(lowerQ);
    });

    displayCommunityMacros();
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
                    <div class="macro-stat" title="Downloads">
                        <i class="fa-solid fa-download"></i>
                        <span>${macro.downloads || 0}</span>
                    </div>
                    <div class="macro-stat" style="margin-left: 12px;" title="Stars">
                        <i class="fa-solid fa-star"></i>
                        <span>${likes}</span>
                    </div>
                    <div class="macro-stat" style="margin-left: 12px;" title="Uploaded">
                        <i class="fa-solid fa-calendar" style="font-size: 0.7rem;"></i>
                        <span style="font-size: 0.75rem;">${dateStr}</span>
                    </div>
                </div>
                <div class="macro-card-actions" style="display: flex; gap: 8px;">
                    <button class="macro-card-btn-icon" title="Star this macro" style="padding: 6px 10px; background: rgba(255,255,255,0.1); border-radius: 6px; border:none; color: var(--text-secondary); cursor: pointer;">
                        <i class="fa-regular fa-star"></i>
                    </button>
                    <button class="macro-card-btn ${isProfile ? 'btn-profile' : ''}" data-macro="${macroJson}" ${isProfile ? 'style="background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%);"' : ''}>
                        <i class="fa-solid ${buttonIcon}"></i>
                        ${buttonText}
                    </button>
                </div>
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
                await showAlert("", `Installed profile "${result.name}" and switched to it!`, "success");
                // Refresh profiles
                if (typeof loadProfiles === 'function') {
                    await loadProfiles();
                } else {
                    location.reload(); // Fallback if loadProfiles isn't available in scope
                }
            } else {
                await showAlert("", `Installed "${result.name}" to your library!`, "success");
                // Refresh macro list
                if (typeof updateMacroList === 'function') {
                    updateMacroList();
                }
            }
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
                await showAlert("", "Please select a profile", "danger");
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
