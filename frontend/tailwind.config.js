/**
 * The Frappe UI design system, unmodified: surfaces, ink and outlines come
 * from the preset's semantic tokens, so the portal looks like the ERPNext the
 * customer is about to use.
 */
import frappeUIPreset from "frappe-ui/tailwind"

export default {
	presets: [frappeUIPreset],
	content: [
		"./index.html",
		"./src/**/*.{vue,js}",
		"./node_modules/frappe-ui/src/**/*.{vue,js,ts}",
	],
	plugins: [],
}
