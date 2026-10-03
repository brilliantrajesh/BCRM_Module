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
        # ---------------------------------------------------------
        # 1. VALIDATE INPUT
        # ---------------------------------------------------------

        if not document_id:
            result["status"] = "missing_document_id"
            result["message"] = "VCRM document ID is required."
            return result

        if not file_id:
            result["status"] = "missing_file_id"
            result["message"] = "VCRM attachment file ID is required."
            return result

        if not file_name:
            result["status"] = "missing_file_name"
            result["message"] = "VCRM attachment file name is required."
            return result

        # ---------------------------------------------------------
        # 2. GET VCRM SETTINGS
        # ---------------------------------------------------------

        settings = frappe.get_doc(
            "VCRM Integration Settings"
        )

        base_url = (
            getattr(settings, "vtiger_url", "")
            or ""
        ).strip().rstrip("/")

        username = (
            getattr(settings, "username", "")
            or ""
        ).strip()

        if not base_url:
            result["status"] = "missing_vcrm_url"
            result["message"] = (
                "VCRM URL is not configured."
            )
            return result

        if not username:
            result["status"] = "missing_vcrm_username"
            result["message"] = (
                "VCRM username is not configured."
            )
            return result

        # ---------------------------------------------------------
        # 3. GET VCRM PASSWORD
        # ---------------------------------------------------------

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

        # ---------------------------------------------------------
        # 4. CREATE WEB SESSION
        # ---------------------------------------------------------

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

        # ---------------------------------------------------------
        # 5. OPEN LOGIN PAGE
        # ---------------------------------------------------------

        login_page_url = (
            base_url
            + "/index.php"
            "?module=Users"
            "&action=Login"
        )

        try:
            login_page = session.get(
                login_page_url,
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
                "Unable to open VCRM login page."
            )
            result["login_page_error"] = str(e)
            return result

        # ---------------------------------------------------------
        # 6. IMPORTANT:
        # VTIGER USES login_user_name / login_password
        # ---------------------------------------------------------

        login_data = {
            "module": "Users",
            "action": "Login",
            "login_user_name": username,
            "login_password": password
        }

        # ---------------------------------------------------------
        # 7. LOGIN
        # ---------------------------------------------------------

        try:
            login_response = session.post(
                login_page_url,
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

        # ---------------------------------------------------------
        # 8. SESSION COOKIE CHECK
        # ---------------------------------------------------------

        cookie_count = 0

        try:
            cookie_count = len(session.cookies)
        except Exception:
            cookie_count = 0

        result["session_cookie_count"] = cookie_count

        # ---------------------------------------------------------
        # 9. CHECK LOGIN RESPONSE
        # ---------------------------------------------------------

        login_html = (
            login_response.text
            if login_response.text
            else ""
        )

        login_lower = login_html.lower()

        still_login_page = False

        if (
            "login_user_name" in login_lower
            and "login_password" in login_lower
        ):
            still_login_page = True

        if (
            "invalid username or password" in login_lower
            or "invalid username" in login_lower
            or "invalid password" in login_lower
        ):
            still_login_page = True

        if still_login_page:
            result["status"] = "vcrm_login_failed"
            result["message"] = (
                "VCRM web login failed. "
                "Check VCRM username and password."
            )
            return result

        if cookie_count == 0:
            result["status"] = "vcrm_session_not_created"
            result["message"] = (
                "VCRM login did not create a session."
            )
            return result

        # ---------------------------------------------------------
        # 10. OPEN DOCUMENT DETAIL
        # ---------------------------------------------------------

        detail_url = (
            base_url
            + "/index.php"
            "?module=Documents"
            "&view=Detail"
            "&record="
            + str(document_id)
            + "&app="
        )

        try:
            detail_response = session.get(
                detail_url,
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

        # ---------------------------------------------------------
        # 11. CHECK WHETHER DETAIL REDIRECTED TO LOGIN
        # ---------------------------------------------------------

        if (
            "login_user_name" in detail_lower
            and "login_password" in detail_lower
        ):
            result["status"] = "session_not_authenticated"
            result["message"] = (
                "VCRM session was created but the "
                "Documents page redirected to login."
            )
            return result

        if (
            "/index.php?action=login"
            in str(detail_response.url or "").lower()
        ):
            result["status"] = "session_not_authenticated"
            result["message"] = (
                "VCRM session was not accepted "
                "for Documents."
            )
            return result

        # ---------------------------------------------------------
        # 12. DOWNLOAD ATTACHMENT
        # ---------------------------------------------------------

        download_url = (
            base_url
            + "/index.php"
            "?module=Documents"
            "&action=DownloadFile"
            "&record="
            + str(document_id)
            + "&fileid="
            + str(file_id)
        )

        if folder_id:
            download_url += (
                "&folderid="
                + str(folder_id)
            )

        download_url += (
            "&name="
            + requests.utils.quote(
                str(file_name)
            )
        )

        result["download_url"] = download_url

        # ---------------------------------------------------------
        # 13. DOWNLOAD USING SAME AUTHENTICATED SESSION
        # ---------------------------------------------------------

        try:
            download_response = session.get(
                download_url,
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

        # ---------------------------------------------------------
        # 14. RESPONSE DETAILS
        # ---------------------------------------------------------

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

        # ---------------------------------------------------------
        # 15. HTTP ERROR
        # ---------------------------------------------------------

        if download_response.status_code != 200:
            result["status"] = "download_failed"
            result["message"] = (
                "VCRM returned HTTP "
                + str(download_response.status_code)
                + "."
            )
            return result

        # ---------------------------------------------------------
        # 16. EMPTY RESPONSE
        # ---------------------------------------------------------

        if not download_response.content:
            result["status"] = "empty_attachment"
            result["message"] = (
                "VCRM returned an empty attachment."
            )
            return result

        # ---------------------------------------------------------
        # 17. CHECK HTML
        # ---------------------------------------------------------

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

        is_html = False

        if "text/html" in content_type:
            is_html = True

        if b"<html" in first_bytes:
            is_html = True

        if b"<!doctype html" in first_bytes:
            is_html = True

        if is_html:
            result["status"] = (
                "authentication_or_redirect"
            )
            result["message"] = (
                "VCRM still returned HTML instead "
                "of the actual attachment."
            )
            return result

        # ---------------------------------------------------------
        # 18. SUCCESS
        # ---------------------------------------------------------

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
