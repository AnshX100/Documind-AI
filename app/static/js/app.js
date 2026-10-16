/**
 * DocuMind AI Global Interactions
 * Handles:
 * - Drag and drop file uploader triggers (dashed zone, browse button, icon, and title)
 * - Size and extension front-end verification
 * - Dynamic metadata rendering and final submit button state updates
 */

document.addEventListener('DOMContentLoaded', () => {
    // --- Mobile Sidebar Off-Canvas Drawer Handling ---
    const mobileNavToggle = document.getElementById('mobileNavToggle');
    const sidebar = document.querySelector('.sidebar');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');

    const openSidebar = () => {
        if (sidebar) sidebar.classList.add('open');
        if (sidebarBackdrop) sidebarBackdrop.classList.add('show');
        document.body.style.overflow = 'hidden';
    };

    const closeSidebar = () => {
        if (sidebar) sidebar.classList.remove('open');
        if (sidebarBackdrop) sidebarBackdrop.classList.remove('show');
        document.body.style.overflow = '';
    };

    if (mobileNavToggle) {
        mobileNavToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            if (sidebar && sidebar.classList.contains('open')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });
    }

    if (sidebarBackdrop) {
        sidebarBackdrop.addEventListener('click', () => {
            closeSidebar();
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebar && sidebar.classList.contains('open')) {
            closeSidebar();
        }
    });

    // Close sidebar on clicking navigation buttons in mobile mode
    const navLinks = document.querySelectorAll('.sidebar .nav a');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth <= 900) {
                closeSidebar();
            }
        });
    });

    // --- Global Document Delete Confirmation Modal Handler ---
    const deleteModal = document.getElementById('deleteModal');
    if (deleteModal) {
        const setupDeleteForm = (docId, docName) => {
            const nameEl = document.getElementById('deleteModalDocName');
            if (nameEl && docName) {
                nameEl.textContent = docName;
            }
            const formEl = document.getElementById('deleteForm');
            if (formEl && docId) {
                formEl.setAttribute('action', `/documents/${docId}/delete`);
            }
        };

        // Bootstrap show event
        deleteModal.addEventListener('show.bs.modal', (event) => {
            const button = event.relatedTarget;
            if (!button) return;
            const docId = button.getAttribute('data-doc-id');
            const docName = button.getAttribute('data-doc-name');
            setupDeleteForm(docId, docName);
        });

        // Event delegation click fallback for all delete triggers
        document.addEventListener('click', (e) => {
            const trigger = e.target.closest('[data-bs-target="#deleteModal"], [data-target="#deleteModal"]');
            if (trigger) {
                const docId = trigger.getAttribute('data-doc-id');
                const docName = trigger.getAttribute('data-doc-name');
                setupDeleteForm(docId, docName);
            }
        });

        // Ensure complete backdrop cleanup and scroll restoration on modal hide
        deleteModal.addEventListener('hidden.bs.modal', () => {
            document.body.classList.remove('modal-open');
            document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        });
    }

    // --- Drag & Drop File Upload Handling (Upload Page Only) ---
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('documentInput');
    const uploadPrompt = document.getElementById('uploadPrompt');
    const fileMetadata = document.getElementById('fileMetadata');
    const fileNameEl = document.getElementById('fileName');
    const fileSizeEl = document.getElementById('fileSize');
    const fileAvatar = document.getElementById('fileAvatar');
    const btnRemove = document.getElementById('btnRemoveFile');
    const btnSubmit = document.getElementById('btnSubmit');

    const btnBrowse = document.getElementById('btnBrowse');
    const uploadIcon = document.getElementById('uploadIcon');
    const uploadTitle = document.getElementById('uploadTitle');

    if (!uploadZone || !fileInput) return;

    // Helper: Trigger file picker
    const triggerFilePicker = (e) => {
        e.preventDefault();
        e.stopPropagation();
        fileInput.click();
    };

    // Bind triggers
    if (btnBrowse) btnBrowse.addEventListener('click', triggerFilePicker);
    if (uploadIcon) uploadIcon.addEventListener('click', triggerFilePicker);
    if (uploadTitle) uploadTitle.addEventListener('click', triggerFilePicker);

    // Clicking anywhere in the prompt zone triggers it too
    uploadZone.addEventListener('click', (e) => {
        if (fileInput.files.length === 0) {
            if (e.target !== btnRemove && !btnRemove.contains(e.target)) {
                fileInput.click();
            }
        }
    });

    // Drag-and-Drop events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
        }, false);
    });

    // Hover styling classes
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadZone.addEventListener(eventName, () => {
            uploadZone.classList.add('dragover');
            if (uploadIcon) uploadIcon.style.transform = 'translateY(-4px)';
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadZone.addEventListener(eventName, () => {
            uploadZone.classList.remove('dragover');
            if (uploadIcon) uploadIcon.style.transform = 'translateY(0)';
        }, false);
    });

    // Handle dropped files
    uploadZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files && files.length > 0) {
            fileInput.files = files;
            updateFileDetails(files[0]);
        }
    });

    // Handle native browser file browsing input change
    fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files.length > 0) {
            updateFileDetails(fileInput.files[0]);
        }
    });

    // Remove selected file trigger
    if (btnRemove) {
        btnRemove.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileInput.value = '';
            
            // Hide metadata and show prompt
            fileMetadata.style.display = 'none';
            uploadPrompt.style.display = 'block';
            
            // Disable submit button
            if (btnSubmit) {
                btnSubmit.disabled = true;
            }
        });
    }

    // Process details and update metadata labels
    function updateFileDetails(file) {
        fileNameEl.textContent = file.name;
        
        // Format file size
        const sizeMB = file.size / (1024 * 1024);
        fileSizeEl.textContent = `${sizeMB.toFixed(2)} MB`;

        // Extract extension for badge avatar
        const ext = file.name.split('.').pop().toUpperCase();
        if (fileAvatar) {
            fileAvatar.textContent = ext.substring(0, 2);
            // Dynamic avatar colors matching extension
            if (ext === 'PDF') {
                fileAvatar.style.background = '#d94d42'; // red
            } else if (['DOCX', 'DOC'].includes(ext)) {
                fileAvatar.style.background = '#386ff5'; // blue
            } else if (['PNG', 'JPG', 'JPEG', 'WEBP'].includes(ext)) {
                fileAvatar.style.background = '#177e61'; // mint/green
            } else {
                fileAvatar.style.background = '#728097'; // default grey
            }
        }

        // Toggle prompt/metadata visibility
        uploadPrompt.style.display = 'none';
        fileMetadata.style.display = 'block';

        // Enable submit button
        if (btnSubmit) {
            btnSubmit.disabled = false;
        }
    }
});
