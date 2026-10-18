import { reactive } from "vue"
import { api, errorText } from "./api"

export const state = reactive({
	id: null,
	overview: null,
	loading: true,
	error: null,
	// Where the live ERPNext pane is looking. `seq` goes up on every nudge,
	// so asking for the page it is already on still reloads it — which is the
	// usual case, because a list does not change its address when a row lands
	// in it.
	site: { path: "/app", seq: 0 },
})

/** Point the live pane at something, or just make it look again. */
export function showInErpnext(path) {
	state.site = { path: path || state.site.path, seq: state.site.seq + 1 }
}

const KEY = "embark-onboarding-id"

export function rememberOnboarding(id) {
	try {
		if (id) sessionStorage.setItem(KEY, id)
		state.id = id || sessionStorage.getItem(KEY)
	} catch {
		state.id = id
	}
}

export async function loadOverview() {
	try {
		setOverview(await api("get_overview", state.id ? { onboarding: state.id } : {}))
		state.error = null
	} catch (e) {
		state.error = errorText(e)
	} finally {
		state.loading = false
	}
}

export function setOverview(overview) {
	state.overview = overview
	state.id = overview.name
}
