import { call } from "frappe-ui"

const METHOD = "embark.api."

export function api(method, args = {}) {
	return call(METHOD + method, args)
}

/** The message Frappe meant for a person, without the traceback. */
export function errorText(error) {
	const messages = (error?.messages || []).filter(Boolean)
	return messages.length ? messages.join(" ") : error?.message || "Something went wrong. Please try again."
}

export function templateUrl(area, onboarding) {
	return (
		`/api/method/${METHOD}download_template?area=${encodeURIComponent(area)}` +
		`&onboarding=${encodeURIComponent(onboarding)}`
	)
}

/**
 * Upload through Frappe's own endpoint as a private file attached to the
 * onboarding. That attachment is the only place attach_file accepts a file
 * from, so one customer can never point at another's upload.
 */
export function uploadFile(file, onboarding, onProgress) {
	const form = new FormData()
	form.append("file", file, file.name)
	form.append("is_private", "1")
	form.append("doctype", "Embark Onboarding")
	form.append("docname", onboarding)

	return new Promise((resolve, reject) => {
		const xhr = new XMLHttpRequest()
		xhr.open("POST", "/api/method/upload_file")
		xhr.setRequestHeader("Accept", "application/json")
		xhr.setRequestHeader("X-Frappe-CSRF-Token", window.csrf_token)
		xhr.upload.onprogress = (e) => {
			if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100))
		}
		xhr.onload = () => {
			let body = {}
			try {
				body = JSON.parse(xhr.responseText)
			} catch {
				// A proxy error page is not JSON; fall through to the generic message.
			}
			if (xhr.status === 200 && body.message) return resolve(body.message)
			reject(new Error(serverMessage(body) || "The upload didn't go through. Please try again."))
		}
		xhr.onerror = () => reject(new Error("The upload didn't go through. Check your connection and try again."))
		xhr.send(form)
	})
}

function serverMessage(body) {
	try {
		return JSON.parse(body._server_messages)
			.map((m) => JSON.parse(m).message)
			.join(" ")
	} catch {
		return ""
	}
}
