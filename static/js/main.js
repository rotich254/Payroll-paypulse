document.addEventListener('DOMContentLoaded', function() {
    const menuToggle = document.getElementById('menu-toggle');
    const wrapper = document.getElementById('wrapper');

    if (menuToggle && wrapper) {
        // Check local storage for sidebar state and apply it
        if (localStorage.getItem('sidebarToggled') === 'true') {
            wrapper.classList.add('toggled');
        }

        menuToggle.addEventListener('click', function() {
            wrapper.classList.toggle('toggled');
            // Save sidebar state to local storage
            if (wrapper.classList.contains('toggled')) {
                localStorage.setItem('sidebarToggled', 'true');
            } else {
                localStorage.setItem('sidebarToggled', 'false');
            }
        });
    }
}); 