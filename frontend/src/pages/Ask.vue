<template>
	<!-- The chat is a column; ERPNext is a whole application. So the chat takes
	     a column's worth and the site takes the rest, which is the only width
	     the desk is actually readable in. -->
	<div class="flex h-full min-h-0 gap-6">
		<section class="flex w-[400px] shrink-0 flex-col">
			<div class="mb-3 shrink-0">
				<h1 class="text-xl font-semibold text-ink-gray-9">Ask Embark</h1>
				<p class="text-sm text-ink-gray-5">
					Say what you need and watch it appear on the site beside you.
				</p>
			</div>

			<Assistant v-if="o?.assistant" />
			<div v-else class="rounded-lg border border-outline-gray-2 px-4 py-5">
				<p class="text-base text-ink-gray-7">
					No model is set up yet, so there is nothing to ask. The questions in Setup work without one.
				</p>
				<div class="mt-3 flex gap-2">
					<Button v-if="o?.can_configure_ai" variant="solid" label="Configure AI" @click="aiOpen = true" />
					<router-link :to="{ name: 'setup' }">
						<Button variant="subtle" label="Go to Setup" />
					</router-link>
				</div>
			</div>
		</section>

		<section class="flex min-w-0 flex-1 flex-col">
			<div class="mb-3 flex shrink-0 items-end justify-between gap-2">
				<div>
					<h2 class="text-base font-semibold text-ink-gray-8">ERPNext</h2>
					<p class="text-sm text-ink-gray-5">This site, live. Anything Embark writes shows up here.</p>
				</div>
				<div class="flex shrink-0 rounded-md border border-outline-gray-2 p-0.5">
					<button
						v-for="place in places"
						:key="place.path"
						class="rounded px-2.5 py-1 text-sm transition-colors"
						:class="path === place.path ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-5 hover:text-ink-gray-8'"
						@click="path = place.path"
					>
						{{ place.label }}
					</button>
				</div>
			</div>
			<ErpnextFrame :path="path" :height="frameHeight" />
		</section>
	</div>

	<AiSettings v-model="aiOpen" />
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue"
import { Button } from "frappe-ui"

import AiSettings from "../components/AiSettings.vue"
import Assistant from "../components/Assistant.vue"
import ErpnextFrame from "../components/ErpnextFrame.vue"
import { state } from "../data/store"

const o = computed(() => state.overview)
const aiOpen = ref(false)
const path = ref("/app")
const frameHeight = ref(600)

// A few places worth reaching without leaving the conversation.
const places = [
	{ label: "Desk", path: "/app" },
	{ label: "Company", path: "/app/company" },
	{ label: "Items", path: "/app/item" },
	{ label: "Customers", path: "/app/customer" },
]

/** The frame should reach the bottom of the window, whatever the window is. */
function fit() {
	frameHeight.value = Math.max(window.innerHeight - 200, 420)
}

onMounted(() => {
	fit()
	window.addEventListener("resize", fit)
})
onBeforeUnmount(() => window.removeEventListener("resize", fit))
</script>
