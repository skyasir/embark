import { reactive } from "vue"
import { api, errorText } from "./api"

export const state = reactive({
	id: null,
	overview: null,
	loading: true,
	error: null,
	// The last login link a consultant created, shown until the page is left.
	invite: null,
})

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
