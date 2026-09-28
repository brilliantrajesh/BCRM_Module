(() => {
    "use strict";

    const VERSION_LABEL_ID = "btpl-app-version";
    const VERSION_VALUE_ID = "btpl-app-version-value";

    function get_user_area() {
        return document.querySelector(".avatar-name-email");
    }

    function render_app_version(version) {
        const clean_version = String(version || "").trim();

        if (!clean_version) {
            return;
        }

        const user_area = get_user_area();

        if (!user_area) {
            return;
        }

        let version_element = document.getElementById(VERSION_LABEL_ID);

        // Create App Version element only when Flutter sends the version
        if (!version_element) {
            version_element = document.createElement("span");
            version_element.id = VERSION_LABEL_ID;
            version_element.className = "text-secondary text-truncate";
            version_element.style.cssText =
                "display:block;margin-top:2px;font-size:10px;";

            const version_value = document.createElement("span");
            version_value.id = VERSION_VALUE_ID;

            version_element.appendChild(
                document.createTextNode("App Version ")
            );
            version_element.appendChild(version_value);

            user_area.appendChild(version_element);
        }

        const version_value = document.getElementById(VERSION_VALUE_ID);

        if (version_value) {
            version_value.textContent = clean_version;
        }

        version_element.style.display = "block";
    }

    function hide_app_version() {
        const version_element = document.getElementById(VERSION_LABEL_ID);

        if (version_element) {
            version_element.style.display = "none";
        }
    }

    function init() {
        // Normal browser = hidden
        hide_app_version();

        // Flutter WebView may already have injected the version
        if (window.BTPL_APP_VERSION) {
            render_app_version(window.BTPL_APP_VERSION);
        }

        // Flutter sends this after injecting the installed app version
        window.addEventListener(
            "btpl-app-version-ready",
            (event) => {
                const version = event?.detail?.version;

                if (version) {
                    render_app_version(version);
                }
            }
        );
    }

    // Frappe desk DOM can load asynchronously
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

    // Handle Frappe sidebar/user area being recreated
    const observer = new MutationObserver(() => {
        if (window.BTPL_APP_VERSION) {
            render_app_version(window.BTPL_APP_VERSION);
        }
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true,
    });
})();
