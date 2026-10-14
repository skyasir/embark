<template>
	<StartOnboarding v-if="o && o.needs_start" @configure-ai="aiOpen = true" />

	<div v-else-if="o" class="flex gap-8">
		<!-- Where the implementation stands, and the way back into it. -->
		<div class="min-w-0 flex-1 space-y-6">
			<div>
				<h1 class="text-2xl font-semibold text-ink-gray-9">
					Setting up {{ o.client_name }} in ERPNext
				</h1>
				<p class="mt-2 text-base leading-relaxed text-ink-gray-6">
					Answer the setup questions and Embark builds each record in ERPNext for you — the company,
					the financial year, your groups and warehouses — and shows you exactly what it wrote.
				</p>
			</div>

			<div class="rounded-lg border border-outline-gray-2 p-5">
				<div class="flex items-baseline justify-between">
					<span class="text-base text-ink-gray-6">Setup</span>
					<span class="text-sm text-ink-gray-5">
						{{ state2.built }} of {{ state2.tasks.length }} records built
					</span>
				</div>
				<div class="mt-1 flex items-baseline gap-3">
					<span class="text-3xl font-semibold tabular-nums text-ink-gray-9">{{ state2.percent }}%</span>
					<span class="text-base text-ink-gray-5">
						{{ state2.answered }} of {{ state2.total }} questions answered
					</span>
				</div>
				<div class="mt-3 h-2 overflow-hidden rounded-full bg-surface-gray-2">
					<div
						class="h-full rounded-full bg-surface-gray-7 transition-all duration-500"
						:style="{ width: `${state2.percent}%` }"
					/>
				</div>
				<div class="mt-4">
					<router-link :to="{ name: 'setup' }">
						<Button variant="solid" size="md" icon-right="arrow-right">
							{{ state2.answered ? "Continue setup" : "Start setup" }}
						</Button>
					</router-link>
				</div>
			</div>

			<!-- Each step, and whether it exists in ERPNext yet. -->
			<ul class="divide-y divide-outline-gray-1 overflow-hidden rounded-lg border border-outline-gray-2">
				<li v-for="task in state2.tasks" :key="task.task" class="flex items-center gap-3 px-4 py-3">
					<FeatherIcon
						:name="task.record ? 'check-circle' : task.icon || 'circle'"
						class="size-4 shrink-0"
						:class="task.record ? 'text-ink-green-3' : 'text-ink-gray-4'"
					/>
					<div class="min-w-0 flex-1">
						<div class="truncate text-base font-medium text-ink-gray-9">{{ task.title }}</div>
						<div class="truncate text-sm text-ink-gray-5">
							{{ task.record ? `${task.doctype} · ${task.record.name}` : task.doctype }}
						</div>
					</div>
					<span class="shrink-0 text-sm tabular-nums text-ink-gray-5">
						{{ task.answered }}/{{ task.total }}
					</span>
					<Badge
						:theme="task.record ? 'green' : task.answered ? 'orange' : 'gray'"
						size="sm"
						:label="task.record ? 'In ERPNext' : task.state"
					/>
				</li>
			</ul>
		</div>

		<!-- The ERPNext view: the records themselves, as the site holds them.
		     The site's own screens are a page wide, so they are on Ask. -->
		<aside class="hidden w-[460px] shrink-0 space-y-4 border-l border-outline-gray-2 pl-6 xl:block">
			<div class="flex items-end justify-between gap-2">
				<div>
					<h2 class="text-base font-semibold text-ink-gray-8">ERPNext</h2>
					<p class="text-sm text-ink-gray-5">What is on this site, read back from the records.</p>
				</div>
				<a :href="framePath" target="_blank" rel="noopener" class="shrink-0">
					<Button size="sm" variant="ghost" icon="external-link" label="Open the site" />
				</a>
			</div>

			<div
				v-for="task in built"
				:key="task.task"
				class="overflow-hidden rounded-lg border border-outline-green-2"
			>
				<div class="flex items-center gap-2 border-b border-outline-green-2 bg-surface-green-1 px-3 py-2">
					<FeatherIcon name="check-circle" class="size-3.5 shrink-0 text-ink-green-3" />
					<span class="min-w-0 flex-1 truncate text-sm font-medium text-ink-green-3">
						{{ task.record.doctype }}
					</span>
					<a :href="task.record.url" target="_blank" rel="noopener">
						<Button size="sm" variant="ghost" icon="external-link" label="Open in ERPNext" />
					</a>
				</div>
				<table class="w-full text-sm">
					<tbody>
						<tr class="border-b border-outline-gray-1">
							<td class="px-3 py-1.5 text-ink-gray-5">Name</td>
							<td class="px-3 py-1.5 font-medium text-ink-gray-9">{{ task.record.name }}</td>
						</tr>
						<tr
							v-for="f in task.record.fields.slice(0, 5)"
							:key="f.field"
							class="border-b border-outline-gray-1 last:border-0"
						>
							<td class="w-2/5 px-3 py-1.5 align-top text-ink-gray-5">{{ f.field }}</td>
							<td class="px-3 py-1.5 align-top text-ink-gray-8">{{ f.value }}</td>
						</tr>
					</tbody>
				</table>
			</div>

			<p
				v-if="!built.length"
				class="rounded-lg border border-outline-gray-2 px-3 py-4 text-sm text-ink-gray-5"
			>
				Nothing built yet. Answer a step's questions and press Create in ERPNext, and the record appears
				here with every field Embark wrote.
			</p>
		</aside>
	</div>

	<AiSettings v-model="aiOpen" />
</template>

<script setup>
import { computed, ref, watch } from "vue"
import { Badge, Button, FeatherIcon } from "frappe-ui"

import AiSettings from "../components/AiSettings.vue"
import StartOnboarding from "../components/StartOnboarding.vue"
import { api } from "../data/api"
import { state } from "../data/store"

const aiOpen = ref(false)
const o = computed(() => state.overview)
const state2 = ref({ tasks: [], answered: 0, total: 0, percent: 0, built: 0 })
const built = computed(() => state2.value.tasks.filter((t) => t.record))

/** "Open the site" goes to the newest record Embark made, else the desk. */
const framePath = computed(() => built.value[built.value.length - 1]?.record?.url || "/app")

async function load() {
	if (!state.id) return
	try {
		state2.value = await api("wizard_state", { onboarding: state.id })
	} catch {
		// The overview is a mirror: if it cannot read, it shows nothing rather than a lie.
	}
}

watch(() => state.id, load, { immediate: true })
</script>
