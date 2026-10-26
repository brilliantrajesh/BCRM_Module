frappe.ui.form.on("Interview", {
    show_feedback_dialog: async function (frm, data) {
        const is_guest = frappe.session.user === "guest@brillianttechnologies.in";
        const fields = await frm.events.get_fields_for_feedback();

        const dialog_fields = [];

        if (is_guest) {
            dialog_fields.push({
                fieldname: "custom_guest_name",
                fieldtype: "Data",
                label: __("Guest Name"),
                reqd: 1,
            });
        }

        dialog_fields.push(
            {
                fieldname: "skill_set",
                fieldtype: "Table",
                label: __("Skill Assessment"),
                cannot_add_rows: false,
                in_editable_grid: true,
                reqd: 1,
                fields: fields,
                data: data,
            },
            {
                fieldname: "result",
                fieldtype: "Select",
                options: ["", "Cleared", "Rejected"],
                label: __("Result"),
                reqd: 1,
            },
            {
                fieldname: "feedback",
                fieldtype: "Small Text",
                label: __("Feedback"),
            }
        );

        const d = new frappe.ui.Dialog({
            title: __("Submit Feedback"),
            fields: dialog_fields,
            size: "large",
            minimizable: true,
            static: true,

            primary_action: function (values) {
                if (is_guest) {
                    values.custom_guest_name =
                        (values.custom_guest_name || "").trim();

                    if (!values.custom_guest_name) {
                        frappe.msgprint({
                            title: __("Guest Name Required"),
                            message: __(
                                "Please enter Guest Name before submitting feedback."
                            ),
                            indicator: "red",
                        });

                        d.fields_dict.custom_guest_name.set_focus();
                        return;
                    }
                }

                frappe.call({
                    method: "bcrm.api.interview_feedback.create_interview_feedback",
                    args: {
                        data: values,
                        interview_name: frm.doc.name,
                        interviewer: frappe.session.user,
                        job_applicant: frm.doc.job_applicant,
                    },
                }).then(() => {
                    frm.refresh();
                });

                d.hide();
            },
        });

        d.show();
        d.get_close_btn().show();
    },
});
