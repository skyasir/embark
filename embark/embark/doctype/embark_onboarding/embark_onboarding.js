// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

const API = "embark.api";

frappe.ui.form.on("Embark Onboarding", {
	refresh(frm) {
		// A customer with desk access can open this form too; the actions are the consultant's.
		if (frm.is_new() || !frappe.user.has_role("System Manager")) return;

		frm.dashboard.add_progress(__("Readiness"), frm.doc.readiness || 0);

		frm.add_custom_button(__("Open Portal"), () => {
			window.open(`/embark?id=${encodeURIComponent(frm.doc.name)}`);
		});

		if ((frm.doc.areas || []).some((row) => row.upload)) {
			frm.add_custom_button(__("Download Prepared Data"), () => {
				window.open(
					`/api/method/${API}.download_prepared_data?onboarding=${encodeURIComponent(frm.doc.name)}`
				);
			});
		}

		if (frm.doc.status === "Submitted") {
			frm.add_custom_button(__("Approve"), () => review(frm, "Approved"), __("Review"));
			frm.add_custom_button(__("Return to Customer"), () => review(frm, "Returned"), __("Review"));
		}
	},
});

function review(frm, decision) {
	const returning = decision === "Returned";
	const d = new frappe.ui.Dialog({
		title: returning ? __("Return to Customer") : __("Approve"),
		fields: returning
			? [
					{
						fieldname: "notes",
						fieldtype: "Small Text",
						label: __("What should they fix?"),
						reqd: 1,
						default: frm.doc.review_notes,
					},
			  ]
			: [
					{
						fieldname: "info",
						fieldtype: "HTML",
						options: `<p>${__("The data is ready for implementation.")}</p>`,
					},
			  ],
		primary_action_label: returning ? __("Return") : __("Approve"),
		primary_action(values) {
			frappe.call({
				method: `${API}.review`,
				args: { onboarding: frm.doc.name, decision, notes: values.notes },
				freeze: true,
				callback() {
					d.hide();
					frm.reload_doc();
				},
			});
		},
	});
	d.show();
}
