<template>
	<Tooltip :text="label" placement="right">
		<router-link
			:to="to"
			class="group relative flex w-16 flex-col items-center gap-1 rounded-lg py-2 transition-colors"
			:class="active ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8'"
		>
			<FeatherIcon :name="icon" class="size-5" />
			<span class="text-[11px] leading-none">{{ label }}</span>
			<!-- Something still to do here, without a number nobody asked for. -->
			<span v-if="dot" class="absolute right-2.5 top-1.5 size-1.5 rounded-full bg-surface-amber-3" />
		</router-link>
	</Tooltip>
</template>

<script setup>
import { computed } from "vue"
import { useRoute } from "vue-router"
import { FeatherIcon, Tooltip } from "frappe-ui"

const props = defineProps({
	to: { type: Object, required: true },
	icon: { type: String, required: true },
	label: { type: String, required: true },
	dot: { type: String, default: "" },
})

const route = useRoute()
const active = computed(() => route.name === props.to.name)
</script>
