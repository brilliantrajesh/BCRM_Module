(function () {
    function applyGuestJobsNavbar() {
        const body = document.body;
        if (!body) return;

        const path = (body.dataset.path || "").replace(/^\/+|\/+$/g, "");
        const isGuestJobsPage =
            path === "jobs" ||
            path.startsWith("jobs/") ||
            path === "job_application" ||
            path.startsWith("job_application/");

        if (!isGuestJobsPage) return;

        const loginLink = document.querySelector(
            ".navbar .btn-login-area, .navbar a[href='/login']"
        );

        if (loginLink) {
            const item = loginLink.closest("li.nav-item");
            if (item) item.style.display = "none";
            else loginLink.style.display = "none";
        }

        if (path === "job_application" || path.startsWith("job_application/")) {
            const brandLink = document.querySelector(".navbar a.navbar-brand");
            if (brandLink) brandLink.setAttribute("href", "/jobs");
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", applyGuestJobsNavbar);
    } else {
        applyGuestJobsNavbar();
    }
})();
