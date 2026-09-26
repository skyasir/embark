<template>
	<form class="ft-fill flex items-center gap-2" @submit.prevent="apply">
		<FormControl
			v-if="options.length"
			v-model="value"
			type="select"
			:options="[{ label: 'Choose…', value: '' }, ...options.map((o) => ({ label: o, value: o }))]"
			:disabled="disabled"
			class="w-48"
		/>
		<template v-else>
			<FormControl
				v-model="value"
				:type="column.fieldtype === 'Date' ? 'date' : 'text'"
				placeholder="Type the correct value"
				:disabled="disabled"
				:list="listId"
				class="w-48"
			/>
			<datalist v-if="suggestions.length" :id="listId">
				<option v-for="s in suggestions" :key="s" :value="s" />
			</datalist>
		</template>
		<Button type="submit" size="sm" :disabled="disabled || value === ''">Apply</Button>
	</form>
</template>

<script setup>
import { computed, ref } from "vue"
import { FormControl } from "frappe-ui"

const props = defineProps({
	column: { type: Object, required: true },
	suggestions: { type: Array, default: () => [] },
	disabled: { type: Boolean, default: false },
})
const emit = defineEmits(["apply"])

const listId = `fix-${Math.random().toString(36).slice(2)}`
// The best suggestion is filled in, so a likely fix is one click; it is only
// applied when the customer presses Apply.
const value = ref(props.suggestions[0] || "")

const options = computed(() => {
	if (props.column.choices?.length) return props.column.choices
	if (props.column.fieldtype === "Check") return ["Yes", "No"]
	return []
})

function apply() {
	if (value.value !== "") emit("apply", value.value)
}
</script>
