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
						<rect width="54" height="54" rx="15.43" fill="#1668E3" />
						<g transform="translate(13 12) scale(0.52)">
							<path d="M0 0h10v56H0z" fill="#fff" />
							<path d="M6 0h44l-8 13H6z" fill="#fff" />
							<path d="M6 20h32l8 8-8 8H6z" fill="#BBD9FF" />
							<path d="M6 43h44l-8 13H6z" fill="#fff" />
						</g>
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

				<RailLink :to="{ name: 'ask' }" icon="message-circle" label="Ask" />
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
	if (route.name === "ask") return "Ask Embark"
	if (route.name === "area") return route.params.area
	return "Overview"
})

// The screens that lay out their own columns need the whole width.
const wide = computed(() => ["setup", "home", "ask"].includes(route.name))

const aiOpen = ref(false)

const appMenu = computed(() => [
	...(overview.value?.assistant
		? [{ label: "Ask Embark", icon: "message-circle", onClick: () => router.push({ name: "ask" }) }]
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
