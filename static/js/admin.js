// Dark mode toggle functionality
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    localStorage.setItem('darkMode', isDark);
    updateDarkModeIcon(isDark);
}

function updateDarkModeIcon(isDark) {
    const icon = document.getElementById('dark-mode-icon');
    if (icon) {
        icon.className = isDark ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
    }
}

// Apply saved dark mode preference on page load
document.addEventListener('DOMContentLoaded', function() {
    const savedDarkMode = localStorage.getItem('darkMode');
    if (savedDarkMode === 'true') {
        document.body.classList.add('dark-mode');
        updateDarkModeIcon(true);
    }
});
