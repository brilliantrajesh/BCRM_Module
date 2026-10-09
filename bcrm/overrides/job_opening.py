from hrms.hr.doctype.job_opening.job_opening import JobOpening as HRMSJobOpening


class BCRMJobOpening(HRMSJobOpening):
    website = HRMSJobOpening.website.copy()
    website.template = "templates/generators/job_opening.html"
