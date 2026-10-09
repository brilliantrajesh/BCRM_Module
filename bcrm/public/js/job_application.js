frappe.ready(function () {
    if (
        document.body &&
        (document.body.dataset.path || "").startsWith("job_application")
    ) {
        const css = document.createElement("link");
        css.rel = "stylesheet";
        css.href = "/assets/bcrm/css/job_application.css";
        document.head.appendChild(css);
    }
});
