<template>
	<div class="flex h-full">
		<aside
			v-if="overview && !overview.needs_start"
			class="hidden w-64 shrink-0 flex-col border-r border-outline-gray-1 bg-surface-menu-bar md:flex"
		>
			<Dropdown :options="appMenu" placement="left">
				<button class="flex w-full items-center gap-2.5 px-3 py-3 text-left hover:bg-surface-gray-2">
					<!-- The app mark, inlined: the same artwork as the desk tile. -->
					<svg viewBox="0 0 54 54" class="size-8 shrink-0" aria-hidden="true">
						<rect width="54" height="54" rx="15.43" fill="#4F46E5" />
						<path d="M19 16h16v4.5H24v4.5h9.5v4.5H24v4.5h11V38H19z" fill="#fff" />
					</svg>
					<div class="min-w-0 flex-1">
						<div class="truncate text-base font-medium text-ink-gray-9">Embark</div>
						<div class="truncate text-sm text-ink-gray-5">{{ overview.client_name }}</div>
					</div>
					<FeatherIcon name="chevron-down" class="size-4 shrink-0 text-ink-gray-5" />
				</button>
			</Dropdown>

			<nav class="flex-1 space-y-0.5 overflow-y-auto px-2 py-2">
				<NavLink :to="{ name: 'home' }" icon="home" label="Overview" />
				<NavLink
					:to="{ name: 'interview' }"
					icon="message-square"
					label="About your business"
					:dot="overview.interview.done ? 'Ready' : overview.interview.answered ? 'In Progress' : 'Not Started'"
				/>
				<NavLink
					:to="{ name: 'company' }"
					icon="briefcase"
					label="Company details"
					:dot="overview.company_complete ? 'Ready' : 'Not Started'"
				/>
				<!-- The data steps are not fixed navigation: they are the plan the
				     interview produced, so they live on the Embark page itself. -->

				<div class="pt-4">
					<button
						v-if="overview.assistant"
						class="flex h-8 w-full items-center gap-2 rounded px-2 text-base text-ink-gray-7 hover:bg-surface-gray-2"
						:class="state.chatOpen ? 'bg-surface-selected font-medium text-ink-gray-9 shadow-sm' : ''"
						@click="state.chatOpen = !state.chatOpen"
					>
						<FeatherIcon name="message-circle" class="size-4 shrink-0 text-ink-gray-6" />
						<span class="flex-1 truncate text-left">Ask Embark</span>
					</button>
					<button
						v-if="overview.is_staff"
						class="flex h-8 w-full items-center gap-2 rounded px-2 text-base text-ink-gray-7 hover:bg-surface-gray-2"
						@click="aiOpen = true"
					>
						<FeatherIcon name="cpu" class="size-4 shrink-0 text-ink-gray-6" />
						<span class="flex-1 truncate text-left">Configure AI</span>
					</button>
				</div>
			</nav>

			<Dropdown :options="userMenu" placement="right">
				<button
					class="flex w-full items-center gap-2.5 border-t border-outline-gray-1 px-3 py-3 text-left hover:bg-surface-gray-2"
				>
					<Avatar :label="overview.user.full_name" size="lg" />
					<div class="min-w-0 flex-1">
						<div class="truncate text-base text-ink-gray-8">{{ overview.user.full_name }}</div>
						<div class="truncate text-sm text-ink-gray-5">{{ overview.user.name }}</div>
					</div>
					<FeatherIcon name="chevron-up" class="size-4 shrink-0 text-ink-gray-5" />
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
import { Avatar, Dropdown, FeatherIcon, LoadingIndicator, Toast, call } from "frappe-ui"

import AiSettings from "./components/AiSettings.vue"
import Assistant from "./components/Assistant.vue"
import Callout from "./components/Callout.vue"
import NavLink from "./components/NavLink.vue"
import { loadOverview, state } from "./data/store"

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
	...(overview.value?.is_staff
		? [{ label: "Configure AI", icon: "cpu", onClick: () => (aiOpen.value = true) }]
		: []),
	...(overview.value?.can_use_desk
		? [{ label: "Switch to Desk", icon: "grid", onClick: () => (window.location.href = "/app") }]
		: []),
])

const userMenu = computed(() => [
	...(overview.value?.can_use_desk
		? [{ label: "Switch to Desk", icon: "grid", onClick: () => (window.location.href = "/app") }]
		: []),
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

onMounted(loadOverview)
</script>
