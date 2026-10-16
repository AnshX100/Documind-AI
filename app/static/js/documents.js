/**
 * FinPilot AI Documents Management Scripts
 * Handles:
 * - Custom three-dot action dropdown overlays (prevents table expansion & layout shifts)
 * - Viewport boundary positioning (opens upward if near viewport bottom)
 * - Bootstrap delete confirmation modal parameter passing
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Action Dropdowns Toggle Overlay
    document.addEventListener('click', (e) => {
        const toggle = e.target.closest('.btn-action-toggle');
        if (toggle) {
            e.preventDefault();
            e.stopPropagation();
            
            const parent = toggle.closest('.action-dropdown');
            if (!parent) return;
            const overlay = parent.querySelector('.dropdown-overlay');
            if (!overlay) return;
            
            // Close other active dropdowns
            document.querySelectorAll('.dropdown-overlay').forEach(ov => {
                if (ov !== overlay) {
                    ov.classList.remove('show');
                }
            });
            
            // Toggle current dropdown
            const isShowing = overlay.classList.toggle('show');

            if (isShowing) {
                // Viewport boundary check to avoid clipping near bottom edge
                const rect = toggle.getBoundingClientRect();
                const spaceBelow = window.innerHeight - rect.bottom;
                if (spaceBelow < 160) {
                    overlay.style.top = 'auto';
                    overlay.style.bottom = '100%';
                    overlay.style.marginBottom = '6px';
                    overlay.style.marginTop = '0';
                } else {
                    overlay.style.top = '100%';
                    overlay.style.bottom = 'auto';
                    overlay.style.marginTop = '4px';
                    overlay.style.marginBottom = '0';
                }
            }
        } else {
            // Clicked outside, close all active dropdowns
            document.querySelectorAll('.dropdown-overlay').forEach(ov => {
                ov.classList.remove('show');
            });
        }
    });

    // Note: Delete confirmation modal is handled globally in app.js
});
