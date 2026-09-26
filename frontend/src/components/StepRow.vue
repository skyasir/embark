<template>
	<li>
		<router-link :to="to" class="flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-surface-gray-1">
			<span
				class="flex size-7 shrink-0 items-center justify-center rounded-full"
				:class="status === 'Ready' ? 'bg-surface-green-3 text-ink-white' : 'bg-surface-gray-2 text-ink-gray-6'"
			>
				<FeatherIcon :name="status === 'Ready' ? 'check' : icon || 'file-text'" class="size-4" />
			</span>
			<span class="min-w-0 flex-1">
				<span class="block text-base font-medium text-ink-gray-9">{{ title }}</span>
				<span class="block truncate text-base text-ink-gray-5">
					{{ description }}
					<template v-if="rows"> · {{ rows }} {{ rows === 1 ? "row" : "rows" }}</template>
				</span>
			</span>
			<StatusBadge :status="status" :errors="errors" :required="required" />
			<FeatherIcon name="chevron-right" class="size-4 shrink-0 text-ink-gray-4" />
		</router-link>
	</li>
</template>

<script setup>
import { FeatherIcon } from "frappe-ui"
import StatusBadge from "./StatusBadge.vue"

defineProps({
	title: { type: String, required: true },
	icon: { type: String, default: "" },
	description: { type: String, default: "" },
	to: { type: Object, required: true },
	status: { type: String, required: true },
	errors: { type: Number, default: 0 },
	rows: { type: Number, default: 0 },
	required: { type: Boolean, default: true },
})
</script>
