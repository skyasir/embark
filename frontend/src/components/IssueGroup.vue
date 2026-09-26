<template>
	<div class="rounded-lg border border-outline-gray-2">
		<button class="flex w-full items-start gap-3 px-4 py-3 text-left" :aria-expanded="open" @click="open = !open">
			<FeatherIcon
				:name="isError ? 'x-circle' : 'info'"
				class="mt-0.5 size-4 shrink-0"
				:class="isError ? 'text-ink-red-3' : 'text-ink-blue-3'"
			/>
			<span class="min-w-0 flex-1">
				<span class="block text-base font-semibold text-ink-gray-9">
					{{ group.title }}<template v-if="group.label">: {{ group.label }}</template>
					<span class="font-normal text-ink-gray-5"> ({{ group.count }})</span>
				</span>
				<span class="mt-0.5 block text-base text-ink-gray-6">{{ group.hint }}</span>
			</span>
			<FeatherIcon :name="open ? 'chevron-up' : 'chevron-down'" class="mt-0.5 size-4 shrink-0 text-ink-gray-5" />
		</button>

		<div v-if="open" class="border-t border-outline-gray-1 px-4 py-3">
			<!-- A whole column is missing: the fix is on the Match step. -->
			<div v-if="group.code === 'COLUMN_MISSING'" class="flex items-center justify-between gap-3">
				<span class="text-base text-ink-gray-7">{{ issues[0]?.message }}</span>
				<Button size="sm" @click="$emit('match')">Match columns</Button>
			</div>

			<p v-else-if="!column" class="text-base text-ink-gray-7">{{ issues[0]?.message }}</p>

			<!-- The same wrong value tends to repeat: fix it once for every row. -->
			<table v-else-if="byValue" class="w-full text-left text-base">
				<thead class="text-ink-gray-5">
					<tr>
						<th class="pb-2 font-medium">Your value</th>
						<th class="w-16 pb-2 font-medium">Rows</th>
						<th class="pb-2 font-medium">Change to</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="v in group.values" :key="v.value" class="align-top">
						<td class="py-1.5 pr-3 font-medium text-ink-gray-8">{{ v.value }}</td>
						<td class="py-1.5 tabular-nums text-ink-gray-6">{{ v.count }}</td>
						<td class="py-1">
							<FixInput
								:column="column"
								:suggestions="suggestionsFor(v.value)"
								:disabled="locked || busy"
								@apply="(value) => $emit('fix', { fieldname: group.fieldname, old_value: v.value, value })"
							/>
						</td>
					</tr>
				</tbody>
			</table>

			<!-- Empty cells and duplicates are row by row. -->
			<template v-else>
				<table class="w-full text-left text-base">
					<thead class="text-ink-gray-5">
						<tr>
							<th class="w-20 pb-2 font-medium">Row</th>
							<th class="pb-2 font-medium">Now</th>
							<th class="pb-2 font-medium">Change to</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="i in shown" :key="i.row" class="align-top">
							<td class="py-1.5 tabular-nums text-ink-gray-6">Row {{ i.row }}</td>
							<td class="py-1.5 pr-3 text-ink-gray-8">{{ i.value || "empty" }}</td>
							<td class="py-1">
								<FixInput
									:column="column"
									:disabled="locked || busy"
									@apply="(value) => $emit('fix', { fieldname: group.fieldname, row: i.row, value })"
								/>
							</td>
						</tr>
					</tbody>
				</table>
				<p v-if="group.count > shown.length" class="mt-2 text-sm text-ink-gray-5">
					And {{ group.count - shown.length }} more. With this many, it's quicker to fix them in your file and
					upload it again.
				</p>
			</template>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue"
import { FeatherIcon } from "frappe-ui"

import FixInput from "./FixInput.vue"

const props = defineProps({
	group: { type: Object, required: true },
	issues: { type: Array, required: true },
	column: { type: Object, default: null },
	locked: { type: Boolean, default: false },
	busy: { type: Boolean, default: false },
})
defineEmits(["fix", "match"])

const ROW_BY_ROW = ["REQUIRED_MISSING", "DUPLICATE"]
const isError = computed(() => props.group.severity === "error")
const byValue = computed(() => !ROW_BY_ROW.includes(props.group.code) && props.group.values.length > 0)
const shown = computed(() => props.issues.slice(0, 25))
// Start with the first few problems open, so the customer sees what to do.
const open = ref(isError.value)

function suggestionsFor(value) {
	return props.issues.find((i) => i.value === value)?.suggestions || []
}
</script>
