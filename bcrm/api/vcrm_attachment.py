import base64
import requests
import frappe


@frappe.whitelist()
def download_vcrm_attachment(
    document_id,
    file_id,
    folder_id,
    file_name
):
    result = {
        "success": False,
        "status": "",
        "message": "",
        "status_code": 0,
        "content_type": "",
        "content_size": 0,
        "final_url": "",
        "document_id": str(document_id or ""),
        "file_id": str(file_id or ""),
        "folder_id": str(folder_id or ""),
        "file_name": str(file_name or "")
    }

    try:

        # =========================================================
        # 1. VALIDATE
        # =========================================================

        if not document_id:
            result["status"] = "missing_document_id"
            result["message"] = "VCRM document ID is required."
            return result

        if not file_id:
            result["status"] = "missing_file_id"
            result["message"] = "VCRM file ID is required."
            return result

        if not file_name:
            result["status"] = "missing_file_name"
            result["message"] = "VCRM file name is required."
            return result

        # =========================================================
        # 2. SETTINGS
        # =========================================================

        settings = frappe.get_doc(
            "VCRM Integration Settings"
        )

        username = (
            getattr(settings, "username", "")
            or ""
        ).strip()

        if not username:
            result["status"] = "missing_vcrm_username"
            result["message"] = (
                "VCRM username is not configured."
            )
            return result

        try:
            password = settings.get_password(
                "vcrm_password"
            )
        except Exception as e:
            result["status"] = "password_field_error"
            result["message"] = (
                "Unable to read vcrm_password."
            )
            result["password_error"] = str(e)
            return result

        if not password:
            result["status"] = "missing_vcrm_password"
            result["message"] = (
                "VCRM Password is empty."
            )
            return result

        # =========================================================
        # 3. IMPORTANT
        #
        # vtiger_url is WEBSERVICE URL.
        # VCRM UI is a DIFFERENT URL.
        # =========================================================

        vcrm_web_url = "https://crm.btpl.net"

        # =========================================================
        # 4. CREATE SESSION
        # =========================================================

        session = requests.Session()

        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/154.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9"
        })

        # =========================================================
        # 5. OPEN ACTUAL VCRM LOGIN PAGE
        # =========================================================

        login_url = (
            vcrm_web_url
            + "/index.php"
        )

        try:
            login_page = session.get(
                login_url,
                params={
                    "module": "Users",
                    "action": "Login"
                },
                verify=False,
                timeout=30,
                allow_redirects=True
            )

            result["login_page_status"] = (
                login_page.status_code
            )

            result["login_page_url"] = (
                str(login_page.url or "")
            )

        except Exception as e:
            result["status"] = "login_page_failed"
            result["message"] = (
                "Unable to open VCRM web login page."
            )
            result["login_page_error"] = str(e)
            return result

        # =========================================================
        # 6. LOGIN
        # =========================================================

        login_data = {
            "module": "Users",
            "action": "Login",
            "login_user_name": username,
            "login_password": password
        }

        try:
            login_response = session.post(
                login_url,
                data=login_data,
                verify=False,
                timeout=30,
                allow_redirects=True
            )

            result["login_status_code"] = (
                login_response.status_code
            )

            result["login_final_url"] = (
                str(login_response.url or "")
            )

        except Exception as e:
            result["status"] = "login_request_failed"
            result["message"] = (
                "VCRM web login request failed."
            )
            result["login_error"] = str(e)
            return result

        # =========================================================
        # 7. SESSION COOKIE
        # =========================================================

        cookie_count = 0

        try:
            cookie_count = len(session.cookies)
        except Exception:
            cookie_count = 0

        result["session_cookie_count"] = cookie_count

        # =========================================================
        # 8. CHECK LOGIN
        # =========================================================

        login_html = (
            login_response.text
            if login_response.text
            else ""
        )

        login_lower = login_html.lower()

        login_failed = False

        if (
            "login_user_name" in login_lower
            and "login_password" in login_lower
        ):
            login_failed = True

        if "invalid username" in login_lower:
            login_failed = True

        if "invalid password" in login_lower:
            login_failed = True

        if "invalid username or password" in login_lower:
            login_failed = True

        if login_failed:
            result["status"] = "vcrm_login_failed"
            result["message"] = (
                "VCRM web login failed. "
                "Check username and password."
            )
            return result

        if cookie_count == 0:
            result["status"] = "vcrm_session_not_created"
            result["message"] = (
                "VCRM web login did not create a session cookie."
            )
            return result

        # =========================================================
        # 9. DOCUMENT DETAIL
        # =========================================================

        detail_url = (
            vcrm_web_url
            + "/index.php"
        )

        try:
            detail_response = session.get(
                detail_url,
                params={
                    "module": "Documents",
                    "view": "Detail",
                    "record": str(document_id),
                    "app": ""
                },
                verify=False,
                timeout=30,
                allow_redirects=True
            )

            result["detail_status_code"] = (
                detail_response.status_code
            )

            result["detail_final_url"] = (
                str(detail_response.url or "")
            )

        except Exception as e:
            result["status"] = "document_detail_failed"
            result["message"] = (
                "Unable to open VCRM document detail."
            )
            result["detail_error"] = str(e)
            return result

        detail_html = (
            detail_response.text
            if detail_response.text
            else ""
        )

        detail_lower = detail_html.lower()

        # =========================================================
        # 10. SESSION CHECK
        # =========================================================

        if (
            "login_user_name" in detail_lower
            and "login_password" in detail_lower
        ):
            result["status"] = "session_not_authenticated"
            result["message"] = (
                "VCRM redirected to login page. "
                "The web session was not authenticated."
            )
            return result

        # =========================================================
        # 11. DOWNLOAD
        # =========================================================

        download_url = (
            vcrm_web_url
            + "/index.php"
        )

        download_params = {
            "module": "Documents",
            "action": "DownloadFile",
            "record": str(document_id),
            "fileid": str(file_id),
            "name": str(file_name)
        }

        if folder_id:
            download_params["folderid"] = str(folder_id)

        try:
            download_response = session.get(
                download_url,
                params=download_params,
                verify=False,
                timeout=60,
                allow_redirects=True
            )

        except Exception as e:
            result["status"] = "download_request_failed"
            result["message"] = (
                "VCRM attachment download failed."
            )
            result["download_error"] = str(e)
            return result

        # =========================================================
        # 12. RESPONSE INFO
        # =========================================================

        result["status_code"] = (
            download_response.status_code
        )

        result["content_type"] = (
            download_response.headers.get(
                "Content-Type",
                ""
            )
        )

        result["content_size"] = len(
            download_response.content
        )

        result["final_url"] = (
            str(download_response.url or "")
        )

        # =========================================================
        # 13. HTTP ERROR
        # =========================================================

        if download_response.status_code != 200:
            result["status"] = "download_failed"
            result["message"] = (
                "VCRM returned HTTP "
                + str(download_response.status_code)
                + "."
            )
            return result

        # =========================================================
        # 14. EMPTY
        # =========================================================

        if not download_response.content:
            result["status"] = "empty_attachment"
            result["message"] = (
                "VCRM returned an empty attachment."
            )
            return result

        # =========================================================
        # 15. HTML CHECK
        # =========================================================

        content_type = (
            download_response.headers.get(
                "Content-Type",
                ""
            ).lower()
        )

        first_bytes = (
            download_response.content[:1000]
            .lower()
        )

        if (
            "text/html" in content_type
            or b"<html" in first_bytes
            or b"<!doctype html" in first_bytes
        ):
            result["status"] = (
                "authentication_or_redirect"
            )
            result["message"] = (
                "VCRM returned HTML instead of "
                "the actual attachment."
            )
            return result

        # =========================================================
        # 16. SUCCESS
        # =========================================================

        file_content = base64.b64encode(
            download_response.content
        ).decode("ascii")

        result["success"] = True
        result["status"] = "success"
        result["message"] = (
            "VCRM attachment downloaded successfully."
        )
        result["file_content"] = file_content

        return result

    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)
        return result
