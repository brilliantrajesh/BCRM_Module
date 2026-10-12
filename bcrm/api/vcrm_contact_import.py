"""VCRM Contact Import API for the BCRM custom app.

VCRM API operations are read-only. The only create/update operations in this
module target BCRM Contact and Customer records. Do not expose credentials to JS.
"""

import requests
import frappe




# ============================================================
# VCRM LOGIN
# ============================================================

def vcrm_login():
    """Authenticate to the configured VCRM webservice endpoint."""
    settings = frappe.get_doc("VCRM Integration Settings")
    base_url = (settings.vtiger_url or "").strip().rstrip("/")
    username = (settings.username or "").strip()
    access_key = settings.get_password("access_key") or ""

    if not base_url:
        frappe.throw("VCRM URL is not configured in VCRM Integration Settings.")
    if not username:
        frappe.throw("VCRM username is empty in VCRM Integration Settings.")
    if not access_key:
        frappe.throw("VCRM Webservice Access Key is empty in VCRM Integration Settings.")

    # requests executes in the custom-app Python runtime, not safe_exec.
    last_error = None
    for attempt in range(2):
        try:
            challenge_response = requests.get(
                base_url,
                params={
                    "operation": "getchallenge",
                    "username": username,
                    "_bt_cache_buster": frappe.utils.now_datetime().strftime("%Y%m%d%H%M%S%f") + str(attempt),
                },
                timeout=(10, 45),
            )
            challenge_response.raise_for_status()
            challenge = challenge_response.json()
        except (requests.RequestException, ValueError) as exc:
            frappe.log_error(title="VCRM getchallenge failed", message=str(exc))
            frappe.throw("VCRM getchallenge request failed: " + str(exc)[:400])

        if not isinstance(challenge, dict) or not challenge.get("success"):
            safe_error = challenge.get("error") if isinstance(challenge, dict) else str(challenge)
            frappe.throw("VCRM getchallenge was rejected: " + str(safe_error)[:500])

        token = str((challenge.get("result") or {}).get("token") or "")
        if not token:
            frappe.throw("VCRM getchallenge succeeded but returned no token.")

        hash_rows = frappe.db.sql("SELECT MD5(%s)", (token + access_key,))
        access_hash = hash_rows[0][0] if hash_rows else ""
        if not access_hash:
            frappe.throw("Could not generate VCRM challenge hash.")

        try:
            login_response = requests.post(
                base_url,
                data={"operation": "login", "username": username, "accessKey": access_hash},
                timeout=(10, 45),
            )
            login_response.raise_for_status()
            login = login_response.json()
        except (requests.RequestException, ValueError) as exc:
            frappe.log_error(title="VCRM login failed", message=str(exc))
            frappe.throw("VCRM POST login request failed: " + str(exc)[:400])

        if isinstance(login, dict) and login.get("success"):
            session_name = (login.get("result") or {}).get("sessionName")
            if not session_name:
                frappe.throw("VCRM login succeeded but no sessionName was returned.")
            return base_url, session_name

        last_error = login.get("error") if isinstance(login, dict) else str(login)
        error_code = last_error.get("code") if isinstance(last_error, dict) else ""
        if error_code != "INVALID_USER_CREDENTIALS" or attempt == 1:
            break

    frappe.throw(
        "VCRM POST login was rejected after requesting a fresh challenge. "
        "Check the VCRM username and Webservice Access Key. Response: " + str(last_error)[:700]
    )

# ============================================================
# VCRM REQUEST
# ============================================================

def vcrm_request(base_url, session_name, operation, data=None):
    params = {"operation": operation, "sessionName": session_name}
    if data:
        for key, value in data.items():
            if value is not None:
                params[key] = value
    try:
        response = requests.get(base_url, params=params, timeout=(10, 45))
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return {"success": False, "error": "VCRM returned a non-object JSON response."}
        return payload
    except (requests.RequestException, ValueError) as exc:
        frappe.log_error(title="VCRM API request failed", message=str(exc))
        return {"success": False, "error": str(exc)[:500]}

# ============================================================
# GET VCRM CONTACT
# ============================================================

def get_vcrm_contact(
    base_url,
    session_name,
    contact_id
):

    if not contact_id:

        return {
            "success": False,
            "error": "Contact ID is required."
        }

    result = vcrm_request(
        base_url,
        session_name,
        "retrieve",
        {
            "id": contact_id,
            "elementType": "Contacts"
        }
    )

    if not result.get("success"):
        return result

    contact = (
        result.get("result") or {}
    )

    if not isinstance(contact, dict):

        if isinstance(contact, list) and contact:
            contact = contact[0]

        else:
            contact = {}

    return {
        "success": True,
        "data": contact
    }


# ============================================================
# GET VCRM ORGANIZATION
# ============================================================

def get_vcrm_organization(
    base_url,
    session_name,
    account_id
):

    if not account_id:
        return ""

    safe_account_id = (
        str(account_id)
        .replace("'", "''")
    )

    query = (
        "select id,accountname "
        "from Accounts "
        "where id = '"
        + safe_account_id
        + "';"
    )

    result = vcrm_request(
        base_url,
        session_name,
        "query",
        {
            "query": query
        }
    )

    if not result.get("success"):
        return ""

    rows = (
        result.get("result") or []
    )

    if not rows:
        return ""

    row = rows[0]

    if not isinstance(row, dict):
        return ""

    return (
        row.get("accountname") or ""
    ).strip()


# ============================================================
# FIND BCRM CUSTOMER
# ============================================================

def find_bcrm_customer(
    organization_name
):

    organization_name = (
        organization_name or ""
    ).strip()

    if not organization_name:
        return None

    customer = frappe.db.get_value(
        "Customer",
        {
            "customer_name":
                organization_name
        },
        [
            "name",
            "customer_name"
        ],
        as_dict=True
    )

    if customer:
        return customer

    rows = frappe.db.sql(
        """
        SELECT name, customer_name
        FROM `tabCustomer`
        WHERE LOWER(TRIM(customer_name))
              = LOWER(TRIM(%s))
        LIMIT 1
        """,
        (
            organization_name,
        ),
        as_dict=True
    )

    if rows:
        return rows[0]

    return None


# ============================================================
# NORMALIZE MOBILE
# ============================================================

def normalize_mobile(value):

    value = (
        value or ""
    ).strip()

    if not value:
        return ""

    digits = ""

    for char in value:

        if char.isdigit():
            digits = digits + char

    # Indian mobile normalization
    if len(digits) >= 10:
        return digits[-10:]

    return digits


# ============================================================
# NORMALIZE EMAIL
# ============================================================

def normalize_email(value):

    return (
        value or ""
    ).strip().lower()


# ============================================================
# CONTACT -> CUSTOMER LINK
# ============================================================

def contact_has_customer_link(
    contact_name,
    customer_name
):

    if not contact_name or not customer_name:
        return False

    rows = frappe.get_all(
        "Dynamic Link",
        filters={
            "parent":
                contact_name,

            "parenttype":
                "Contact",

            "link_doctype":
                "Customer",

            "link_name":
                customer_name
        },
        fields=[
            "name"
        ],
        limit_page_length=1
    )

    return bool(rows)


# ============================================================
# LINK CONTACT TO CUSTOMER
# ============================================================

def link_contact_to_customer(
    contact,
    customer
):

    if not customer:
        return False

    customer_name = (
        customer.get("name")
    )

    if not customer_name:
        return False

    if contact_has_customer_link(
        contact.name,
        customer_name
    ):
        return False

    contact.append(
        "links",
        {
            "link_doctype":
                "Customer",

            "link_name":
                customer_name
        }
    )

    return True


# ============================================================
# FIND CONTACT BY VCRM ID
# ============================================================

def find_contact_by_vcrm_id(
    contact_id
):

    if not contact_id:
        return None

    meta = frappe.get_meta(
        "Contact"
    )

    if not meta.has_field(
        "custom_vcrm_contact_id"
    ):
        return None

    name = frappe.db.get_value(
        "Contact",
        {
            "custom_vcrm_contact_id":
                str(contact_id)
        },
        "name"
    )

    return name


# ============================================================
# FIND CONTACT BY MOBILE
# ============================================================

def find_contact_by_mobile(
    mobile
):

    mobile = normalize_mobile(
        mobile
    )

    if not mobile:
        return None

    rows = frappe.db.sql(
        """
        SELECT name, mobile_no, phone
        FROM `tabContact`
        WHERE mobile_no IS NOT NULL
        AND mobile_no != ''
        """,
        as_dict=True
    )

    for row in rows:

        if normalize_mobile(
            row.get("mobile_no")
        ) == mobile:

            return row.get("name")

        if normalize_mobile(
            row.get("phone")
        ) == mobile:

            return row.get("name")

    return None


# ============================================================
# FIND CONTACT BY EMAIL
# ============================================================

def find_contact_by_email(
    email
):

    email = normalize_email(
        email
    )

    if not email:
        return None

    rows = frappe.db.sql(
        """
        SELECT name, email_id
        FROM `tabContact`
        WHERE email_id IS NOT NULL
        AND email_id != ''
        """,
        as_dict=True
    )

    for row in rows:

        if normalize_email(
            row.get("email_id")
        ) == email:

            return row.get("name")

    return None


# ============================================================
# FIND EXISTING CONTACT
# ============================================================

def find_existing_contact(
    contact_data,
    customer_name,
    contact_id
):

    # --------------------------------------------------------
    # 1. VCRM ID - strongest match
    # --------------------------------------------------------

    existing = find_contact_by_vcrm_id(
        contact_id
    )

    if existing:
        return existing


    mobile = (
        contact_data.get("mobile")
        or ""
    ).strip()

    phone = (
        contact_data.get("phone")
        or ""
    ).strip()

    email = (
        contact_data.get("email")
        or ""
    ).strip()

    firstname = (
        contact_data.get("firstname")
        or ""
    ).strip()

    lastname = (
        contact_data.get("lastname")
        or ""
    ).strip()


    # --------------------------------------------------------
    # 2. MOBILE
    # --------------------------------------------------------

    existing = find_contact_by_mobile(
        mobile
    )

    if existing:
        return existing


    # --------------------------------------------------------
    # 3. PHONE
    # --------------------------------------------------------

    existing = find_contact_by_mobile(
        phone
    )

    if existing:
        return existing


    # --------------------------------------------------------
    # 4. EMAIL
    # --------------------------------------------------------

    existing = find_contact_by_email(
        email
    )

    if existing:
        return existing


    # --------------------------------------------------------
    # 5. CUSTOMER + FULL NAME
    # --------------------------------------------------------

    full_name = (
        firstname
        + " "
        + lastname
    ).strip()

    if full_name and customer_name:

        rows = frappe.db.sql(
            """
            SELECT DISTINCT c.name
            FROM `tabContact` c
            INNER JOIN `tabDynamic Link` dl
                ON dl.parent = c.name
                AND dl.parenttype = 'Contact'
                AND dl.link_doctype = 'Customer'
                AND dl.link_name = %s
            WHERE LOWER(
                TRIM(
                    CONCAT(
                        COALESCE(c.first_name, ''),
                        ' ',
                        COALESCE(c.last_name, '')
                    )
                )
            ) = LOWER(TRIM(%s))
            LIMIT 1
            """,
            (
                customer_name,
                full_name
            ),
            as_dict=True
        )

        if rows:
            return rows[0].get(
                "name"
            )

    return None


# ============================================================
# SANITIZE VCRM PHONE / EMAIL VALUES BEFORE WRITING TO BCRM
# Bad source values (names/emails in phone fields) are ignored, not fatal.
# ============================================================
def clean_phone(value):
    value = str(value or "").replace("\u200b", "").replace("\ufeff", "").strip()
    if not value:
        return ""
    # Reject values containing letters or @; keep only common phone punctuation.
    for ch in value:
        if not (ch.isdigit() or ch in "+-() .\t"):
            return ""
    digits = ""
    for ch in value:
        if ch.isdigit():
            digits += ch
    if len(digits) < 7 or len(digits) > 15:
        return ""
    # Store a normalized value; don't persist extensions/comments or invisible chars.
    return digits


def clean_email(value):
    value = str(value or "").replace("\u200b", "").replace("\ufeff", "").strip()
    if not value or " " in value or value.count("@") != 1:
        return ""
    parts = value.split("@")
    if not parts[0] or "." not in parts[1] or parts[1].startswith(".") or parts[1].endswith("."):
        return ""
    # Reject invalid domain characters (for example underscore in a domain).
    for ch in parts[1]:
        if not (ch.isalnum() or ch in ".-"):
            return ""
    for label in parts[1].split("."):
        if not label or label.startswith("-") or label.endswith("-"):
            return ""
    return value


def sanitize_contact_before_save(contact):
    # Keep generated Contact.full_name / Contact.name comfortably below
    # MariaDB's name column limit. Use conservative component limits because
    # Contact controller/autoname may add separators or other name components.
    # This only trims name components; phone/email data is handled below.
    first_name = str(contact.get("first_name") or "").strip()
    last_name = str(contact.get("last_name") or "").strip()
    middle_name = str(contact.get("middle_name") or "").strip()

    if len(first_name) > 40:
        contact.first_name = first_name[:40].rstrip()
    if len(last_name) > 40:
        contact.last_name = last_name[:40].rstrip()
    if len(middle_name) > 20:
        contact.middle_name = middle_name[:20].rstrip()

    # Invalid source values should not prevent importing the person's other valid data.
    contact.mobile_no = clean_phone(contact.get("mobile_no"))
    contact.phone = clean_phone(contact.get("phone"))
    contact.email_id = clean_email(contact.get("email_id"))

    # Remove invalid/duplicate phone child rows and enforce one primary per type.
    valid_rows = []
    seen = []
    for row in (contact.get("phone_nos") or []):
        number = clean_phone(row.get("phone"))
        if not number or number in seen:
            continue
        seen.append(number)
        row.phone = number
        valid_rows.append(row)
    contact.set("phone_nos", valid_rows)
    primary_mobile_set = False
    primary_phone_set = False
    for row in (contact.get("phone_nos") or []):
        if row.get("is_primary_mobile"):
            if primary_mobile_set:
                row.is_primary_mobile = 0
            else:
                primary_mobile_set = True
        if row.get("is_primary_phone"):
            if primary_phone_set:
                row.is_primary_phone = 0
            else:
                primary_phone_set = True
    if not primary_mobile_set and contact.get("phone_nos"):
        for row in contact.get("phone_nos"):
            if contact.mobile_no and row.phone == contact.mobile_no:
                row.is_primary_mobile = 1
                primary_mobile_set = True
                break
    if not primary_phone_set and contact.get("phone_nos"):
        for row in contact.get("phone_nos"):
            if contact.phone and row.phone == contact.phone and row.phone != contact.mobile_no:
                row.is_primary_phone = 1
                primary_phone_set = True
                break

    # Remove invalid email child rows and deduplicate case-insensitively.
    email_rows = []
    email_seen = []
    for row in (contact.get("email_ids") or []):
        address = clean_email(row.get("email_id"))
        key = address.lower()
        if not address or key in email_seen:
            continue
        email_seen.append(key)
        row.email_id = address
        email_rows.append(row)
    contact.set("email_ids", email_rows)


# ============================================================
# UPDATE EMAIL IDS CHILD TABLE
# ============================================================

def update_email_child_table(
    contact,
    email
):

    email = (
        email or ""
    ).strip()

    if not email:
        return

    existing = []

    for row in (
        contact.get("email_ids") or []
    ):

        existing_email = (
            row.get("email_id")
            or ""
        ).strip()

        if existing_email:
            existing.append(
                normalize_email(
                    existing_email
                )
            )

    if normalize_email(email) not in existing:

        row = contact.append(
            "email_ids",
            {}
        )

        row.email_id = email

        # First email becomes primary
        if len(existing) == 0:
            row.is_primary = 1


# ============================================================
# UPDATE PHONE CHILD TABLE
# ============================================================

def update_phone_child_table(contact, mobile, phone):
    mobile = clean_phone(mobile)
    phone = clean_phone(phone)
    numbers = []
    if mobile:
        numbers.append((mobile, True))
    if phone and phone != mobile:
        numbers.append((phone, False))

    existing = []
    for row in (contact.get("phone_nos") or []):
        number = clean_phone(row.get("phone"))
        if number:
            existing.append(number)
            row.phone = number

    for number, is_mobile in numbers:
        if number in existing:
            continue
        row = contact.append("phone_nos", {})
        row.phone = number
        if is_mobile:
            # Avoid multiple primary flags if an existing row is already primary.
            has_primary = False
            for old_row in (contact.get("phone_nos") or []):
                if old_row.name != row.name and old_row.get("is_primary_mobile"):
                    has_primary = True
            row.is_primary_mobile = 0 if has_primary else 1
        else:
            has_primary = False
            for old_row in (contact.get("phone_nos") or []):
                if old_row.name != row.name and old_row.get("is_primary_phone"):
                    has_primary = True
            row.is_primary_phone = 0 if has_primary else 1
        existing.append(number)


# ============================================================
# CUSTOMER CONTACT DETAILS
# ============================================================

def update_customer_contact_details(
    customer_name,
    contact
):

    if not customer_name:
        return

    if not frappe.db.exists(
        "Customer",
        customer_name
    ):
        return

    customer = frappe.get_doc(
        "Customer",
        customer_name
    )

    rows = (
        customer.get(
            "custom_contact_details"
        )
        or []
    )

    mobile = (
        contact.get("mobile_no")
        or ""
    )

    phone = (
        contact.get("phone")
        or ""
    )

    email = (
        contact.get("email_id")
        or ""
    )

    full_name = (
        contact.get("full_name")
        or ""
    )

    found = None

    for row in rows:

        if full_name and (
            (
                row.get("full_name")
                or ""
            ).strip().lower()
            ==
            full_name.strip().lower()
        ):
            found = row
            break

        if mobile and (
            normalize_mobile(
                row.get("mobile_phone")
            )
            ==
            normalize_mobile(mobile)
        ):
            found = row
            break

        if email and (
            normalize_email(
                row.get("primary_email")
            )
            ==
            normalize_email(email)
        ):
            found = row
            break


    if not found:

        found = customer.append(
            "custom_contact_details",
            {}
        )


    found.full_name = (
        full_name
    )

    found.customer_name = (
        customer.customer_name
        or customer.name
    )

    found.mobile_phone = (
        mobile
    )

    found.office_mobile = (
        phone
    )

    found.primary_email = (
        email
    )


    if contact.designation:

        found.titledesignation = (
            contact.designation
        )

    if contact.department:

        found.department = (
            contact.department
        )


    customer.save(
        ignore_permissions=True
    )


# ============================================================
# CONTACT FIELD MAPPING (NO IMPORT STATEMENTS)
# Mapping format: {"vcrm_source_key": "bcrm_target_field"}
# Only approved Contact fields can be written.
# ============================================================

def get_contact_field_mapping(raw_mapping=None):
    allowed = [
        "first_name", "last_name", "email_id", "mobile_no",
        "phone", "designation", "department"
    ]
    mapping = {}
    if isinstance(raw_mapping, dict):
        source_keys = [
            "firstname", "lastname", "email", "secondaryemail",
            "mobile", "phone", "title", "department"
        ]
        for source_key in source_keys:
            target = raw_mapping.get(source_key)
            if target in allowed:
                mapping[source_key] = target
    return mapping


def apply_contact_field_mapping(contact, vcrm_data, raw_mapping=None):
    mapping = get_contact_field_mapping(raw_mapping)
    source_aliases = {
        "firstname": "firstname",
        "lastname": "lastname",
        "email": "email",
        "secondaryemail": "secondaryemail",
        "mobile": "mobile",
        "phone": "phone",
        "title": "title",
        "department": "department"
    }
    for source_key in source_aliases:
        target = mapping.get(source_key)
        value = vcrm_data.get(source_key)
        if target and value is not None and str(value).strip():
            # Contact.email_id is the primary email. Do not let secondaryemail
            # overwrite it through the mapping UI; secondary email is handled
            # separately by the Contact Email child table.
            if source_key == "secondaryemail" and target == "email_id":
                continue
            contact.set(target, str(value).strip())


# ============================================================
# IMPORT ONE CONTACT
# ============================================================

def import_one_contact(
    base_url,
    session_name,
    contact_id,
    field_mapping=None
):

    import_stage = "validate_contact_id"

    if not contact_id:

        return {
            "success": False,
            "action": "import_one",
            "error":
                "Contact ID is required."
        }


    # --------------------------------------------------------
    # GET VCRM CONTACT
    # --------------------------------------------------------

    import_stage = "retrieve_vcrm_contact"
    contact_result = get_vcrm_contact(
        base_url,
        session_name,
        contact_id
    )

    if not contact_result.get("success"):

        return {
            "success": False,
            "action": "import_one",
            "contact_id":
                contact_id,
            "error":
                "Unable to retrieve VCRM Contact.",
            "details":
                contact_result
        }


    data = (
        contact_result.get("data")
        or {}
    )


    # --------------------------------------------------------
    # VCRM DATA
    # --------------------------------------------------------

    firstname = (
        data.get("firstname")
        or ""
    ).strip()

    lastname = (
        data.get("lastname")
        or ""
    ).strip()

    email = clean_email(data.get("email"))

    secondary_email = clean_email(data.get("secondaryemail"))

    mobile = clean_phone(data.get("mobile"))

    phone = clean_phone(data.get("phone"))

    account_id = (
        data.get("account_id")
        or data.get("accountid")
        or ""
    ).strip()


    # --------------------------------------------------------
    # ORGANIZATION
    # --------------------------------------------------------

    import_stage = "lookup_vcrm_organization"
    organization_name = (
        get_vcrm_organization(
            base_url,
            session_name,
            account_id
        )
    )


    # --------------------------------------------------------
    # CUSTOMER
    # --------------------------------------------------------

    customer = find_bcrm_customer(
        organization_name
    )

    customer_name = None

    if customer:
        customer_name = (
            customer.get("name")
        )


    # --------------------------------------------------------
    # EXISTING CONTACT
    # --------------------------------------------------------

    import_stage = "find_existing_contact"
    existing_name = find_existing_contact(
        data,
        customer_name,
        contact_id
    )


    created = False
    updated = False
    linked = False


    # ========================================================
    # EXISTING
    # ========================================================

    import_stage = "load_or_create_contact"
    if existing_name:

        contact = frappe.get_doc(
            "Contact",
            existing_name
        )


    # ========================================================
    # NEW
    # ========================================================

    else:

        contact = frappe.new_doc(
            "Contact"
        )

        created = True


    # --------------------------------------------------------
    # BASIC FIELDS
    # --------------------------------------------------------

    # Use the configured BCO series for newly created Contacts only.
    # This requires Contact autoname to be configured as naming_series:.
    if created and frappe.get_meta("Contact").has_field("naming_series"):
        contact.naming_series = "BCO-.YYYY.-.#######"

    if firstname:
        contact.first_name = firstname

    elif not contact.first_name and lastname:
        contact.first_name = lastname

    if lastname:
        contact.last_name = lastname

    if email:
        contact.email_id = email

    if mobile:
        contact.mobile_no = mobile

    if phone:
        contact.phone = phone


    # --------------------------------------------------------
    # VCRM ID
    # --------------------------------------------------------

    meta = frappe.get_meta(
        "Contact"
    )

    if meta.has_field(
        "custom_vcrm_contact_id"
    ):

        old_id = (
            contact.get(
                "custom_vcrm_contact_id"
            )
            or ""
        )

        if old_id != str(contact_id):

            contact.custom_vcrm_contact_id = (
                str(contact_id)
            )

            updated = True


    # --------------------------------------------------------
    # EMAIL CHILD TABLE
    # --------------------------------------------------------

    update_email_child_table(
        contact,
        email
    )

    update_email_child_table(
        contact,
        secondary_email
    )


    # --------------------------------------------------------
    # PHONE CHILD TABLE
    # --------------------------------------------------------

    update_phone_child_table(
        contact,
        mobile,
        phone
    )


    # --------------------------------------------------------
    # CUSTOMER LINK
    # --------------------------------------------------------

    if customer:

        linked = link_contact_to_customer(
            contact,
            customer
        )


    # --------------------------------------------------------
    # APPLY USER FIELD MAPPING
    # --------------------------------------------------------
    apply_contact_field_mapping(contact, data, field_mapping)

    # Final guard also sanitizes values introduced by custom field mapping.
    sanitize_contact_before_save(contact)

    # --------------------------------------------------------
    # SAVE / INSERT
    # --------------------------------------------------------

    import_stage = "save_contact"
    if created:

        contact.insert(
            ignore_permissions=True
        )

    else:

        contact.save(
            ignore_permissions=True
        )

        updated = True

    # Verify the VCRM source ID was actually persisted. Otherwise the UI may
    # report success while the dashboard continues to count this ID as missing.
    if meta.has_field("custom_vcrm_contact_id"):
        saved_vcrm_id = frappe.db.get_value(
            "Contact", contact.name, "custom_vcrm_contact_id"
        )
        if str(saved_vcrm_id or "") != str(contact_id):
            frappe.throw(
                "Contact was saved but custom_vcrm_contact_id was not persisted. "
                "Check the custom field configuration and permissions before retrying."
            )
    else:
        frappe.throw(
            "Missing Contact.custom_vcrm_contact_id field. Add this custom field "
            "before importing so dashboard counts and duplicate checks work correctly."
        )

    # --------------------------------------------------------
    # CUSTOMER CONTACT DETAILS
    # --------------------------------------------------------

    import_stage = "update_customer_contact_details"
    if customer_name:

        update_customer_contact_details(
            customer_name,
            contact
        )


    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    return {
        "success": True,

        "action":
            "import_one",

        "created":
            created,

        "updated":
            updated,

        "linked":
            linked,

        "contact":
            contact.name,

        "vcrm_contact_id":
            contact_id,

        "customer":
            customer_name,

        "customer_name":
            (
                customer.get(
                    "customer_name"
                )
                if customer
                else ""
            ),

        "organization":
            organization_name,

        "email":
            email,

        "secondary_email":
            secondary_email,

        "mobile":
            mobile,

        "phone":
            phone,

        "message":
            (
                "VCRM Contact imported/updated successfully."
            )
    }


@frappe.whitelist()
def import_vcrm_contacts():
    if frappe.session.user == "Guest":
        frappe.throw("Authentication required.")
    if not frappe.has_permission("Contact", "create") and not frappe.has_permission("Contact", "write"):
        frappe.throw("You need Contact create or write permission to use VCRM Contact Import.")
    # ============================================================
    # LOGIN
    # ============================================================

    base_url, session_name = vcrm_login()

    # ============================================================
    # ACTION
    # ============================================================

    action = (
        frappe.form_dict.get("action")
        or "list"
    )

    field_mapping_raw = frappe.form_dict.get("field_mapping") or "{}"
    try:
        field_mapping = frappe.parse_json(field_mapping_raw)
    except Exception:
        field_mapping = {}
    if not isinstance(field_mapping, dict):
        field_mapping = {}


    # ============================================================
    # DESCRIBE
    # ============================================================



    # ============================================================
    # ORGANIZATION SEARCH SUPPORT
    # Search contacts by their linked VCRM Organization / Account.
    # VCRM is queried read-only; no VCRM records are modified.
    # ============================================================

    def get_vcrm_account_ids_for_search(base_url, session_name, search_text):
        search_text = (search_text or "").strip()
        if not search_text:
            return []

        safe_search = search_text.replace("'", "''")
        query = (
            "select id, accountname from Accounts "
            "where accountname like '%" + safe_search + "%' "
            "limit 0,1000;"
        )
        result = vcrm_request(
            base_url,
            session_name,
            "query",
            {"query": query}
        )

        ids = []
        if result.get("success"):
            for row in (result.get("result") or []):
                account_id = row.get("id") or row.get("accountid")
                if account_id:
                    ids.append(str(account_id))
        return ids


    def build_contact_search_where(base_url, session_name, search_text):
        search_text = (search_text or "").strip()
        if not search_text:
            return ""

        safe_search = search_text.replace("'", "''")
        clauses = [
            "id like '%" + safe_search + "%'",
            "firstname like '%" + safe_search + "%'",
            "lastname like '%" + safe_search + "%'",
            "email like '%" + safe_search + "%'",
            "mobile like '%" + safe_search + "%'",
            "phone like '%" + safe_search + "%'"
        ]

        # Also include contacts whose linked organization name matches.
        account_ids = get_vcrm_account_ids_for_search(
            base_url, session_name, search_text
        )
        if account_ids:
            # IDs originate from VCRM query results; keep only safe alphanumeric IDs.
            safe_ids = [
                account_id for account_id in account_ids
                if account_id and all(ch.isalnum() or ch in "_-" for ch in account_id)
            ]
            for account_id in safe_ids:
                clauses.append(
                    "account_id = '" + account_id + "'"
                )

        # Vtiger query language may reject parenthesized WHERE groups and IN().
        # Keep the same flat OR syntax used by the original working contact search.
        return " where " + " or ".join(clauses)


    if action == "describe":

        result = vcrm_request(
            base_url,
            session_name,
            "describe",
            {
                "elementType":
                    "Contacts"
            }
        )

        frappe.response["message"] = {
            "success":
                bool(
                    result.get("success")
                ),

            "action":
                "describe",

            "data":
                result
        }


    # ============================================================
    # GLOBAL STATS: count all BCRM contacts imported from VCRM by source ID
    # ============================================================

    elif action == "stats":

        count_result = vcrm_request(
            base_url,
            session_name,
            "query",
            {"query": "select count(*) from Contacts;"}
        )

        total_count = 0
        count_error = ""
        if count_result.get("success"):
            count_rows = count_result.get("result") or []
            if count_rows:
                first_row = count_rows[0]
                if isinstance(first_row, dict):
                    count_values = list(first_row.values())
                    if count_values:
                        total_count = int(count_values[0] or 0)
                else:
                    total_count = int(first_row or 0)
        else:
            count_error = str(count_result.get("error") or count_result)

        imported_count = 0
        has_vcrm_id = frappe.get_meta("Contact").has_field("custom_vcrm_contact_id")
        if has_vcrm_id:
            imported_count = frappe.db.count(
                "Contact",
                {"custom_vcrm_contact_id": ["is", "set"]}
            )
        else:
            count_error = count_error or (
                "Contact field custom_vcrm_contact_id is missing. Add this custom field "
                "before importing so imported contacts can be counted and deduplicated."
            )

        frappe.response["message"] = {
            "success": not bool(count_error),
            "action": "stats",
            "total_count": total_count,
            "already_imported_count": imported_count,
            "remaining_count": max(0, total_count - imported_count),
            "error": count_error,
            "has_vcrm_id_field": has_vcrm_id
        }


    # ============================================================
    # COUNT
    # ============================================================

    elif action == "count":

        search = (
            frappe.form_dict.get("search")
            or ""
        ).strip()

        where_sql = build_contact_search_where(
            base_url,
            session_name,
            search
        )


        query = (
            "select count(*) "
            "from Contacts"
            + where_sql
            + ";"
        )


        result = vcrm_request(
            base_url,
            session_name,
            "query",
            {
                "query":
                    query
            }
        )


        total_count = 0

        if result.get("success"):

            rows = (
                result.get("result")
                or []
            )

            if rows:

                first_row = rows[0]

                if isinstance(
                    first_row,
                    dict
                ):

                    values = list(
                        first_row.values()
                    )

                    if values:

                        total_count = int(
                            values[0] or 0
                        )

                else:

                    total_count = int(
                        first_row or 0
                    )


        frappe.response["message"] = {

            "success":
                bool(
                    result.get("success")
                ),

            "action":
                "count",

            "total_count":
                total_count,

            "data":
                result
        }


    # ============================================================
    # REMAINING LIST: query only VCRM contacts whose IDs are not yet stored in BCRM
    # ============================================================

    elif action == "remaining_list":

        # Reuse the authenticated session created once above.
        # Avoid NOT IN: some Vtiger installations reject it or URL/query strings become too large.
        total_result = vcrm_request(
            base_url, session_name, "query",
            {"query": "select count(*) from Contacts;"}
        )
        total_count = 0
        if total_result.get("success"):
            total_rows = total_result.get("result") or []
            if total_rows:
                first = total_rows[0]
                if isinstance(first, dict):
                    vals = list(first.values())
                    total_count = int(vals[0] or 0) if vals else 0
                else:
                    total_count = int(first or 0)
        else:
            frappe.response["message"] = {
                "success": False,
                "action": "remaining_list",
                "error": "Could not count VCRM Contacts",
                "details": total_result
            }
            total_count = -1

        if total_count >= 0:
            imported_ids = []
            if frappe.get_meta("Contact").has_field("custom_vcrm_contact_id"):
                imported_ids = frappe.get_all(
                    "Contact",
                    filters={"custom_vcrm_contact_id": ["is", "set"]},
                    pluck="custom_vcrm_contact_id",
                    limit_page_length=0
                )

            imported_id_set = set()
            for imported_id in imported_ids:
                imported_id = str(imported_id or "").strip()
                if imported_id:
                    imported_id_set.add(imported_id)

            # VCRM may cap query responses at 100 rows even when LIMIT asks for 500.
            # Use 100-row pages and keep scanning after a short (non-empty) response.
            # Stop only on an empty batch or once the reported total is reached.
            batch_size = 100
            offset = 0
            remaining_count = 0
            remaining_rows = []
            scan_error = None

            while offset < total_count:
                batch_query = (
                    "select id,firstname,lastname,email,mobile,phone,account_id "
                    "from Contacts order by id limit " + str(offset) + "," + str(batch_size) + ";"
                )
                batch_result = vcrm_request(
                    base_url, session_name, "query", {"query": batch_query}
                )
                if not batch_result.get("success"):
                    scan_error = batch_result
                    break

                batch_rows = batch_result.get("result") or []
                if not batch_rows:
                    break

                for row in batch_rows:
                    contact_id = str(row.get("id") or "").strip()
                    if not contact_id or contact_id in imported_id_set:
                        continue
                    remaining_count += 1
                    if len(remaining_rows) < 500:
                        remaining_rows.append(row)

                # Advance by the number actually returned. Do not stop merely because
                # the server returned fewer rows than requested; some VCRM instances
                # enforce a lower server-side page cap.
                offset += len(batch_rows)
                if offset >= total_count:
                    break

            if scan_error:
                frappe.response["message"] = {
                    "success": False,
                    "action": "remaining_list",
                    "error": "Could not scan VCRM Contacts in batches.",
                    "details": scan_error,
                    "total_count": total_count
                }
            else:
                account_cache = {}
                for row in remaining_rows:
                    account_id = str(row.get("account_id") or row.get("accountid") or "")
                    if account_id:
                        if account_id not in account_cache:
                            account_cache[account_id] = get_vcrm_organization(
                                base_url, session_name, account_id
                            )
                        organization_name = account_cache.get(account_id) or ""
                    else:
                        organization_name = ""
                    row["organization_name"] = organization_name
                    customer = find_bcrm_customer(organization_name) if organization_name else None
                    row["customer_name"] = (customer.get("customer_name") or "") if customer else ""
                    row["customer"] = (customer.get("name") or "") if customer else ""
                    row["already_imported"] = False
                    row["bcrm_contact"] = ""

                frappe.response["message"] = {
                    "success": True,
                    "action": "remaining_list",
                    "total_count": total_count,
                    "already_imported_count": len(imported_id_set),
                    "remaining_count": remaining_count,
                    "returned_count": len(remaining_rows),
                    "data": remaining_rows
                }

    # ============================================================
    # LIST
    # ============================================================

    elif action == "list":

        try:

            page = int(
                frappe.form_dict.get(
                    "page"
                )
                or 1
            )

        except Exception:

            page = 1


        try:

            page_size = int(
                frappe.form_dict.get(
                    "page_size"
                )
                or 100
            )

        except Exception:

            page_size = 100


        search = (
            frappe.form_dict.get("search")
            or ""
        ).strip()


        if page < 1:
            page = 1

        if page_size < 1:
            page_size = 100

        if page_size > 100:
            page_size = 100


        offset = (
            (page - 1)
            * page_size
        )


        where_sql = build_contact_search_where(
            base_url,
            session_name,
            search
        )


        count_query = (
            "select count(*) "
            "from Contacts"
            + where_sql
            + ";"
        )


        count_result = vcrm_request(
            base_url,
            session_name,
            "query",
            {
                "query":
                    count_query
            }
        )


        total_count = 0

        if count_result.get("success"):

            count_rows = (
                count_result.get(
                    "result"
                )
                or []
            )

            if count_rows:

                first = count_rows[0]

                if isinstance(
                    first,
                    dict
                ):

                    values = list(
                        first.values()
                    )

                    if values:

                        total_count = int(
                            values[0] or 0
                        )

                else:

                    total_count = int(
                        first or 0
                    )


        contact_query = (
            "select "
            "id,"
            "firstname,"
            "lastname,"
            "email,"
            "mobile,"
            "phone,"
            "account_id "
            "from Contacts"
            + where_sql
            + " order by id "
            + "limit "
            + str(offset)
            + ","
            + str(page_size)
            + ";"
        )


        contact_result = vcrm_request(
            base_url,
            session_name,
            "query",
            {
                "query":
                    contact_query
            }
        )


        if not contact_result.get("success"):

            frappe.response["message"] = {

                "success":
                    False,

                "action":
                    "list",

                "error":
                    "VCRM Contacts query failed.",

                "details":
                    contact_result
            }

        else:

            contact_rows = (
                contact_result.get(
                    "result"
                )
                or []
            )

            account_cache = {}


            for row in contact_rows:

                account_id = (
                    row.get("account_id")
                    or row.get("accountid")
                    or ""
                )

                organization_name = ""

                if account_id:

                    if account_id in account_cache:

                        organization_name = (
                            account_cache.get(
                                account_id
                            )
                            or ""
                        )

                    else:

                        organization_name = (
                            get_vcrm_organization(
                                base_url,
                                session_name,
                                account_id
                            )
                        )

                        account_cache[
                            account_id
                        ] = organization_name


                row[
                    "organization_name"
                ] = organization_name


                customer = find_bcrm_customer(
                    organization_name
                )


                if customer:

                    row[
                        "customer_name"
                    ] = (
                        customer.get(
                            "customer_name"
                        )
                        or ""
                    )

                    row[
                        "customer"
                    ] = (
                        customer.get(
                            "name"
                        )
                        or ""
                    )

                else:

                    row[
                        "customer_name"
                    ] = ""

                    row[
                        "customer"
                    ] = ""


                existing_contact = (
                    find_existing_contact(
                        row,
                        row.get("customer"),
                        row.get("id")
                    )
                )


                row[
                    "already_imported"
                ] = bool(
                    existing_contact
                )


                row[
                    "bcrm_contact"
                ] = (
                    existing_contact
                    or ""
                )


            total_pages = 1

            if total_count > 0:

                total_pages = (
                    (
                        total_count
                        + page_size
                        - 1
                    )
                    // page_size
                )


            frappe.response["message"] = {

                "success":
                    True,

                "action":
                    "list",

                "page":
                    page,

                "page_size":
                    page_size,

                "total_count":
                    total_count,

                "total_pages":
                    total_pages,

                "data":
                    contact_rows
            }


    # ============================================================
    # PREVIEW
    # ============================================================

    elif action == "preview":

        contact_id = (
            frappe.form_dict.get(
                "contact_id"
            )
            or ""
        ).strip()


        if not contact_id:

            frappe.response["message"] = {

                "success":
                    False,

                "action":
                    "preview",

                "error":
                    "Contact ID is required."
            }

        else:

            contact_result = get_vcrm_contact(
                base_url,
                session_name,
                contact_id
            )


            if not contact_result.get(
                "success"
            ):

                frappe.response["message"] = {

                    "success":
                        False,

                    "action":
                        "preview",

                    "error":
                        "Unable to retrieve VCRM Contact.",

                    "details":
                        contact_result
                }

            else:

                contact_data = (
                    contact_result.get(
                        "data"
                    )
                    or {}
                )


                account_id = (
                    contact_data.get(
                        "account_id"
                    )
                    or contact_data.get(
                        "accountid"
                    )
                    or ""
                )


                organization_name = (
                    get_vcrm_organization(
                        base_url,
                        session_name,
                        account_id
                    )
                )


                customer = find_bcrm_customer(
                    organization_name
                )


                contact_data[
                    "organization_name"
                ] = organization_name


                contact_data[
                    "bcrm_customer"
                ] = (
                    customer.get("name")
                    if customer
                    else ""
                )


                contact_data[
                    "bcrm_customer_name"
                ] = (
                    customer.get(
                        "customer_name"
                    )
                    if customer
                    else ""
                )


                frappe.response["message"] = {

                    "success":
                        True,

                    "action":
                        "preview",

                    "data":
                        contact_data
                }


    # ============================================================
    # IMPORT ONE
    # ============================================================

    elif action == "import_one":

        contact_id = (
            frappe.form_dict.get(
                "contact_id"
            )
            or ""
        ).strip()


        if not contact_id:

            frappe.response["message"] = {

                "success":
                    False,

                "action":
                    "import_one",

                "error":
                    "Contact ID is required."
            }

        else:

            try:

                result = import_one_contact(
                    base_url,
                    session_name,
                    contact_id,
                    field_mapping
                )

                frappe.response["message"] = (
                    result
                )

            except Exception as e:

                error_text = str(e)
                message = (
                    "Contact import failed. "
                    "If the error is '__import__', this is commonly caused by "
                    "Frappe Server Script safe_exec blocking a framework/controller "
                    "import during Contact insert/save; moving this API to a whitelisted "
                    "method in a custom app is the reliable fix. "
                    "Original error: " + error_text
                )

                frappe.response["message"] = {
                    "success": False,
                    "action": "import_one",
                    "contact_id": contact_id,
                    "error": message
                }


    # ============================================================
    # IMPORT MANY
    # ============================================================

    elif action == "import_many":

        raw_ids = (
            frappe.form_dict.get(
                "contact_ids"
            )
            or "[]"
        )


        try:

            contact_ids = frappe.parse_json(
                raw_ids
            )

        except Exception:

            contact_ids = []


        if not isinstance(
            contact_ids,
            list
        ):

            contact_ids = []


        if not contact_ids:

            frappe.response["message"] = {

                "success":
                    False,

                "action":
                    "import_many",

                "error":
                    "No contacts selected."
            }

        else:

            results = []

            success_count = 0

            failed_count = 0


            for contact_id in contact_ids:

                try:
                    existing_by_id = find_contact_by_vcrm_id(contact_id)
                    if existing_by_id:
                        results.append({"success": True, "skipped": True, "contact_id": str(contact_id), "contact": existing_by_id, "message": "Already imported; skipped."})
                        continue

                    result = import_one_contact(
                        base_url,
                        session_name,
                        contact_id,
                        field_mapping
                    )

                    results.append(
                        result
                    )

                    if result.get(
                        "success"
                    ):

                        success_count += 1

                    else:

                        failed_count += 1


                except Exception as e:

                    failed_count += 1

                    results.append({

                        "success":
                            False,

                        "contact_id":
                            contact_id,

                        "error":
                            (
                                "Contact import failed: " + str(e) +
                                (". The Contact name may exceed the database name-column limit; name fields are now trimmed before save. Retry this contact after updating the server script."
                                 if "Data too long for column 'name'" in str(e) else "") +
                                (". If this is '__import__', move the import API "
                                 "from Server Script to a whitelisted custom-app method."
                                 if str(e) == "'__import__'" else "")
                            )
                    })


            frappe.response["message"] = {

                "success":
                    failed_count == 0,

                "action":
                    "import_many",

                "total":
                    len(contact_ids),

                "success_count":
                    success_count,

                "failed_count":
                    failed_count,

                "results":
                    results
            }


    # ============================================================
    # IMPORT ALL
    # ============================================================

    elif action == "import_all":

        # Bounded scan batches. Offset is a VCRM scan offset, not imported count.
        # Already-imported records are skipped by exact VCRM Contact ID.
        try:
            offset = max(0, int(frappe.form_dict.get("offset") or 0))
        except Exception:
            offset = 0

        try:
            batch_size = int(frappe.form_dict.get("batch_size") or 10)
        except Exception:
            batch_size = 10
        batch_size = max(1, min(batch_size, 10))

        count_result = vcrm_request(
            base_url, session_name, "query",
            {"query": "select count(*) from Contacts;"}
        )
        total_count = 0
        if count_result.get("success"):
            count_rows = count_result.get("result") or []
            if count_rows:
                first_row = count_rows[0]
                if isinstance(first_row, dict):
                    count_values = list(first_row.values())
                    if count_values:
                        total_count = int(count_values[0] or 0)
                else:
                    total_count = int(first_row or 0)
        else:
            frappe.response["message"] = {
                "success": False, "action": "import_all",
                "error": "Unable to count VCRM contacts.", "details": count_result
            }

        if not frappe.response.get("message"):
            # Exact ID count for the dashboard; do not modify VCRM.
            imported_count = 0
            if frappe.get_meta("Contact").has_field("custom_vcrm_contact_id"):
                imported_count = frappe.db.count(
                    "Contact", {"custom_vcrm_contact_id": ["is", "set"]}
                )

            batch_query = (
                "select id,firstname,lastname,email,mobile,phone,account_id "
                "from Contacts order by id limit " + str(offset) + "," + str(batch_size) + ";"
            )
            batch_result = vcrm_request(
                base_url, session_name, "query", {"query": batch_query}
            )

            if not batch_result.get("success"):
                frappe.response["message"] = {
                    "success": False, "action": "import_all", "offset": offset,
                    "error": "Unable to load this VCRM contact batch.", "details": batch_result
                }
            else:
                batch_rows = batch_result.get("result") or []
                results = []
                success_count = 0
                failed_count = 0
                skipped_count = 0

                for row in batch_rows:
                    contact_id = row.get("id")
                    if not contact_id:
                        failed_count += 1
                        results.append({"success": False, "contact_id": "", "error": "VCRM row has no Contact ID."})
                        continue

                    try:
                        existing_by_id = find_contact_by_vcrm_id(contact_id)
                        if existing_by_id:
                            skipped_count += 1
                            results.append({
                                "success": True, "skipped": True,
                                "contact_id": str(contact_id),
                                "contact": existing_by_id,
                                "message": "Already imported; skipped."
                            })
                            continue

                        result = import_one_contact(
                            base_url, session_name, contact_id, field_mapping
                        )
                        results.append(result)
                        if result.get("success"):
                            success_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        failed_count += 1
                        results.append({
                            "success": False, "contact_id": str(contact_id),
                            "error": "Contact import failed: " + str(e) +
                                (". This '__import__' error requires moving this API from Server Script to a whitelisted custom-app Python method." if str(e) == "'__import__'" else "")
                        })

                next_offset = offset + len(batch_rows)
                frappe.response["message"] = {
                    "success": failed_count == 0,
                    "action": "import_all",
                    "offset": offset,
                    "next_offset": next_offset,
                    "total_count": total_count,
                    "already_imported_count": imported_count,
                    "remaining_before_scan": max(0, total_count - imported_count),
                    "batch_size": batch_size,
                    "scanned_in_batch": len(batch_rows),
                    "processed_in_batch": success_count + failed_count + skipped_count,
                    "success_count": success_count,
                    "skipped_count": skipped_count,
                    "failed_count": failed_count,
                    "has_more": next_offset < total_count and len(batch_rows) > 0,
                    "results": results,
                    "message": "Batch scanned. Existing exact-ID imports skipped; continue from next_offset."
                }


    # ============================================================
    # INVALID ACTION
    # ============================================================

    else:

        frappe.response["message"] = {

            "success":
                False,

            "action":
                action,

            "error":
                "Invalid action",

            "allowed_actions": [
                "describe",
                "stats",
                "count",
                "list",
                "preview",
                "import_one",
                "import_many",
                "import_all"
            ]
        }
    return frappe.response.get("message")
