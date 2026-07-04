(function () {
    "use strict";

    var HIDE_LABELS = ["Edit Profile", "Toggle Theme", "About", "Frappe Support", "Reset to Default"];

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
