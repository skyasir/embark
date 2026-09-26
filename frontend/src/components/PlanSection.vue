<template>
	<section v-if="lines.length" class="space-y-3">
		<div>
			<h2 class="text-base font-semibold text-ink-gray-8">{{ title }}</h2>
			<p class="text-base text-ink-gray-6">{{ subtitle }}</p>
		</div>
		<ul class="divide-y divide-outline-gray-1 overflow-hidden rounded-lg border border-outline-gray-2">
			<li v-for="line in lines" :key="line.key" class="flex items-start gap-3 px-4 py-3">
				<FeatherIcon :name="icon" class="mt-0.5 size-4 shrink-0 text-ink-gray-5" />
				<div class="min-w-0 flex-1">
					<div class="text-base font-medium text-ink-gray-9">{{ line.title }}</div>
					<div v-if="line.description" class="text-base text-ink-gray-6">{{ line.description }}</div>
					<div v-if="line.because" class="mt-0.5 text-sm text-ink-gray-5">
						Because {{ line.because }}.
					</div>
					<div v-if="line.detail" class="mt-1 text-sm text-ink-gray-5">
						<span class="font-medium">How:</span> {{ line.detail }}
					</div>
				</div>
				<Badge v-if="line.status !== 'Planned'" :theme="line.status === 'Done' ? 'green' : 'gray'" :label="line.status" size="md" />
			</li>
		</ul>
	</section>
</template>

<script setup>
import { computed } from "vue"
import { Badge, FeatherIcon } from "frappe-ui"

const props = defineProps({
	plan: { type: Array, required: true },
	kind: { type: String, required: true },
	title: { type: String, required: true },
	subtitle: { type: String, default: "" },
	icon: { type: String, default: "check" },
})

const lines = computed(() => props.plan.filter((line) => line.kind === props.kind))
</script>
