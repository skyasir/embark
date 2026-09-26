<template>
	<Tooltip :text="collapsed ? label : ''" placement="right">
		<router-link
			:to="to"
			class="flex h-8 items-center gap-2 rounded text-base text-ink-gray-7 transition-colors hover:bg-surface-gray-2"
			:class="collapsed ? 'justify-center px-0' : 'px-2'"
			active-class="!bg-surface-selected font-medium !text-ink-gray-9 shadow-sm"
			exact-active-class="!bg-surface-selected font-medium !text-ink-gray-9 shadow-sm"
		>
			<span class="relative shrink-0">
				<FeatherIcon :name="icon || 'file-text'" class="size-4 text-ink-gray-6" />
				<!-- Collapsed, the status has nowhere else to go. -->
				<span
					v-if="collapsed && dot"
					class="absolute -right-1 -top-0.5 size-1.5 rounded-full ring-2 ring-surface-menu-bar"
					:class="dotClass"
				/>
			</span>
			<template v-if="!collapsed">
				<span class="flex-1 truncate">{{ label }}</span>
				<span v-if="hint" class="text-sm text-ink-gray-4">{{ hint }}</span>
				<span v-if="dot" class="size-1.5 shrink-0 rounded-full" :class="dotClass" :title="dot" />
			</template>
		</router-link>
	</Tooltip>
</template>

<script setup>
import { computed } from "vue"
import { FeatherIcon, Tooltip } from "frappe-ui"

const props = defineProps({
	to: { type: Object, required: true },
	label: { type: String, required: true },
	icon: { type: String, default: "" },
	dot: { type: String, default: "" },
	hint: { type: String, default: "" },
	collapsed: { type: Boolean, default: false },
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
