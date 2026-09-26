<template>
	<Badge :theme="look.theme" :label="look.label" size="md" />
</template>

<script setup>
import { computed } from "vue"
import { Badge } from "frappe-ui"

const props = defineProps({
	status: { type: String, required: true },
	errors: { type: Number, default: 0 },
	required: { type: Boolean, default: true },
})

const look = computed(() => {
	if (props.status === "Ready") return { theme: "green", label: "Ready" }
	if (props.status === "Needs Attention")
		return {
			theme: "red",
			label: props.errors ? `${props.errors} to fix` : "Needs attention",
		}
	return { theme: "gray", label: props.required ? "Not started" : "Optional" }
})
</script>
