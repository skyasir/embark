<template>
	<!-- One answer, in whatever shape the question takes. The same control
	     serves the company form and the one-question-at-a-time wizard, so an
	     answer looks the same wherever it is given. -->
	<select
		v-if="question.type === 'Select'"
		:value="modelValue"
		class="w-full rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-2 text-base text-ink-gray-8"
		@change="emit('update:modelValue', $event.target.value)"
	>
		<option value="">Choose…</option>
		<option v-for="c in question.choices" :key="c.value" :value="c.value">{{ c.label }}</option>
	</select>

	<select
		v-else-if="question.type === 'Yes / No'"
		:value="modelValue"
		class="w-full rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-2 text-base text-ink-gray-8"
		@change="emit('update:modelValue', $event.target.value)"
	>
		<option value="">Choose…</option>
		<option value="Yes">Yes</option>
		<option value="No">No</option>
	</select>

	<!-- Several answers at once, pressed on and off. As cards when the choice
	     is the point of the screen, as rows when it is one question among many. -->
	<div
		v-else-if="question.type === 'Multiple Choice'"
		:class="layout === 'cards' ? 'grid gap-3 sm:grid-cols-2 xl:grid-cols-3' : 'space-y-2'"
	>
		<button
			v-for="(choice, i) in question.choices"
			:key="choice.value"
			class="flex w-full items-center gap-3 rounded-lg border text-left transition-colors"
			:class="[
				layout === 'cards' ? 'px-3.5 py-3 text-base' : 'px-3 py-2.5 text-base',
				picked.includes(choice.value)
					? 'border-outline-gray-4 bg-surface-gray-2 text-ink-gray-9'
					: 'border-outline-gray-2 text-ink-gray-7 hover:bg-surface-gray-1',
			]"
			@click="toggle(choice.value)"
		>
			<span
				class="flex size-5 shrink-0 items-center justify-center rounded border text-xs"
				:class="
					picked.includes(choice.value)
						? 'border-outline-gray-5 bg-surface-gray-7 text-ink-white'
						: 'border-outline-gray-3 text-ink-gray-4'
				"
			>
				<FeatherIcon v-if="picked.includes(choice.value)" name="check" class="size-3" />
				<template v-else-if="i < 9">{{ i + 1 }}</template>
			</span>
			<span class="min-w-0 flex-1">{{ choice.label }}</span>
		</button>
	</div>

	<Autocomplete
		v-else-if="question.type === 'Link'"
		:options="links"
		:model-value="modelValue"
		placeholder="Start typing…"
		@update:model-value="(v) => emit('update:modelValue', v?.value ?? '')"
	/>

	<FormControl
		v-else
		:model-value="modelValue"
		:type="question.type === 'Date' ? 'date' : question.type === 'Number' ? 'number' : 'text'"
		placeholder="Enter your answer..."
		@update:model-value="(v) => emit('update:modelValue', v)"
		@keydown.enter="emit('enter')"
	/>
</template>

<script setup>
import { computed, ref, watch } from "vue"
import { Autocomplete, FeatherIcon, FormControl } from "frappe-ui"

import { api } from "../data/api"

const props = defineProps({
	question: { type: Object, required: true },
	modelValue: { type: String, default: "" },
	// "cards" when the choice is the whole screen, "rows" inside a question.
	layout: { type: String, default: "rows" },
})
const emit = defineEmits(["update:modelValue", "enter"])

const links = ref([])
const picked = computed(() =>
	(props.modelValue || "")
		.split(",")
		.map((v) => v.trim())
		.filter(Boolean)
)

function toggle(value) {
	// A second press takes it off again, so nothing is a one-way door.
	const now = picked.value.includes(value)
		? picked.value.filter((v) => v !== value)
		: [...picked.value, value]
	emit("update:modelValue", now.join(","))
}

/** A Link question offers what the site actually has. */
watch(
	() => props.question?.link_doctype,
	async (doctype) => {
		links.value = []
		if (props.question?.type !== "Link" || !doctype) return
		try {
			const rows = await api("suggestions", { doctype })
			links.value = (rows || []).map((name) => ({ label: name, value: name }))
		} catch {
			// Nothing to suggest is not an error: the answer can still be typed.
		}
	},
	{ immediate: true }
)
</script>
