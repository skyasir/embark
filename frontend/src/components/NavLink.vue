<template>
	<router-link
		:to="to"
		class="flex h-8 items-center gap-2 rounded px-2 text-base text-ink-gray-7 transition-colors hover:bg-surface-gray-2"
		active-class="!bg-surface-selected font-medium !text-ink-gray-9 shadow-sm"
		exact-active-class="!bg-surface-selected font-medium !text-ink-gray-9 shadow-sm"
	>
		<FeatherIcon :name="icon || 'file-text'" class="size-4 shrink-0 text-ink-gray-6" />
		<span class="flex-1 truncate">{{ label }}</span>
		<span v-if="hint" class="text-sm text-ink-gray-4">{{ hint }}</span>
		<span v-if="dot" class="size-1.5 shrink-0 rounded-full" :class="dotClass" :title="dot" />
	</router-link>
</template>

<script setup>
import { computed } from "vue"
import { FeatherIcon } from "frappe-ui"

const props = defineProps({
	to: { type: Object, required: true },
	label: { type: String, required: true },
	icon: { type: String, default: "" },
	dot: { type: String, default: "" },
	hint: { type: String, default: "" },
})

const dotClass = computed(
	() =>
		({
			Ready: "bg-surface-green-3",
			"In Progress": "bg-surface-amber-3",
			"Needs Attention": "bg-surface-red-5",
		})[props.dot] || "bg-surface-gray-4"
)
</script>
