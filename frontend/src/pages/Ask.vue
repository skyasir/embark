<template>
	<!-- Two panes: what you say on the left, the site it happens on, in full,
	     on the right. Nothing above either of them — the page title is already
	     in the header, and a second one only pushed ERPNext down. -->
	<div class="flex h-full min-h-0 gap-4">
		<section class="flex w-[380px] shrink-0 flex-col xl:w-[420px]">
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
			<ErpnextFrame :path="state.site.path" :seq="state.site.seq" :height="frameHeight" />
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
const frameHeight = ref(600)

/** The frame reaches the bottom of the window, whatever the window is. */
function fit() {
	frameHeight.value = Math.max(window.innerHeight - 136, 420)
}

onMounted(() => {
	fit()
	window.addEventListener("resize", fit)
})
onBeforeUnmount(() => window.removeEventListener("resize", fit))
</script>
