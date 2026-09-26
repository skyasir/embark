<template>
	<div class="flex gap-3 rounded-lg border px-4 py-3 text-base" :class="tones[tone].box">
		<FeatherIcon :name="icon || tones[tone].icon" class="mt-0.5 size-4 shrink-0" :class="tones[tone].icon_class" />
		<div class="min-w-0 flex-1 leading-relaxed text-ink-gray-8">
			<slot />
		</div>
	</div>
</template>

<script setup>
import { FeatherIcon } from "frappe-ui"

defineProps({
	tone: { type: String, default: "info" },
	icon: { type: String, default: "" },
})

const tones = {
	info: { box: "bg-surface-blue-1 border-outline-blue-1", icon: "info", icon_class: "text-ink-blue-3" },
	success: { box: "bg-surface-green-1 border-outline-green-1", icon: "check-circle", icon_class: "text-ink-green-3" },
	warning: { box: "bg-surface-amber-1 border-outline-amber-1", icon: "alert-triangle", icon_class: "text-ink-amber-3" },
	error: { box: "bg-surface-red-1 border-outline-red-1", icon: "alert-circle", icon_class: "text-ink-red-4" },
}
</script>
