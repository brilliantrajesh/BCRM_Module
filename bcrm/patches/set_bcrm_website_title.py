import frappe


def execute():
    website_settings = frappe.get_single("Website Settings")

    if website_settings.app_name != "BCRM":
        website_settings.app_name = "BCRM"
        website_settings.save(ignore_permissions=True)
        frappe.db.commit()
