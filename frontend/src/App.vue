<template>
	<div class="flex h-full">
		<!-- A rail, not a sidebar: icons only, so the three panes beside it get
		     the width they need. Every destination keeps its name on hover. -->
		<aside
			v-if="overview && !overview.needs_start"
			class="hidden w-[76px] shrink-0 flex-col items-center border-r border-outline-gray-1 bg-surface-menu-bar py-3 md:flex"
		>
			<Dropdown :options="appMenu" placement="right">
				<button class="rounded-lg p-1 transition-colors hover:bg-surface-gray-2" aria-label="Embark">
					<svg viewBox="0 0 54 54" class="size-9" aria-hidden="true">
						<defs>
							<linearGradient id="embarkTile" x1="0" y1="0" x2="1" y2="1">
								<stop offset="0" stop-color="#6366F1" />
								<stop offset="1" stop-color="#4338CA" />
							</linearGradient>
						</defs>
						<rect width="54" height="54" rx="15.43" fill="url(#embarkTile)" />
						<path
							d="M16.65 15.55a2.9 2.9 0 0 1 2.9-2.9h14.7a2.9 2.9 0 1 1 0 5.8H22.45v6.7h9.5a2.9 2.9 0 1 1 0 5.8h-9.5v6.7h11.8a2.9 2.9 0 1 1 0 5.8H19.55a2.9 2.9 0 0 1-2.9-2.9z"
							fill="#fff"
						/>
					</svg>
				</button>
			</Dropdown>

			<nav class="mt-6 flex flex-1 flex-col items-center gap-1">
				<RailLink :to="{ name: 'home' }" icon="home" label="Overview" />
				<RailLink :to="{ name: 'setup' }" icon="sliders" label="Setup" />
				<RailLink
					:to="{ name: 'company' }"
					icon="briefcase"
					label="Company"
					:dot="overview.company_complete ? '' : 'todo'"
				/>

				<button
					v-if="overview.assistant"
					class="group mt-2 flex w-16 flex-col items-center gap-1 rounded-lg py-2 text-ink-gray-5 transition-colors hover:bg-surface-gray-2 hover:text-ink-gray-8"
					@click="state.chatOpen = !state.chatOpen"
				>
					<FeatherIcon name="message-circle" class="size-5" />
					<span class="text-[11px] leading-none">Ask</span>
				</button>
				<button
					v-if="overview.can_configure_ai"
					class="flex w-16 flex-col items-center gap-1 rounded-lg py-2 text-ink-gray-5 transition-colors hover:bg-surface-gray-2 hover:text-ink-gray-8"
					@click="aiOpen = true"
				>
					<FeatherIcon name="cpu" class="size-5" />
					<span class="text-[11px] leading-none">AI</span>
				</button>
			</nav>

			<Tooltip :text="isDark ? 'Switch to light' : 'Switch to dark'" placement="right">
				<button
					class="flex size-9 items-center justify-center rounded-lg text-ink-gray-5 transition-colors hover:bg-surface-gray-2 hover:text-ink-gray-8"
					:aria-label="isDark ? 'Switch to light theme' : 'Switch to dark theme'"
					@click="setTheme(isDark ? 'light' : 'dark')"
				>
					<FeatherIcon :name="isDark ? 'sun' : 'moon'" class="size-4" />
				</button>
			</Tooltip>

			<Dropdown :options="userMenu" placement="right">
				<button class="mt-2 rounded-full" :aria-label="overview.user.full_name">
					<Avatar :label="overview.user.full_name" size="lg" />
				</button>
			</Dropdown>
		</aside>

		<Assistant />

		<div class="flex min-w-0 flex-1 flex-col">
			<header class="flex h-12 shrink-0 items-center gap-2 border-b border-outline-gray-1 px-5 text-base">
				<router-link :to="{ name: 'home' }" class="text-ink-gray-5 hover:text-ink-gray-8" aria-label="Overview">
					<FeatherIcon name="home" class="size-4" />
				</router-link>
				<span class="text-ink-gray-4">/</span>
				<span class="truncate font-medium text-ink-gray-9">{{ title }}</span>
				<!-- The sidebar, and its user menu, is hidden on phones. -->
				<a v-if="overview?.can_use_desk" href="/app" class="ml-auto text-sm text-ink-gray-6 hover:text-ink-gray-9 md:hidden">Desk</a>
				<Button v-if="overview" :class="overview?.can_use_desk ? '' : 'ml-auto'" class="md:hidden" variant="ghost" icon="log-out" label="Log out" @click="logout" />
			</header>

			<main class="flex-1 overflow-y-auto">
				<!-- The wizard lays out its own three columns and needs the whole
				     width; everything else reads better in a column. -->
				<div
					class="mx-auto w-full px-5 py-8"
					:class="wide ? 'h-full max-w-none' : 'max-w-3xl'"
				>
					<div v-if="state.loading" class="flex justify-center py-24">
						<LoadingIndicator class="size-6 text-ink-gray-5" />
					</div>
					<Callout v-else-if="state.error" tone="error">{{ state.error }}</Callout>
					<router-view v-else />
				</div>
			</main>
		</div>
	</div>
	<AiSettings v-model="aiOpen" />
	<Toast />
</template>

<script setup>
import { computed, onMounted, ref, watchEffect } from "vue"
import { useRoute, useRouter } from "vue-router"
import { Avatar, Button, Dropdown, FeatherIcon, LoadingIndicator, Toast, Tooltip, call } from "frappe-ui"

import AiSettings from "./components/AiSettings.vue"
import Assistant from "./components/Assistant.vue"
import Callout from "./components/Callout.vue"
import RailLink from "./components/RailLink.vue"
import { loadOverview, state } from "./data/store"
import { applyTheme, setTheme, theme, watchSystemTheme } from "./data/theme"

const route = useRoute()
const router = useRouter()
const overview = computed(() => state.overview)

// Until the consultant starts the onboarding there is nothing but the start screen.
watchEffect(() => {
	if (overview.value?.needs_start && route.name && route.name !== "home") router.replace({ name: "home" })
})

const title = computed(() => {
	if (route.name === "setup") return "Setup Wizard"
	if (route.name === "company") return "Company details"
	if (route.name === "area") return route.params.area
	return "Overview"
})

// The screens that lay out their own columns need the whole width.
const wide = computed(() => ["setup", "home"].includes(route.name))

const aiOpen = ref(false)

const appMenu = computed(() => [
	...(overview.value?.assistant
		? [
				{
					label: state.chatOpen ? "Hide the chat" : "Ask Embark",
					icon: "message-circle",
					onClick: () => (state.chatOpen = !state.chatOpen),
				},
			]
		: []),
	...(overview.value?.can_configure_ai
		? [{ label: "Configure AI", icon: "cpu", onClick: () => (aiOpen.value = true) }]
		: []),
	...(overview.value?.can_use_desk
		? [{ label: "Switch to Desk", icon: "grid", onClick: () => (window.location.href = "/app") }]
		: []),
])

const themeMenu = computed(() =>
	[
		{ label: "System theme", value: "system", icon: "monitor" },
		{ label: "Light", value: "light", icon: "sun" },
		{ label: "Dark", value: "dark", icon: "moon" },
	].map((choice) => ({
		label: theme.value === choice.value ? `${choice.label} ✓` : choice.label,
		icon: choice.icon,
		onClick: () => setTheme(choice.value),
	}))
)

const userMenu = computed(() => [
	...(overview.value?.can_use_desk
		? [{ label: "Switch to Desk", icon: "grid", onClick: () => (window.location.href = "/app") }]
		: []),
	...themeMenu.value,
	{ label: "Log out", icon: "log-out", onClick: logout },
])

// The tab reads "Items · Embark", so a customer with several tabs open can find it.
watchEffect(() => {
	document.title = route.name === "home" ? "Embark" : `${title.value} · Embark`
})

async function logout() {
	try {
		await call("logout")
	} finally {
		window.location.href = "/login"
	}
}

onMounted(() => {
	applyTheme()
	watchSystemTheme()
	loadOverview()
})
</script>
