/* BCRM: Avatar menu lo Logout + Toggle Width matrame undali, migatha anni hide */
(function () {
    "use strict";

    var KEEP = [/^log\s?out$/i, /toggle.*width/i];

    function keep_only_allowed() {
        document.querySelectorAll(".es-menu").forEach(function (menu) {
            menu.querySelectorAll(".es-menu__item").forEach(function (item) {
                var label = item.querySelector(".es-menu__label");
                var text = ((label || item).textContent || "").trim();
                var keep = KEEP.some(function (re) { return re.test(text); });

                if (keep) {
                    item.style.removeProperty("display");
                } else {
                    item.style.setProperty("display", "none", "important");
                }
            });

            // visible item lekapothe aa group ni kuda hide
            menu.querySelectorAll(".es-menu__group").forEach(function (group) {
                var has_visible = Array.prototype.some.call(
                    group.querySelectorAll(".es-menu__item"),
                    function (i) { return i.style.display !== "none"; }
                );
                group.style.display = has_visible ? "" : "none";
            });
        });
    }

    setInterval(keep_only_allowed, 300);
    keep_only_allowed();

    // Debug: avatar menu open chesi console lo BCRM_debug_menu() run cheyyi
    window.BCRM_debug_menu = function () {
        var rows = Array.prototype.map.call(
            document.querySelectorAll(".es-menu .es-menu__item"),
            function (i) {
                var l = i.querySelector(".es-menu__label");
                return {
                    label: (l ? l.textContent : i.textContent).trim(),
                    hidden: i.style.display === "none" ? "yes" : "no"
                };
            }
        );
        console.table(rows);
        return rows;
    };
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

    var VERSION_LABEL_ID = "bcrm-common-app-version";
    var VERSION_VALUE_ID = "bcrm-common-app-version-value";
    var current_version = "";

    function get_user_area() {
        return document.querySelector(".avatar-name-email");
    }

    function render_app_version(version) {
        var clean_version = String(version || "").trim();
        var user_area = get_user_area();

        if (!clean_version || !user_area) {
            return;
        }

        var version_element = document.getElementById(VERSION_LABEL_ID);

        if (!version_element) {
            version_element = document.createElement("span");
            version_element.id = VERSION_LABEL_ID;
            version_element.className = "text-secondary text-truncate";
            version_element.style.cssText =
                "display:block;margin-top:2px;font-size:10px;";
            version_element.innerHTML =
                'BTPL Ver <span id="' + VERSION_VALUE_ID + '"></span>';
            user_area.appendChild(version_element);
        }

        var version_value = document.getElementById(VERSION_VALUE_ID);
        if (version_value) {
            version_value.textContent = clean_version;
        }
    }

    function ensure_version_label() {
        if (current_version) {
            render_app_version(current_version);
        }
    }

    // Initial version load + keep label alive (v16 re-renders the sidebar)
    frappe.call({
        method: "bcrm.api.app_version.get_app_version"
    }).then(function (response) {
        current_version = response.message || "";
        ensure_version_label();
    });
    setInterval(ensure_version_label, 1000);

    // Silent update for all connected users
    frappe.realtime.on("bcrm_app_version_updated", function (data) {
        if (data && data.version) {
            current_version = data.version;
            render_app_version(current_version);
        }
    });
})();
