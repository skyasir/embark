/**
 * Embark's own toasts.
 *
 * frappe-ui has toasts, and a provider that renders them, but the package
 * does not export that provider — so every `toast.error(...)` in this app
 * wrote into a store nothing was listening to, and every failure since the
 * portal was built has been silent. A button that fails without saying so
 * reads as a broken button.
 *
 * This is the whole thing: a list, three ways to add to it, and a component
 * that draws it. Nothing to go stale when the library moves.
 */
import { reactive } from "vue"

export const toasts = reactive([])

let last = 0

function show(message, tone) {
	const text = String(message || "").trim()
	if (!text) return
	const id = ++last
	toasts.push({ id, text, tone })
	// Long enough to read a sentence, short enough not to sit in the way.
	setTimeout(() => dismiss(id), tone === "error" ? 8000 : 4000)
	return id
}

export function dismiss(id) {
	const at = toasts.findIndex((t) => t.id === id)
	if (at >= 0) toasts.splice(at, 1)
}

export const toast = {
	success: (message) => show(message, "success"),
	error: (message) => show(message, "error"),
	warning: (message) => show(message, "warning"),
	info: (message) => show(message, "info"),
	create: ({ message, type } = {}) => show(message, type || "info"),
}
