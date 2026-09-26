<template>
	<div class="rounded-lg border border-outline-gray-2 px-4 py-3">
		<div class="text-2xl font-semibold tabular-nums text-ink-gray-9">{{ value }}</div>
		<Badge class="mt-1" :theme="theme" :label="label" size="md" />
	</div>
</template>

<script setup>
import { Badge } from "frappe-ui"

defineProps({
	value: { type: Number, required: true },
	label: { type: String, required: true },
	theme: { type: String, default: "gray" },
})
</script>
