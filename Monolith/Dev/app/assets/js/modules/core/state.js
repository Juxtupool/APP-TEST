
// Application State Module
// Centralizes all global state variables
// Loaded as a standard script, not a module

window.State = {
    currentProfile: "Default Profile",
    profiles: {},
    currentControl: { type: "key", id: 1 },
    isConnected: false,
    isRecording: false,
    recordedKeys: [],
    lastEventTime: 0,
    editingMacroName: null
};

// Global Constants
window.CONSTANTS = {
    PROFILE_NAME_MAX_LENGTH: 30
};

// Legacy Compatibility Shim
// Expose these to window so legacy scripts (community.js, update.js) can still access them
window.currentProfile = window.State.currentProfile;
window.profiles = window.State.profiles;
window.currentControl = window.State.currentControl;
window.isConnected = window.State.isConnected;
window.isRecording = window.State.isRecording;
window.recordedKeys = window.State.recordedKeys;
window.actLastEventTime = window.State.lastEventTime;
window.editingMacroName = window.State.editingMacroName;
window.PROFILE_NAME_MAX_LENGTH = window.CONSTANTS.PROFILE_NAME_MAX_LENGTH;

// Function to update global state from module (if needed by legacy code)
window.updateGlobalState = function (key, value) {
    window.State[key] = value;
    window[key] = value;
};

// Function to sync from global to module (if legacy code modifies window directly)
window.syncStateFromGlobal = function () {
    window.State.currentProfile = window.currentProfile;
    window.State.profiles = window.profiles;
    window.State.currentControl = window.currentControl;
    window.State.isConnected = window.isConnected;
    window.State.isRecording = window.isRecording;
    window.State.recordedKeys = window.recordedKeys;
    window.State.lastEventTime = window.actLastEventTime;
    window.State.editingMacroName = window.editingMacroName;
};

// --- Callbacks (Registered early to prevent race conditions) ---
window.onSerialMessage = function (message) { };

window.onSerialConnectionLost = function () { };
window.onAutoProfileSwitch = function (profile) { };
window.onFirmwareVersion = function (v) { };
window.onRecordedKey = function (t, k) { };
