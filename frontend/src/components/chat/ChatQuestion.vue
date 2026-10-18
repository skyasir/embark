<template>
	<!-- The wizard's own control, inside the conversation. The customer answers
	     here and it is the same answer, saved the same way, as on the Setup
	     page — there is no second copy of a question anywhere. -->
	<div v-if="question" class="rounded-lg border border-outline-gray-2 p-3">
		<p class="text-base font-medium leading-snug text-ink-gray-8">{{ question.label }}</p>
		<p v-if="question.description" class="mt-1 text-sm leading-relaxed text-ink-gray-5">
			{{ question.description }}
		</p>

		<div class="ft-fill mt-2">
			<AnswerField v-model="draft" :question="question" @enter="save()" />
		</div>

		<div class="mt-2 flex items-center gap-2">
			<Button size="sm" variant="solid" :loading="saving" :disabled="!changed" @click="save()">
				{{ saved ? "Saved" : "Save" }}
			</Button>
			<span v-if="saved && !changed" class="text-sm text-ink-green-3">Answered.</span>
		</div>
	</div>

	<!-- A key that is not one of ours draws nothing: the words of the answer
	     are already on the screen, and an error box helps nobody. -->
	<p v-else-if="board && !question" class="hidden" />
</template>

<script setup>
import { computed, ref, watch } from "vue"
import { Button } from "frappe-ui"

import { toast } from "../../data/toast"

import AnswerField from "../AnswerField.vue"
import { api, errorText } from "../../data/api"
import { state } from "../../data/store"

const componentProps = defineProps({ props: { type: Object, required: true } })

const board = ref(null)
const draft = ref("")
const saving = ref(false)
const saved = ref(false)

/** Every question the wizard is asking, flattened. */
const questions = computed(() => (board.value?.tasks || []).flatMap((t) => t.questions))
const question = computed(() => questions.value.find((q) => q.key === componentProps.props.key) || null)
const changed = computed(() => question.value && draft.value !== (question.value.answer || ""))

async function load() {
	try {
		board.value = await api("wizard", { onboarding: state.id })
	} catch {
		// A question it cannot look up is a question it cannot show.
	}
}

watch(question, (q) => {
	draft.value = q?.answer || ""
	saved.value = Boolean(q?.answer)
})

async function save() {
	if (!question.value || !changed.value) return
	saving.value = true
	try {
		board.value = await api("wizard_answer", {
			onboarding: state.id,
			question: question.value.key,
			value: draft.value,
		})
		saved.value = true
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		saving.value = false
	}
}

load()
</script>
