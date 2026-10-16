/**
 * UI and responsive layout actions for DocuMind AI
 */
function toggleSidebar() {
    const sidebar = document.getElementById('sidebarMenu');
    const overlay = document.getElementById('sidebarOverlay');
    if (sidebar && overlay) {
        sidebar.classList.toggle('show');
        overlay.classList.toggle('show');
    }
}

// Close sidebar on window resize if moving to desktop view
window.addEventListener('resize', function() {
    if (window.innerWidth >= 992) {
        const sidebar = document.getElementById('sidebarMenu');
        const overlay = document.getElementById('sidebarOverlay');
        if (sidebar && sidebar.classList.contains('show')) {
            sidebar.classList.remove('show');
        }
        if (overlay && overlay.classList.contains('show')) {
            overlay.classList.remove('show');
        }
    }
});
