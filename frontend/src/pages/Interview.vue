<template>
	<div v-if="loading" class="flex justify-center py-24">
		<LoadingIndicator class="size-6 text-ink-gray-5" />
	</div>

	<div v-else-if="data" class="mx-auto max-w-xl">
		<!-- Where you are, without a wall of questions to scroll past. -->
		<div class="mb-8 flex items-center gap-3">
			<div class="h-1 flex-1 overflow-hidden rounded-full bg-surface-gray-2">
				<div
					class="h-full rounded-full bg-surface-gray-7 transition-all duration-300"
					:style="{ width: `${(100 * answered) / Math.max(total, 1)}%` }"
				/>
			</div>
			<span class="shrink-0 text-sm tabular-nums text-ink-gray-5">{{ answered }} of {{ total }}</span>
		</div>

		<Callout v-if="data.locked" tone="info" class="mb-6">
			Your data is with your consultant, so it can't be changed now.
		</Callout>

		<TallyHint class="mb-6" />

		<!-- One question at a time. -->
		<section v-if="current" :key="current.key" class="space-y-6">
			<div>
				<p class="text-sm font-medium uppercase tracking-wide text-ink-gray-4">{{ current.section }}</p>
				<h1 class="mt-1 text-2xl font-semibold leading-snug text-ink-gray-9">{{ current.label }}</h1>
				<p v-if="current.help" class="mt-2 text-base leading-relaxed text-ink-gray-6">
					{{ current.help }}
				</p>
			</div>

			<!-- A number is typed; everything else is chosen. -->
			<div v-if="current.type === 'Number'" class="ft-fill flex gap-2">
				<FormControl
					v-model="number"
					class="w-40"
					type="text"
					placeholder="0"
					:disabled="data.locked || busy"
					@keydown.enter="answer(current, number)"
				/>
				<Button variant="solid" size="md" :loading="busy" @click="answer(current, number)">Continue</Button>
			</div>

			<div v-else class="space-y-2">
				<button
					v-for="(choice, i) in optionsFor(current)"
					:key="choice.value"
					class="flex w-full items-center gap-3 rounded-lg border px-4 py-3 text-left text-base transition-colors"
					:class="
						isChosen(current, choice.value)
							? 'border-outline-gray-5 bg-surface-gray-2 font-medium text-ink-gray-9'
							: 'border-outline-gray-2 text-ink-gray-7 hover:border-outline-gray-3 hover:bg-surface-gray-1'
					"
					:disabled="data.locked || busy"
					@click="choose(current, choice.value)"
				>
					<span
						class="flex size-5 shrink-0 items-center justify-center rounded-full border text-xs"
						:class="
							isChosen(current, choice.value)
								? 'border-outline-gray-5 bg-surface-gray-7 text-ink-white'
								: 'border-outline-gray-2 text-ink-gray-4'
						"
					>
						<FeatherIcon v-if="isChosen(current, choice.value)" name="check" class="size-3" />
						<template v-else>{{ i + 1 }}</template>
					</span>
					<span class="flex-1">{{ choice.label }}</span>
				</button>

				<!-- Several choices stay open until you say you are done. -->
				<div v-if="current.type === 'Several choices'" class="pt-2">
					<Button
						variant="solid"
						size="md"
						icon-right="arrow-right"
						:loading="busy"
						:disabled="!current.answer"
						@click="goNext()"
					>
						Continue
					</Button>
				</div>
			</div>

			<div class="flex items-center justify-between pt-2">
				<Button v-if="index > 0" variant="ghost" icon-left="chevron-left" @click="index--">Back</Button>
				<span v-else />
				<span class="text-sm text-ink-gray-4">Press 1–9 to choose</span>
			</div>
		</section>

		<!-- Everything answered: what you said, and where to go next. -->
		<section v-else class="space-y-6">
			<div>
				<h1 class="text-2xl font-semibold text-ink-gray-9">That's everything we need to ask</h1>
				<p class="mt-2 text-base leading-relaxed text-ink-gray-6">
					Your answers decide what we set up and what we ask you for. Change any of them and the
					checklist follows.
				</p>
			</div>

			<ul class="divide-y divide-outline-gray-1 overflow-hidden rounded-lg border border-outline-gray-2">
				<li
					v-for="(q, i) in data.questions"
					:key="q.key"
					class="flex items-center gap-3 px-4 py-3 hover:bg-surface-gray-1"
				>
					<span class="min-w-0 flex-1">
						<span class="block text-base text-ink-gray-7">{{ q.label }}</span>
						<span class="block truncate text-base font-medium text-ink-gray-9">{{ shown(q) }}</span>
					</span>
					<Button variant="ghost" size="sm" :disabled="data.locked" @click="index = i">Change</Button>
				</li>
			</ul>

			<div class="flex justify-end">
				<Button variant="solid" size="md" icon-right="arrow-right" @click="router.push({ name: 'company' })">
					Next: company details
				</Button>
			</div>
		</section>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"
import { useRouter } from "vue-router"
import { Button, FeatherIcon, FormControl, LoadingIndicator, toast } from "frappe-ui"

import Callout from "../components/Callout.vue"
import TallyHint from "../components/TallyHint.vue"
import { api, errorText } from "../data/api"
import { setOverview, state } from "../data/store"

const router = useRouter()
const data = ref(null)
const loading = ref(true)
const busy = ref(false)
const index = ref(0)
const number = ref("")

const total = computed(() => data.value?.questions.length || 0)
const answered = computed(() => (data.value?.questions || []).filter((q) => q.answer).length)
const current = computed(() => (data.value ? data.value.questions[index.value] : null))

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

function shown(q) {
	if (!q.answer) return "—"
	const labels = optionsFor(q)
	return q.answer
		.split(",")
		.map((v) => labels.find((c) => c.value === v)?.label || v)
		.join(", ")
}

function choose(q, value) {
	// One choice answers and moves on; several stay open until Continue.
	if (q.type !== "Several choices" || value === "not_sure") {
		return answer(q, isChosen(q, value) ? "" : value, true)
	}
	const chosen = (q.answer || "").split(",").filter((v) => v && v !== "not_sure")
	const next = isChosen(q, value) ? chosen.filter((v) => v !== value) : [...chosen, value]
	answer(q, next.join(","))
}

async function answer(q, value, advance = false) {
	busy.value = true
	try {
		// Saved one at a time, because the next question depends on this one.
		setOverview(await api("save_answers", { onboarding: state.id, answers: { [q.key]: value } }))
		await load()
		if (advance && value) goNext()
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		busy.value = false
	}
}

function goNext() {
	const questions = data.value?.questions || []
	// The next one that still needs an answer, wherever it is.
	const unanswered = questions.findIndex((q, i) => i > index.value && !q.answer)
	const first = questions.findIndex((q) => !q.answer)
	index.value = unanswered !== -1 ? unanswered : first !== -1 ? first : questions.length
}

function onKey(event) {
	if (!current.value || busy.value || data.value?.locked) return
	if (event.target.tagName === "INPUT" || event.target.tagName === "TEXTAREA") return
	const n = Number(event.key)
	const choices = optionsFor(current.value)
	if (n >= 1 && n <= choices.length) {
		event.preventDefault()
		choose(current.value, choices[n - 1].value)
	}
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

// Open on the first unanswered question, so coming back resumes rather than
// restarts — and does not skip the one it lands on.
watch(data, (value, old) => {
	if (!value || old) return
	const first = value.questions.findIndex((q) => !q.answer)
	index.value = first === -1 ? value.questions.length : first
})
watch(current, (q) => (number.value = q?.type === "Number" ? q.answer || "" : ""))

onMounted(() => window.addEventListener("keydown", onKey))
onBeforeUnmount(() => window.removeEventListener("keydown", onKey))

load()
</script>
