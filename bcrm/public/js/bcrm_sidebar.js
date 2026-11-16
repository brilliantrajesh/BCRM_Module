(function () {
    const BCRM_SIDEBAR = "BCRM"; // Workspace Sidebar name (exact)
    const BCRM_WORKSPACES = ["Main Dashboard", "BCRM Home", "BCRM Portal"]; // ee workspaces open ayithe BCRM sidebar undali

    function lock_bcrm_sidebar() {
        const route = frappe.get_route();
        if (!route || route[0] !== "Workspaces") return;

        const ws = decodeURIComponent(route[route.length - 1] || "");
        if (!BCRM_WORKSPACES.includes(ws)) return;

        const sb = frappe.app && frappe.app.sidebar;
        if (!sb) return;

        // Frappe version batti function name maruthundi, anni try chesthundi
        if (typeof sb.set_workspace_sidebar === "function") {
            sb.set_workspace_sidebar(BCRM_SIDEBAR);
        } else if (typeof sb.setup === "function") {
            sb.setup(BCRM_SIDEBAR);
        } else if (typeof sb.render === "function") {
            sb.sidebar_title = BCRM_SIDEBAR;
            sb.render();
        }
    }

    $(document).on("page-change", () => setTimeout(lock_bcrm_sidebar, 300));
    $(document).ready(() => setTimeout(lock_bcrm_sidebar, 800));
})();
