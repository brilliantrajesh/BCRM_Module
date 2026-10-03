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
        # SETTINGS
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
            result["message"] = "VCRM username is missing."
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
            result["message"] = "VCRM password is empty."
            return result

        # =========================================================
        # VCRM WEB URL
        # =========================================================

        vcrm_url = "https://crm.btpl.net"

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
        # STEP 1
        # OPEN LOGIN PAGE
        # =========================================================

        login_page_url = (
            vcrm_url
            + "/index.php"
        )

        try:
            login_page = session.get(
                login_page_url,
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
                "Could not open VCRM login page."
            )
            result["login_page_error"] = str(e)
            return result

        # =========================================================
        # STEP 2
        # ACTUAL AUTHENTICATION
        #
        # IMPORTANT:
        # Login.php = login page
        # Authenticate.php = authentication
        # =========================================================

        authenticate_url = (
            vcrm_url
            + "/index.php"
        )

        login_data = {
            "module": "Users",
            "action": "Authenticate",
            "username": username,
            "user_name": username,
            "login_user_name": username,
            "user_password": password,
            "login_password": password,
            "Login": "Login"
        }

        try:
            auth_response = session.post(
                authenticate_url,
                data=login_data,
                headers={
                    "Referer": login_page.url
                },
                verify=False,
                timeout=30,
                allow_redirects=False
            )

            result["login_status_code"] = (
                auth_response.status_code
            )

            result["login_location"] = (
                auth_response.headers.get(
                    "Location",
                    ""
                )
            )

        except Exception as e:
            result["status"] = "authentication_request_failed"
            result["message"] = (
                "VCRM authentication request failed."
            )
            result["login_error"] = str(e)
            return result

        # =========================================================
        # STEP 3
        # SESSION COOKIE
        # =========================================================

        try:
            result["session_cookie_count"] = len(
                session.cookies
            )
        except Exception:
            result["session_cookie_count"] = 0

        # =========================================================
        # STEP 4
        # FOLLOW AUTH REDIRECT
        # =========================================================

        location = (
            auth_response.headers.get(
                "Location",
                ""
            )
            or ""
        ).strip()

        if location:
            if location.startswith("http"):
                next_url = location
            elif location.startswith("/"):
                next_url = (
                    vcrm_url
                    + location
                )
            else:
                next_url = (
                    vcrm_url
                    + "/"
                    + location
                )
        else:
            next_url = (
                vcrm_url
                + "/index.php"
            )

        try:
            home_response = session.get(
                next_url,
                verify=False,
                timeout=30,
                allow_redirects=True
            )

            result["login_final_url"] = (
                str(home_response.url or "")
            )

            result["login_final_status"] = (
                home_response.status_code
            )

        except Exception as e:
            result["status"] = "post_login_request_failed"
            result["message"] = (
                "VCRM session was created but "
                "post-login page could not be opened."
            )
            result["post_login_error"] = str(e)
            return result

        # =========================================================
        # STEP 5
        # CHECK WHETHER STILL LOGIN PAGE
        # =========================================================

        home_html = (
            home_response.text
            if home_response.text
            else ""
        )

        home_lower = home_html.lower()

        still_login = False

        if (
            "login_user_name" in home_lower
            and "login_password" in home_lower
        ):
            still_login = True

        if (
            "error=login"
            in str(home_response.url or "").lower()
        ):
            still_login = True

        if still_login:
            result["status"] = "vcrm_login_failed"
            result["message"] = (
                "VCRM rejected the web authentication. "
                "The session is not authenticated."
            )
            return result

        # =========================================================
        # STEP 6
        # OPEN DOCUMENT
        # =========================================================

        detail_url = (
            vcrm_url
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
                "Could not open VCRM document."
            )
            result["detail_error"] = str(e)
            return result

        detail_html = (
            detail_response.text
            if detail_response.text
            else ""
        )

        detail_lower = detail_html.lower()

        if (
            "login_user_name" in detail_lower
            and "login_password" in detail_lower
        ):
            result["status"] = "session_not_authenticated"
            result["message"] = (
                "VCRM redirected to login after authentication."
            )
            return result

        # =========================================================
        # STEP 7
        # ACTUAL DOWNLOAD
        #
        # CONFIRMED:
        # document_id = 33
        # file_id     = 34
        # folder_id   = not required
        # =========================================================

        download_url = (
            vcrm_url
            + "/index.php"
        )

        download_params = {
            "module": "Documents",
            "action": "DownloadFile",
            "record": str(document_id),
            "fileid": str(file_id)
        }

        if folder_id:
            download_params["folderid"] = str(folder_id)

        download_params["name"] = str(file_name)

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
        # STEP 8
        # RESPONSE
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
        # STEP 9
        # CHECK HTTP
        # =========================================================

        if download_response.status_code != 200:
            result["status"] = "download_failed"
            result["message"] = (
                "VCRM returned HTTP "
                + str(download_response.status_code)
                + "."
            )
            return result

        if not download_response.content:
            result["status"] = "empty_attachment"
            result["message"] = (
                "VCRM returned an empty attachment."
            )
            return result

        # =========================================================
        # STEP 10
        # HTML CHECK
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
        # SUCCESS
        # =========================================================

        result["success"] = True
        result["status"] = "success"
        result["message"] = (
            "VCRM attachment downloaded successfully."
        )

        result["file_content"] = (
            base64.b64encode(
                download_response.content
            ).decode("ascii")
        )

        return result

    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)
        return result
