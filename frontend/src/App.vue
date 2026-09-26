<template>
	<div class="flex h-full">
		<aside
			v-if="overview && !overview.needs_start"
			class="hidden w-64 shrink-0 flex-col border-r border-outline-gray-1 bg-surface-menu-bar md:flex"
		>
			<div class="flex items-center gap-2.5 px-3 py-3">
				<div
					class="flex size-8 shrink-0 items-center justify-center rounded-md bg-surface-gray-7 text-base font-semibold text-ink-white"
				>
					{{ overview.client_name.charAt(0).toUpperCase() }}
				</div>
				<div class="min-w-0">
					<div class="truncate text-base font-medium text-ink-gray-9">{{ overview.client_name }}</div>
					<div class="truncate text-sm text-ink-gray-5">
						{{ overview.package.name }} · {{ hours(overview.package.hours) }}
					</div>
				</div>
			</div>

			<nav class="flex-1 space-y-0.5 overflow-y-auto px-2 py-2">
				<NavLink :to="{ name: 'home' }" icon="home" label="Overview" />
				<NavLink
					:to="{ name: 'interview' }"
					label="About your business"
					:dot="overview.interview.done ? 'Ready' : 'Not Started'"
				/>
				<NavLink
					:to="{ name: 'company' }"
					label="Company details"
					:dot="overview.company_complete ? 'Ready' : 'Not Started'"
				/>
				<div class="px-2 pb-1 pt-4 text-sm font-medium text-ink-gray-5">Your data</div>
				<NavLink
					v-for="step in overview.steps"
					:key="step.area"
					:to="{ name: 'area', params: { area: step.area } }"
					:label="step.area"
					:dot="step.status"
					:hint="step.required ? '' : 'Optional'"
				/>
			</nav>

			<a
				v-if="overview.can_use_desk"
				href="/app"
				class="mx-2 mb-2 flex h-8 items-center gap-2 rounded px-2 text-base text-ink-gray-7 hover:bg-surface-gray-2"
			>
				<FeatherIcon name="grid" class="size-4" />
				Switch to Desk
			</a>
			<div class="flex items-center gap-2.5 border-t border-outline-gray-1 px-3 py-3">
				<Avatar :label="overview.user.full_name" size="lg" />
				<div class="min-w-0 flex-1">
					<div class="truncate text-base text-ink-gray-8">{{ overview.user.full_name }}</div>
					<div class="truncate text-sm text-ink-gray-5">{{ overview.user.name }}</div>
				</div>
				<Tooltip text="Log out">
					<Button variant="ghost" icon="log-out" label="Log out" @click="logout" />
				</Tooltip>
			</div>
		</aside>

		<div class="flex min-w-0 flex-1 flex-col">
			<header class="flex h-12 shrink-0 items-center gap-2 border-b border-outline-gray-1 px-5 text-base">
				<router-link :to="{ name: 'home' }" class="text-ink-gray-5 hover:text-ink-gray-8" aria-label="Overview">
					<FeatherIcon name="home" class="size-4" />
				</router-link>
				<span class="text-ink-gray-4">/</span>
				<span class="truncate font-medium text-ink-gray-9">{{ title }}</span>
				<!-- The sidebar, and its log-out button, is hidden on phones. -->
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
	<Toast />
</template>

<script setup>
import { computed, onMounted, watchEffect } from "vue"
import { useRoute, useRouter } from "vue-router"
import { Avatar, FeatherIcon, LoadingIndicator, Toast, Tooltip, call } from "frappe-ui"

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

// The tab reads "Items · Embark", so a customer with several tabs open can find it.
watchEffect(() => {
	document.title = route.name === "home" ? "Embark" : `${title.value} · Embark`
})

function hours(n) {
	return `${Number(n)} ${Number(n) === 1 ? "hour" : "hours"}`
}

async function logout() {
	try {
		await call("logout")
	} finally {
		window.location.href = "/login"
	}
}

onMounted(loadOverview)
</script>
