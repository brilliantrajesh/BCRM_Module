(function () {
    "use strict";

    var HIDE_LABELS = [
        "Edit Profile",
        "Toggle Theme",
        "About",
        "Frappe Support",
        "Reset to Default",
        "Reset Desktop Layout",
        "Manage Billing"
    ];

    function hide_items_in(menu) {
        menu.querySelectorAll(".dropdown-menu-item").forEach(function (item) {
            var titleEl = item.querySelector(".menu-item-title");
            if (!titleEl) return;
            var label = titleEl.textContent.trim();
            if (HIDE_LABELS.some(function (l) { return label.indexOf(l) === 0; })) {
                item.classList.add("bcrm-hidden-menu-item");
            }
        });
    }

    function process_all_menus() {
        document.querySelectorAll(".frappe-menu.context-menu").forEach(hide_items_in);
    }

    setInterval(process_all_menus, 300);
    process_all_menus();
})();

/* BCRM Local Agent Bridge */
window.BCRM_Agent = window.BCRM_Agent || {};

window.BCRM_Agent.open_ultraviewer = function () {
    return fetch("http://127.0.0.1:5000/open", {
        method: "GET",
        signal: AbortSignal.timeout(30000)
    }).then(function (response) {
        return response.json().then(function (data) {
            if (!response.ok || data.status !== "success") {
                throw new Error(
                    data.message || "BCRM Agent could not open UltraViewer."
                );
            }
            return data;
        });
    });
};

window.BCRM_Agent.is_running = function () {
    return fetch("http://127.0.0.1:5000/", {
        method: "GET",
        signal: AbortSignal.timeout(3000)
    }).then(function (response) {
        return response.ok;
    }).catch(function () {
        return false;
    });
};
