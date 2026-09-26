// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

const API = "embark.api";

frappe.ui.form.on("Embark Onboarding", {
	setup(frm) {
		frm.set_query("package", () => ({ filters: { is_active: 1 } }));
	},

	refresh(frm) {
		// A customer with desk access can open this form too; the actions are the consultant's.
		if (frm.is_new() || !frappe.user.has_role(["System Manager", "Embark Consultant"])) return;

		frm.dashboard.add_progress(__("Readiness"), frm.doc.readiness || 0);

		frm.add_custom_button(__("Open Portal"), () => {
			window.open(`/embark?id=${encodeURIComponent(frm.doc.name)}`);
		});
		frm.add_custom_button(__("Invite Customer"), () => invite(frm));

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

function invite(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Invite Customer"),
		fields: [
			{ fieldname: "email", fieldtype: "Data", options: "Email", label: __("Email"), reqd: 1 },
			{ fieldname: "first_name", fieldtype: "Data", label: __("First Name"), reqd: 1 },
			{ fieldname: "last_name", fieldtype: "Data", label: __("Last Name") },
			{
				fieldname: "desk_access",
				fieldtype: "Check",
				label: __("Also give desk access"),
				description: __("Their package's ERPNext roles, never System Manager. They still land in Embark."),
			},
			{
				fieldname: "send_email",
				fieldtype: "Check",
				label: __("Email them the login link"),
				default: 1,
				description: __("Untick to get a link you can share yourself."),
			},
		],
		primary_action_label: __("Invite"),
		primary_action(values) {
			frappe.call({
				method: `${API}.invite_customer`,
				args: { onboarding: frm.doc.name, ...values },
				freeze: true,
				callback({ message }) {
					d.hide();
					frm.reload_doc();
					if (message.emailed) {
						frappe.show_alert({ message: __("Invitation sent to {0}", [message.user]), indicator: "green" });
					} else {
						frappe.msgprint({
							title: __("Share this link"),
							message: __("{0} can set their password here:<br><br><code>{1}</code>", [
								frappe.utils.escape_html(message.user),
								frappe.utils.escape_html(message.setup_link),
							]),
						});
					}
				},
			});
		},
	});
	d.show();
}

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
