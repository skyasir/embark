/**
 * Light, dark, or whatever the machine is set to — the same three choices as
 * the desk, stored the same way (`data-theme` on <html>, remembered per
 * browser), so the portal follows the ERPNext beside it.
 */
import { ref } from "vue"

const KEY = "embark-theme"
const CHOICES = ["system", "light", "dark"]

export const theme = ref(read())

function read() {
	try {
		const saved = localStorage.getItem(KEY)
		return CHOICES.includes(saved) ? saved : "system"
	} catch {
		return "system"
	}
}

function systemIsDark() {
	return window.matchMedia?.("(prefers-color-scheme: dark)").matches
}

export function applyTheme() {
	const dark = theme.value === "dark" || (theme.value === "system" && systemIsDark())
	document.documentElement.setAttribute("data-theme", dark ? "dark" : "light")
}

export function setTheme(choice) {
	theme.value = CHOICES.includes(choice) ? choice : "system"
	try {
		localStorage.setItem(KEY, theme.value)
	} catch {
		// A private window can refuse; the choice still holds for this visit.
	}
	applyTheme()
}

export function watchSystemTheme() {
	window
		.matchMedia?.("(prefers-color-scheme: dark)")
		.addEventListener("change", () => theme.value === "system" && applyTheme())
}
