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
    try:
        url = (
            "https://crm.btpl.net/index.php"
            "?module=Documents"
            "&action=DownloadFile"
            "&record=" + str(document_id)
            + "&fileid=" + str(file_id)
            + "&folderid=" + str(folder_id)
            + "&name=" + frappe.utils.quote(str(file_name))
        )

        print("========================================")
        print("VCRM ATTACHMENT DOWNLOAD")
        print("URL:", url)
        print("Document ID:", document_id)
        print("File ID:", file_id)
        print("Folder ID:", folder_id)
        print("========================================")

        response = requests.get(
            url,
            verify=False,
            timeout=60,
            allow_redirects=True
        )

        print("HTTP STATUS:", response.status_code)
        print("CONTENT TYPE:", response.headers.get("Content-Type"))
        print("CONTENT LENGTH:", len(response.content))
        print("FINAL URL:", response.url)

        if response.status_code != 200:
            return {
                "success": False,
                "status": "download_failed",
                "message": (
                    "VCRM attachment download failed. "
                    "HTTP Status: "
                    + str(response.status_code)
                ),
                "status_code": response.status_code
            }

        if not response.content:
            return {
                "success": False,
                "status": "empty_attachment",
                "message": "VCRM returned empty attachment content."
            }

        file_content = base64.b64encode(
            response.content
        ).decode("ascii")

        return {
            "success": True,
            "status": "downloaded",
            "file_name": str(file_name),
            "content_type": (
                response.headers.get("Content-Type")
                or "application/octet-stream"
            ),
            "file_size": len(response.content),
            "file_content": file_content
        }

    except Exception as e:
        print("VCRM ATTACHMENT ERROR:", str(e))

        return {
            "success": False,
            "status": "exception",
            "message": str(e)
        }
