
// UI Dialogs Module
// Handles all modal interactions (Alert, Confirm, Prompt)
// Loaded as a standard script, not a module

// Helper for XSS Prevention
window.sanitizeHTML = (str) => {
    if (!str) return "";
    const temp = document.createElement('div');
    temp.textContent = str;
    return temp.innerHTML
        .replace(/\n/g, '<br>')
        .replace(/&lt;strong&gt;/g, '<strong>')
        .replace(/&lt;\/strong&gt;/g, '</strong>')
        .replace(/&lt;b&gt;/g, '<b>')
        .replace(/&lt;\/b&gt;/g, '</b>');
};

window.Dialog = {
    modal: document.getElementById('generic-modal'),
    title: document.getElementById('generic-modal-title'),
    message: document.getElementById('generic-modal-message'),
    input: document.getElementById('generic-modal-input'),
    btnOk: document.getElementById('generic-modal-ok'),
    btnCancel: document.getElementById('generic-modal-cancel'),
    btnClose: null,
    icon: document.querySelector('.generic-modal-icon'),
    hideTimeout: null,

    // Re-initialize DOM elements (in case module loads before DOM)
    init() {
        this.modal = document.getElementById('generic-modal');
        this.title = document.getElementById('generic-modal-title');
        this.message = document.getElementById('generic-modal-message');
        this.input = document.getElementById('generic-modal-input');
        this.btnOk = document.getElementById('generic-modal-ok');
        this.btnCancel = document.getElementById('generic-modal-cancel');
        this.icon = document.querySelector('.generic-modal-icon');
    },

    show(options) {
        // Ensure DOM is ready
        if (!this.modal) this.init();
        if (!this.modal) {
            console.error("Dialog Modal elements not found in DOM");
            return Promise.reject("DOM not ready");
        }

        return new Promise((resolve) => {
            // clear any pending hide
            if (this.hideTimeout) {
                clearTimeout(this.hideTimeout);
                this.hideTimeout = null;
            }

            const titleText = (options.title !== undefined) ? options.title : "Alert";
            this.title.innerText = titleText;
            this.title.style.display = titleText ? "block" : "none";

            // Hide header if empty
            if (this.title.parentElement && this.title.parentElement.classList.contains('modal-header')) {
                this.title.parentElement.style.display = titleText ? "flex" : "none";
            }

            // Use the Sanitizer!
            this.message.innerHTML = options.message ? window.sanitizeHTML(options.message) : "";

            this.input.value = options.defaultValue || "";
            this.input.style.display = options.hasInput ? "block" : "none";
            this.btnOk.innerText = options.confirmText || "OK";

            // Handle Cancel Button
            if (options.showCancel === false) {
                this.btnCancel.style.display = 'none';
            } else {
                this.btnCancel.style.display = '';
            }

            // Hide progress bar
            const progContainer = document.getElementById('generic-modal-progress-container');
            if (progContainer) progContainer.style.display = 'none';

            // Reset classes
            this.modal.classList.remove('modal-type-danger', 'modal-type-success');
            if (this.icon) {
                this.icon.style.display = "none";
                this.icon.className = "modal-icon generic-modal-icon";
            }

            // Apply Type
            if (options.type && this.icon) {
                this.modal.classList.add(`modal-type-${options.type}`);
                this.icon.style.display = "block";

                if (options.type === 'danger') {
                    this.icon.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';
                    this.btnCancel.className = 'btn-primary';
                    this.btnOk.className = 'btn-danger';
                } else if (options.type === 'success') {
                    this.icon.innerHTML = '<i class="fa-solid fa-check-circle"></i>';
                    this.btnCancel.className = 'btn-cancel';
                    this.btnOk.className = 'btn-primary';
                } else {
                    this.icon.innerHTML = '<i class="fa-solid fa-info-circle"></i>';
                    this.btnCancel.className = 'btn-cancel';
                    this.btnOk.className = 'btn-primary';
                }
            } else {
                this.btnCancel.className = 'btn-cancel';
                this.btnOk.className = 'btn-primary';
            }

            // Focus input
            if (options.hasInput) {
                setTimeout(() => this.input.focus(), 100);
            }

            this.modal.style.display = "flex";
            setTimeout(() => this.modal.classList.add('active'), 10);

            const close = (value) => {
                this.modal.classList.remove('active');
                this.hideTimeout = setTimeout(() => {
                    this.modal.style.display = "none";
                    this.cleanup();
                    resolve(value);
                }, 200);
            };

            this.onOk = () => {
                const val = options.hasInput ? this.input.value.trim() : true;
                close(val);
            };

            this.onCancel = () => close(null);

            this.btnOk.onclick = this.onOk;
            this.btnCancel.onclick = this.onCancel;

            if (options.hasInput) {
                this.input.onkeydown = (e) => {
                    if (e.key === "Enter") this.onOk();
                    if (e.key === "Escape") this.onCancel();
                };
            }
        });
    },

    cleanup() {
        if (this.btnOk) this.btnOk.onclick = null;
        if (this.btnCancel) this.btnCancel.onclick = null;
        if (this.input) this.input.onkeydown = null;
    }
};

window.showPrompt = async function (title, message, defaultValue = "", confirmText = "OK") {
    return await window.Dialog.show({ title, message, hasInput: true, defaultValue, confirmText });
};

window.showConfirm = async function (title, message, type = "info", confirmText = "OK") {
    return await window.Dialog.show({ title, message, hasInput: false, type, confirmText });
};

window.showAlert = async function (title, message, type = "info") {
    return await window.Dialog.show({ title, message, hasInput: false, type, showCancel: false });
};
