import frappe


def user_version_updated(doc, method=None):
    if doc.email != "tracker@brillianttechnologies.com":
        return

    frappe.publish_realtime(
        "bcrm_app_version_updated",
        {
            "version": doc.custom_app_version or ""
        },
        room="all",
        after_commit=True
    )
