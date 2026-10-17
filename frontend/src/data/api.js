import { call } from "frappe-ui"

const METHOD = "embark.api."

export function api(method, args = {}) {
	return call(METHOD + method, args)
}

/** A whitelisted method outside embark.api, called by its full path. */
export function callMethod(method, args = {}) {
	return call(method, args)
}

/** The message Frappe meant for a person, without the traceback. */
export function errorText(error) {
	const messages = (error?.messages || []).filter(Boolean)
	return messages.length ? messages.join(" ") : error?.message || "Something went wrong. Please try again."
}

/**
 * A whitelisted method that answers with server-sent events, read piece by
 * piece. `call` cannot do this — it waits for the whole body — so this is a
 * plain fetch with Frappe's CSRF token, which is what `call` sends too.
 *
 * `onPiece` is given each piece as it lands; the promise settles when the
 * stream ends.
 */
export async function stream(method, args, onPiece) {
	const response = await fetch(`/api/method/${METHOD}${method}`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			// The same guard frappe-ui uses: on a page served without a
			// session the placeholder is still sitting there unrendered.
			"X-Frappe-CSRF-Token":
				window.csrf_token && window.csrf_token !== "{{ csrf_token }}" ? window.csrf_token : "",
		},
		body: JSON.stringify(args),
	})
	if (!response.ok || !response.body) throw new Error(`${response.status} ${response.statusText}`)

	const reader = response.body.getReader()
	const decoder = new TextDecoder()
	let buffer = ""
	for (;;) {
		const { done, value } = await reader.read()
		if (done) break
		buffer += decoder.decode(value, { stream: true })
		// One event per blank line; a half-arrived one waits for the rest.
		const events = buffer.split("\n\n")
		buffer = events.pop() || ""
		for (const event of events) {
			const line = event.split("\n").find((l) => l.startsWith("data:"))
			if (!line) continue
			try {
				const data = JSON.parse(line.slice(5))
				if (data.done) return data
				if (data.text) onPiece(data.text)
			} catch {
				// A piece that is not JSON is not a piece of the answer.
			}
		}
	}
	return { done: true }
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
