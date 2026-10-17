<template>
	<!-- Something that is now in ERPNext, with a way straight to it. -->
	<div class="overflow-hidden rounded-lg border border-outline-green-2">
		<div class="flex items-center gap-2 border-b border-outline-green-2 bg-surface-green-1 px-3 py-2">
			<FeatherIcon name="check-circle" class="size-4 shrink-0 text-ink-green-3" />
			<span class="min-w-0 flex-1 truncate text-sm font-semibold text-ink-green-3">
				{{ props.doctype }} {{ props.name }}
			</span>
			<a v-if="url" :href="url" target="_blank" rel="noopener">
				<Button size="sm" variant="ghost" icon-right="external-link" label="Open" />
			</a>
		</div>
		<p v-if="props.note" class="px-3 py-2 text-sm text-ink-gray-6">{{ props.note }}</p>
	</div>
</template>

<script setup>
import { computed } from "vue"
import { Button, FeatherIcon } from "frappe-ui"

const componentProps = defineProps({ props: { type: Object, required: true } })

/** Built here, not taken from the model: it cannot send anyone elsewhere. */
const url = computed(() => {
	const { doctype, name } = componentProps.props
	if (!doctype || !name) return ""
	return `/app/${doctype.toLowerCase().replace(/ /g, "-")}/${encodeURIComponent(name)}`
})
</script>
