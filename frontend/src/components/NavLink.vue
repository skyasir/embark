<template>
	<router-link
		:to="to"
		class="flex h-8 items-center gap-2 rounded px-2 text-base text-ink-gray-7 transition-colors hover:bg-surface-gray-2"
		active-class="!bg-surface-selected font-medium !text-ink-gray-9 shadow-sm"
		exact-active-class="!bg-surface-selected font-medium !text-ink-gray-9 shadow-sm"
	>
		<FeatherIcon v-if="icon" :name="icon" class="size-4 shrink-0" />
		<span v-else class="mx-1 size-2 shrink-0 rounded-full" :class="dotClass" :title="dot" />
		<span class="flex-1 truncate">{{ label }}</span>
		<span v-if="hint" class="text-sm text-ink-gray-4">{{ hint }}</span>
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
			"Needs Attention": "bg-surface-red-5",
		})[props.dot] || "bg-surface-gray-4"
)
</script>
