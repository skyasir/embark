<template>
	<!-- What is left, as a list you can press. Each line is a step of the
	     wizard, so pressing one goes to the real thing rather than a copy. -->
	<ul class="divide-y divide-outline-gray-1 overflow-hidden rounded-lg border border-outline-gray-2">
		<li v-for="(item, i) in items" :key="i">
			<router-link
				:to="{ name: 'setup' }"
				class="flex items-center gap-2 px-3 py-2 text-base text-ink-gray-7 transition-colors hover:bg-surface-gray-2"
			>
				<FeatherIcon
					:name="item.done ? 'check-circle' : 'circle'"
					class="size-3.5 shrink-0"
					:class="item.done ? 'text-ink-green-3' : 'text-ink-gray-4'"
				/>
				<span class="min-w-0 flex-1">{{ item.label }}</span>
			</router-link>
		</li>
	</ul>
</template>

<script setup>
import { computed } from "vue"
import { FeatherIcon } from "frappe-ui"

const componentProps = defineProps({ props: { type: Object, required: true } })

const items = computed(() =>
	(componentProps.props.items || []).map((item) =>
		typeof item === "string" ? { label: item, done: false } : item
	)
)
</script>
