document.addEventListener('DOMContentLoaded', function() {
    const wrapper = document.getElementById('wrapper');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const mobileMenuToggle = document.getElementById('mobile-menu-toggle');

    function setupEventListeners() {
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => {
                wrapper.classList.toggle('toggled');
            });
        }
        if (mobileMenuToggle) {
            mobileMenuToggle.addEventListener('click', () => {
                wrapper.classList.toggle('toggled');
            });
        }
    }

    setupEventListeners();

    function makeTablesResponsive() {
        const tables = document.querySelectorAll('.table');
        tables.forEach(table => {
            const headers = table.querySelectorAll('thead th');
            const headerTexts = Array.from(headers).map(header => header.textContent.trim());
            const rows = table.querySelectorAll('tbody tr');
            rows.forEach(row => {
                const cells = row.querySelectorAll('td');
                cells.forEach((cell, index) => {
                    if (index < headerTexts.length) {
                        cell.setAttribute('data-label', headerTexts[index]);
                    }
                });
            });
        });
    }

    makeTablesResponsive();
});