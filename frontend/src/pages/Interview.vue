<template>
	<div v-if="loading" class="flex justify-center py-24">
		<LoadingIndicator class="size-6 text-ink-gray-5" />
	</div>

	<div v-else-if="data" class="space-y-6">
		<div>
			<h1 class="text-2xl font-semibold text-ink-gray-9">Tell us about your business</h1>
			<p class="mt-2 text-base leading-relaxed text-ink-gray-6">
				A few questions, so we set up ERPNext the way you work and only ask for the data that matters.
				Answer "Not sure" and your consultant will decide.
			</p>
		</div>

		<Callout v-if="data.locked" tone="info">Your data is with your consultant, so it can't be changed now.</Callout>

		<div class="flex items-center gap-3">
			<div class="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-gray-2">
				<div
					class="h-full rounded-full transition-all"
					:class="data.progress.done ? 'bg-surface-green-3' : 'bg-surface-gray-7'"
					:style="{ width: `${(100 * data.progress.answered) / Math.max(data.progress.total, 1)}%` }"
				/>
			</div>
			<span class="text-base tabular-nums text-ink-gray-6">
				{{ data.progress.answered }} of {{ data.progress.total }} answered
			</span>
		</div>

		<TallyHint />

		<section v-for="group in groups" :key="group.name" class="space-y-5">
			<h2 class="border-b border-outline-gray-1 pb-1 text-base font-semibold text-ink-gray-8">
				{{ group.name }}
			</h2>
			<div v-for="q in group.questions" :key="q.key" class="space-y-2">
				<div>
					<div class="text-base font-medium text-ink-gray-8">{{ q.label }}</div>
					<div v-if="q.help" class="text-sm text-ink-gray-5">{{ q.help }}</div>
				</div>

				<FormControl
					v-if="q.type === 'Number'"
					:model-value="q.answer"
					type="text"
					class="ft-fill w-32"
					placeholder="0"
					:disabled="data.locked || busy"
					@change="(e) => answer(q, e.target.value)"
				/>
				<div v-else class="flex flex-wrap gap-2">
					<button
						v-for="choice in optionsFor(q)"
						:key="choice.value"
						class="rounded border px-3 py-1 text-base transition-colors disabled:opacity-60"
						:class="
							isChosen(q, choice.value)
								? 'border-outline-gray-5 bg-surface-gray-7 text-ink-white'
								: 'border-outline-gray-2 text-ink-gray-7 hover:bg-surface-gray-2'
						"
						:disabled="data.locked || busy"
						@click="choose(q, choice.value)"
					>
						{{ choice.label }}
					</button>
				</div>
			</div>
		</section>

		<div class="flex justify-between">
			<Button size="md" icon-left="chevron-left" @click="$router.push({ name: 'home' })">Overview</Button>
			<Button variant="solid" size="md" icon-right="arrow-right" @click="next">
				{{ data.progress.done ? "Next: company details" : "Back to overview" }}
			</Button>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import { FormControl, LoadingIndicator, toast } from "frappe-ui"

import Callout from "../components/Callout.vue"
import TallyHint from "../components/TallyHint.vue"
import { api, errorText } from "../data/api"
import { setOverview, state } from "../data/store"

const router = useRouter()
const data = ref(null)
const loading = ref(true)
const busy = ref(false)

const groups = computed(() => {
	const out = []
	for (const q of data.value.questions) {
		const group = out.find((g) => g.name === q.section)
		if (group) group.questions.push(q)
		else out.push({ name: q.section, questions: [q] })
	}
	return out
})

const YES_NO = [
	{ value: "yes", label: "Yes" },
	{ value: "no", label: "No" },
]
const NOT_SURE = { value: "not_sure", label: "Not sure" }

function optionsFor(q) {
	const choices = q.type === "Yes / No" ? YES_NO : q.choices
	return q.allow_not_sure ? [...choices, NOT_SURE] : choices
}

function isChosen(q, value) {
	return (q.answer || "").split(",").includes(value)
}

function choose(q, value) {
	if (q.type !== "Several choices" || value === "not_sure") {
		return answer(q, isChosen(q, value) ? "" : value)
	}
	const chosen = (q.answer || "").split(",").filter((v) => v && v !== "not_sure")
	const next = isChosen(q, value) ? chosen.filter((v) => v !== value) : [...chosen, value]
	answer(q, next.join(","))
}

async function answer(q, value) {
	busy.value = true
	try {
		// Saving each answer as it is given keeps the follow-up questions honest.
		setOverview(await api("save_answers", { onboarding: state.id, answers: { [q.key]: value } }))
		await load()
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		busy.value = false
	}
}

function next() {
	router.push(data.value.progress.done ? { name: "company" } : { name: "home" })
}

async function load() {
	try {
		data.value = await api("get_interview", { onboarding: state.id })
	} catch (e) {
		toast.error(errorText(e))
		router.push({ name: "home" })
	} finally {
		loading.value = false
	}
}

load()
</script>
