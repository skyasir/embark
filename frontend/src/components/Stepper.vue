<template>
	<ol class="flex flex-wrap items-center gap-x-3 gap-y-2">
		<template v-for="(step, i) in steps" :key="step.label">
			<li>
				<button
					class="flex items-center gap-2 rounded text-base disabled:cursor-default"
					:disabled="!step.reachable"
					@click="$emit('select', i)"
				>
					<span
						class="flex size-6 items-center justify-center rounded-full text-sm font-medium"
						:class="
							i === current
								? 'bg-surface-gray-7 text-ink-white'
								: step.done
									? 'bg-surface-green-3 text-ink-white'
									: 'bg-surface-gray-2 text-ink-gray-5'
						"
					>
						<FeatherIcon v-if="step.done && i !== current" name="check" class="size-3.5" />
						<template v-else>{{ i + 1 }}</template>
					</span>
					<span
						:class="
							i === current
								? 'font-semibold text-ink-gray-9'
								: step.done
									? 'text-ink-green-3'
									: 'text-ink-gray-5'
						"
					>
						{{ step.label }}
					</span>
				</button>
			</li>
			<li
				v-if="i < steps.length - 1"
				aria-hidden="true"
				class="hidden h-px w-8 sm:block"
				:class="step.done ? 'bg-surface-green-3' : 'bg-surface-gray-3'"
			/>
		</template>
	</ol>
</template>

<script setup>
import { FeatherIcon } from "frappe-ui"

defineProps({
	steps: { type: Array, required: true },
	current: { type: Number, required: true },
})
defineEmits(["select"])
</script>
