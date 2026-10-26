import json

import frappe
from frappe import _
from frappe.utils import get_link_to_form


@frappe.whitelist()
def create_interview_feedback(
    data: str | dict,
    interview_name: str,
    interviewer: str,
    job_applicant: str,
):
    if isinstance(data, str):
        data = frappe._dict(json.loads(data))
    elif isinstance(data, dict):
        data = frappe._dict(data)

    if frappe.session.user != interviewer:
        frappe.throw(
            _("Only Interviewer Are allowed to submit Interview Feedback")
        )

    guest_name = (data.get("custom_guest_name") or "").strip()

    if interviewer == "guest@brillianttechnologies.in" and not guest_name:
        frappe.throw(
            _("Please enter Guest Name before submitting feedback.")
        )

    interview_feedback = frappe.new_doc("Interview Feedback")
    interview_feedback.interview = interview_name
    interview_feedback.interviewer = interviewer
    interview_feedback.job_applicant = job_applicant

    for row in data.skill_set:
        interview_feedback.append("skill_assessment", frappe._dict(row))

    interview_feedback.feedback = data.get("feedback")
    interview_feedback.result = data.get("result")
    interview_feedback.custom_guest_name = guest_name or data.get(
        "custom_guest_name"
    )

    interview_feedback.save()
    interview_feedback.submit()

    frappe.msgprint(
        _("Interview Feedback {0} submitted successfully").format(
            get_link_to_form("Interview Feedback", interview_feedback.name)
        )
    )
