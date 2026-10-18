<template>
	<!-- Bottom right, out of the way of the composer and the wizard's
	     buttons, and above the ERPNext frame. -->
	<div class="pointer-events-none fixed bottom-5 right-5 z-[60] flex flex-col items-end gap-2">
		<TransitionGroup
			enter-active-class="transition duration-150 ease-out"
			enter-from-class="translate-y-2 opacity-0"
			leave-active-class="transition duration-150 ease-in"
			leave-to-class="translate-y-2 opacity-0"
		>
			<div
				v-for="item in toasts"
				:key="item.id"
				class="pointer-events-auto flex max-w-[420px] items-start gap-2.5 rounded-lg border px-3.5 py-2.5 shadow-lg"
				:class="skin[item.tone] || skin.info"
				role="status"
			>
				<FeatherIcon :name="mark[item.tone] || 'info'" class="mt-0.5 size-4 shrink-0" />
				<span class="min-w-0 flex-1 text-base leading-snug">{{ item.text }}</span>
				<button class="shrink-0 opacity-60 hover:opacity-100" aria-label="Dismiss" @click="dismiss(item.id)">
					<FeatherIcon name="x" class="size-3.5" />
				</button>
			</div>
		</TransitionGroup>
	</div>
</template>

<script setup>
import { FeatherIcon } from "frappe-ui"

import { dismiss, toasts } from "../data/toast"

const skin = {
	success: "border-outline-green-2 bg-surface-green-1 text-ink-green-3",
	error: "border-outline-red-2 bg-surface-red-1 text-ink-red-3",
	warning: "border-outline-amber-2 bg-surface-amber-1 text-ink-amber-3",
	info: "border-outline-gray-2 bg-surface-gray-2 text-ink-gray-8",
}
const mark = { success: "check-circle", error: "alert-circle", warning: "alert-triangle", info: "info" }
</script>
