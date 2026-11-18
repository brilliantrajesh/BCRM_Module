/* BCRM: Avatar menu lo "Log out" matrame undali, migatha anni hide */
(function () {
    "use strict";

    var KEEP_LABELS = ["Log out", "Logout", "Log Out"];
    var ROOT_SEL = '[role="menu"], .dropdown-menu, .frappe-menu, .context-menu, [class*="popover"]';

    function is_keep(text) {
        text = (text || "").trim();
        return KEEP_LABELS.some(function (l) { return text.indexOf(l) === 0; });
    }

    function hide(el) {
        // version label / user header protect cheyyadam
        if (el.classList.contains("avatar-name-email") ||
            el.querySelector("#bcrm-common-app-version")) {
            return;
        }
        el.classList.add("bcrm-hidden-menu-item");
        el.style.setProperty("display", "none", "important");
    }

    function keep_only_logout() {
        document.querySelectorAll("body *").forEach(function (el) {
            if (el.children.length !== 0) return;
            if (!is_keep(el.textContent)) return;

            var root = el.closest(ROOT_SEL);
            if (!root) return;

            // logout row ni find cheyyadam
            var row = el;
            while (row.parentElement &&
                   row.parentElement !== root &&
                   row.parentElement.children.length < 3) {
                row = row.parentElement;
            }

            // row nundi menu root varaku, prathi level lo siblings hide
            var node = row;
            while (node && node !== root && node.parentElement) {
                Array.prototype.forEach.call(node.parentElement.children, function (sib) {
                    if (sib !== node) hide(sib);
                });
                node = node.parentElement;
            }
        });
    }

    setInterval(keep_only_logout, 300);
    keep_only_logout();
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
