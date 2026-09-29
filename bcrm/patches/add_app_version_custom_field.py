import frappe


def execute():
    fieldname = "custom_app_version"

    if frappe.db.exists(
        "Custom Field",
        {
            "dt": "User",
            "fieldname": fieldname
        }
    ):
        return

    doc = frappe.get_doc({
        "doctype": "Custom Field",
        "dt": "User",
        "label": "App Version",
        "fieldname": fieldname,
        "fieldtype": "Data",
        "insert_after": "email",
        "depends_on": 'eval:doc.email == "tracker@brillianttechnologies.com"',
        "description": "Enter Mobile BTPL APP version"
    })

    doc.insert(ignore_permissions=True)
