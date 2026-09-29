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

/* BCRM Common App Version */
(function () {
    "use strict";

    var BTPL_APP_USER = "tracker@brillianttechnologies.com";
    var VERSION_LABEL_ID = "bcrm-common-app-version";
    var VERSION_VALUE_ID = "bcrm-common-app-version-value";

    function get_user_area() {
        return document.querySelector(".avatar-name-email");
    }

    function render_app_version(version) {
        var clean_version = String(version || "").trim();
        var user_area = get_user_area();

        if (!clean_version || !user_area) {
            return;
        }

        var version_element =
            document.getElementById(VERSION_LABEL_ID);

        if (!version_element) {
            version_element = document.createElement("span");
            version_element.id = VERSION_LABEL_ID;
            version_element.className =
                "text-secondary text-truncate";

            version_element.style.cssText =
                "display:block;margin-top:2px;font-size:10px;";

            version_element.innerHTML =
                'BTPL Ver <span id="' +
                VERSION_VALUE_ID +
                '"></span>';

            user_area.appendChild(version_element);
        }

        var version_value =
            document.getElementById(VERSION_VALUE_ID);

        if (version_value) {
            version_value.textContent = clean_version;
        }
    }

    function load_app_version() {
        frappe.db.get_value(
            "User",
            BTPL_APP_USER,
            "custom_app_version"
        ).then(function (response) {
            var version =
                response && response.message
                    ? response.message.custom_app_version
                    : null;

            render_app_version(version);
        });
    }

    // Initial version load
    load_app_version();

    // Silent update for all connected users
    frappe.realtime.on(
        "bcrm_app_version_updated",
        function (data) {
            if (data && data.version) {
                render_app_version(data.version);
            }
        }
    );
})();
