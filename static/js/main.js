// Auto-logout due to inactivity
(function() {
    const idleTimeout = parseInt(document.body.dataset.sessionTimeout, 10) * 1000;
    if (isNaN(idleTimeout) || idleTimeout <= 0) {
        return;
    }

    let timeout;

    function resetTimer() {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            // Redirect to login page if idle
            const nextUrl = encodeURIComponent(window.location.pathname + window.location.search);
            window.location.href = `/login?next=${nextUrl}&reason=idle`;
        }, idleTimeout);
    }

    // Reset timer on user activity
    window.addEventListener("mousemove", resetTimer, false);
    window.addEventListener("keypress", resetTimer, false);
    window.addEventListener("scroll", resetTimer, false);
    window.addEventListener("click", resetTimer, false);

    // Initial timer start
    resetTimer();

    // Keep-alive function to prevent server from sleeping
    (function keepAlive() {
        const PING_URL = window.location.origin;  // root of your app
        const INTERVAL = 4 * 60 * 1000; // every 4 minutes

        setInterval(() => {
            fetch(PING_URL, { cache: "no-store" })
                .then(response => console.log("Keep-alive ping:", response.status))
                .catch(err => console.warn("Ping error:", err));
        }, INTERVAL);
    })();
})();
