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
    """
    Download an internal VCRM Document attachment.

    This method:
    1. Builds the VCRM DownloadFile URL.
    2. Connects to VCRM with SSL verification disabled because
       the current VCRM server uses a self-signed certificate.
    3. Follows redirects.
    4. Verifies that VCRM returned a real file instead of HTML.
    5. Converts the binary file to Base64.
    6. Returns the file content to the BCRM import process.

    This is extension-independent.
    """

    try:
        # ---------------------------------------------------------
        # Basic validation
        # ---------------------------------------------------------

        document_id = str(document_id or "").strip()
        file_id = str(file_id or "").strip()
        folder_id = str(folder_id or "").strip()
        file_name = str(file_name or "").strip()

        if not document_id:
            return {
                "success": False,
                "status": "missing_document_id",
                "message": "VCRM document ID is required."
            }

        if not file_id:
            return {
                "success": False,
                "status": "missing_file_id",
                "message": "VCRM attachment file ID is required."
            }

        if not folder_id:
            return {
                "success": False,
                "status": "missing_folder_id",
                "message": "VCRM folder ID is required."
            }

        if not file_name:
            return {
                "success": False,
                "status": "missing_file_name",
                "message": "VCRM file name is required."
            }

        # ---------------------------------------------------------
        # Build VCRM DownloadFile URL
        # ---------------------------------------------------------

        url = (
            "https://crm.btpl.net/index.php"
            "?module=Documents"
            "&action=DownloadFile"
            "&record=" + document_id
            + "&fileid=" + file_id
            + "&folderid=" + folder_id
            + "&name=" + frappe.utils.quote(file_name)
        )

        print("========================================")
        print("VCRM ATTACHMENT DOWNLOAD")
        print("========================================")
        print("Document ID:", document_id)
        print("File ID:", file_id)
        print("Folder ID:", folder_id)
        print("File Name:", file_name)
        print("URL:", url)
        print("========================================")

        # ---------------------------------------------------------
        # Download from VCRM
        # ---------------------------------------------------------
        #
        # VCRM currently has a self-signed SSL certificate.
        # Therefore verify=False is intentionally used here.
        #
        # This is inside the custom Python app, NOT a Server Script.
        # ---------------------------------------------------------

        response = requests.get(
            url,
            verify=False,
            timeout=60,
            allow_redirects=True,
            headers={
                "Accept": "*/*",
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/153.0 Safari/537.36"
                )
            }
        )

        status_code = response.status_code
        content_type = (
            response.headers.get("Content-Type")
            or ""
        ).lower()

        content_length = len(response.content)

        final_url = str(response.url or "")

        print("HTTP STATUS:", status_code)
        print("CONTENT TYPE:", content_type)
        print("CONTENT LENGTH:", content_length)
        print("FINAL URL:", final_url)

        # ---------------------------------------------------------
        # HTTP status validation
        # ---------------------------------------------------------

        if status_code != 200:
            print(
                "VCRM DOWNLOAD FAILED - HTTP:",
                status_code
            )

            return {
                "success": False,
                "status": "download_failed",
                "message": (
                    "VCRM attachment download failed. "
                    "HTTP Status: "
                    + str(status_code)
                ),
                "status_code": status_code,
                "content_type": content_type,
                "final_url": final_url
            }

        # ---------------------------------------------------------
        # Empty response validation
        # ---------------------------------------------------------

        if not response.content:
            print("VCRM returned empty content.")

            return {
                "success": False,
                "status": "empty_attachment",
                "message": (
                    "VCRM returned empty attachment content."
                ),
                "status_code": status_code,
                "content_type": content_type,
                "final_url": final_url
            }

        # ---------------------------------------------------------
        # IMPORTANT:
        # Detect HTML/login page
        # ---------------------------------------------------------
        #
        # HTTP 200 does NOT always mean the actual file was returned.
        # VCRM may return a login page as HTML.
        #
        # We must never save that HTML page as a BCRM File.
        # ---------------------------------------------------------

        if "text/html" in content_type:

            print(
                "VCRM returned HTML instead of attachment."
            )

            return {
                "success": False,
                "status": "authentication_or_redirect",
                "message": (
                    "VCRM returned HTML instead of the actual "
                    "attachment. The VCRM download endpoint "
                    "may require an authenticated VCRM session."
                ),
                "status_code": status_code,
                "content_type": content_type,
                "content_size": content_length,
                "final_url": final_url
            }

        # ---------------------------------------------------------
        # Get original content type
        # ---------------------------------------------------------

        original_content_type = (
            response.headers.get("Content-Type")
            or "application/octet-stream"
        )

        # Remove optional charset information
        if ";" in original_content_type:
            original_content_type = (
                original_content_type.split(";")[0].strip()
            )

        # ---------------------------------------------------------
        # Convert binary → Base64
        # ---------------------------------------------------------

        file_content = base64.b64encode(
            response.content
        ).decode("ascii")

        print("========================================")
        print("VCRM ATTACHMENT SUCCESS")
        print("========================================")
        print("File Name:", file_name)
        print("Content Type:", original_content_type)
        print("File Size:", content_length)
        print("Base64 Size:", len(file_content))
        print("========================================")

        # ---------------------------------------------------------
        # Return result
        # ---------------------------------------------------------

        return {
            "success": True,
            "status": "downloaded",

            "file_name": file_name,

            "content_type": original_content_type,

            "file_size": content_length,

            "file_content": file_content,

            "document_id": document_id,

            "file_id": file_id,

            "folder_id": folder_id,

            "final_url": final_url
        }

    except requests.exceptions.Timeout as e:

        print(
            "VCRM ATTACHMENT TIMEOUT:",
            str(e)
        )

        return {
            "success": False,
            "status": "timeout",
            "message": (
                "VCRM attachment download timed out."
            ),
            "error": str(e)
        }

    except requests.exceptions.SSLError as e:

        print(
            "VCRM ATTACHMENT SSL ERROR:",
            str(e)
        )

        return {
            "success": False,
            "status": "ssl_error",
            "message": (
                "VCRM SSL connection failed."
            ),
            "error": str(e)
        }

    except requests.exceptions.RequestException as e:

        print(
            "VCRM ATTACHMENT REQUEST ERROR:",
            str(e)
        )

        return {
            "success": False,
            "status": "request_error",
            "message": (
                "VCRM attachment request failed."
            ),
            "error": str(e)
        }

    except Exception as e:

        print(
            "VCRM ATTACHMENT ERROR:",
            str(e)
        )

        return {
            "success": False,
            "status": "exception",
            "message": str(e)
        }
