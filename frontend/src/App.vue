<template>
	<div class="flex h-full">
		<aside
			v-if="overview && !overview.needs_start"
			class="hidden shrink-0 flex-col border-r border-outline-gray-1 bg-surface-menu-bar transition-[width] md:flex"
			:class="collapsed ? 'w-14' : 'w-64'"
		>
			<div class="flex items-center" :class="collapsed ? 'flex-col gap-1 px-2 py-3' : 'px-1 py-3'">
				<Dropdown :options="appMenu" placement="left">
					<button
						class="flex items-center gap-2.5 rounded p-2 text-left hover:bg-surface-gray-2"
						:class="collapsed ? '' : 'w-full'"
					>
						<!-- The app mark, inlined: the same artwork as the desk tile. -->
						<svg viewBox="0 0 54 54" class="size-8 shrink-0" aria-hidden="true">
							<rect width="54" height="54" rx="15.43" fill="#4F46E5" />
							<path d="M19 16h16v4.5H24v4.5h9.5v4.5H24v4.5h11V38H19z" fill="#fff" />
						</svg>
						<template v-if="!collapsed">
							<div class="min-w-0 flex-1">
								<div class="truncate text-base font-medium text-ink-gray-9">Embark</div>
								<div class="truncate text-sm text-ink-gray-5">{{ overview.client_name }}</div>
							</div>
							<FeatherIcon name="chevron-down" class="size-4 shrink-0 text-ink-gray-5" />
						</template>
					</button>
				</Dropdown>
				<Tooltip :text="collapsed ? 'Expand' : 'Collapse'" placement="right">
					<Button
						variant="ghost"
						:icon="collapsed ? 'chevrons-right' : 'chevrons-left'"
						:label="collapsed ? 'Expand sidebar' : 'Collapse sidebar'"
						@click="setCollapsed(!collapsed)"
					/>
				</Tooltip>
			</div>

			<nav class="flex-1 space-y-0.5 overflow-y-auto px-2 py-2">
				<NavLink :to="{ name: 'home' }" icon="home" label="Overview" :collapsed="collapsed" />
				<NavLink
					:to="{ name: 'interview' }"
					icon="message-square"
					label="About your business"
					:collapsed="collapsed"
					:dot="overview.interview.done ? 'Ready' : overview.interview.answered ? 'In Progress' : 'Not Started'"
				/>
				<NavLink
					:to="{ name: 'company' }"
					icon="briefcase"
					label="Company details"
					:collapsed="collapsed"
					:dot="overview.company_complete ? 'Ready' : 'Not Started'"
				/>
				<!-- The data steps are not fixed navigation: they are the plan the
				     interview produced, so they live on the Embark page itself. -->

				<div class="pt-4">
					<Tooltip :text="collapsed ? 'Ask Embark' : ''" placement="right">
						<button
							v-if="overview.assistant"
							class="flex h-8 w-full items-center gap-2 rounded text-base text-ink-gray-7 hover:bg-surface-gray-2"
							:class="[
								collapsed ? 'justify-center px-0' : 'px-2',
								state.chatOpen ? 'bg-surface-selected font-medium text-ink-gray-9 shadow-sm' : '',
							]"
							@click="state.chatOpen = !state.chatOpen"
						>
							<FeatherIcon name="message-circle" class="size-4 shrink-0 text-ink-gray-6" />
							<span v-if="!collapsed" class="flex-1 truncate text-left">Ask Embark</span>
						</button>
					</Tooltip>
					<Tooltip :text="collapsed ? 'Configure AI' : ''" placement="right">
						<button
							v-if="overview.can_configure_ai"
							class="flex h-8 w-full items-center gap-2 rounded text-base text-ink-gray-7 hover:bg-surface-gray-2"
							:class="collapsed ? 'justify-center px-0' : 'px-2'"
							@click="aiOpen = true"
						>
							<FeatherIcon name="cpu" class="size-4 shrink-0 text-ink-gray-6" />
							<span v-if="!collapsed" class="flex-1 truncate text-left">Configure AI</span>
						</button>
					</Tooltip>
				</div>
			</nav>

			<Dropdown :options="userMenu" placement="right">
				<button
					class="flex w-full items-center gap-2.5 border-t border-outline-gray-1 py-3 text-left hover:bg-surface-gray-2"
					:class="collapsed ? 'justify-center px-0' : 'px-3'"
				>
					<Avatar :label="overview.user.full_name" size="lg" />
					<template v-if="!collapsed">
						<div class="min-w-0 flex-1">
							<div class="truncate text-base text-ink-gray-8">{{ overview.user.full_name }}</div>
							<div class="truncate text-sm text-ink-gray-5">{{ overview.user.name }}</div>
						</div>
						<FeatherIcon name="chevron-up" class="size-4 shrink-0 text-ink-gray-5" />
					</template>
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
				<div class="mx-auto w-full max-w-3xl px-5 py-8">
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
import NavLink from "./components/NavLink.vue"
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
	if (route.name === "interview") return "About your business"
	if (route.name === "company") return "Company details"
	if (route.name === "area") return route.params.area
	return "Overview"
})

const aiOpen = ref(false)

// Remembered per browser, like the desk's own sidebar.
const COLLAPSED_KEY = "embark-sidebar-collapsed"
const collapsed = ref(read(COLLAPSED_KEY))

function read(key) {
	try {
		return localStorage.getItem(key) === "1"
	} catch {
		return false
	}
}

function setCollapsed(value) {
	collapsed.value = value
	try {
		localStorage.setItem(COLLAPSED_KEY, value ? "1" : "0")
	} catch {
		// A private window can refuse; the sidebar still collapses for this visit.
	}
}

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
