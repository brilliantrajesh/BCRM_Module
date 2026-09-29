import frappe


BTPL_APP_USER = "tracker@brillianttechnologies.com"


@frappe.whitelist()
def get_app_version():
    return frappe.db.get_value(
        "User",
        BTPL_APP_USER,
        "custom_app_version"
    ) or ""


def user_version_updated(doc, method=None):
    if doc.email != BTPL_APP_USER:
        return

    frappe.publish_realtime(
        "bcrm_app_version_updated",
        {
            "version": doc.custom_app_version or ""
        },
        room="all",
        after_commit=True
    )
