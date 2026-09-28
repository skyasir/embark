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

				<!-- "Not sure" opens a place to say it instead of closing the question. -->
				<div v-if="openText" class="pt-2">
					<p class="mb-2 text-base text-ink-gray-6">
						Tell us in your own words and we'll work out what it means — or skip it and your
						consultant will ask.
					</p>
					<div
						class="rounded-lg border px-3 py-2 transition-colors"
						:class="writing ? 'border-outline-gray-3' : 'border-outline-gray-2'"
					>
						<div class="flex items-end gap-2">
							<textarea
								v-model="words"
								rows="1"
								class="fvs-words block max-h-28 flex-1 resize-none border-0 bg-transparent p-0 text-base leading-relaxed text-ink-gray-8 placeholder:text-ink-gray-4 focus:outline-none focus:ring-0"
							placeholder="For example: we keep some stock but order most of it in…"
								:disabled="data.locked || busy"
								@focus="writing = true"
								@blur="writing = false"
								@keydown.enter.exact.prevent="sendWords()"
							/>
							<button
								class="flex size-7 shrink-0 items-center justify-center rounded-full bg-surface-gray-3 text-ink-gray-8 transition-colors hover:bg-surface-gray-4 disabled:opacity-40"
								:disabled="busy || !words.trim()"
								aria-label="Send"
								@click="sendWords()"
							>
								<FeatherIcon name="arrow-up" class="size-4" />
							</button>
						</div>
					</div>
					<div class="mt-2">
						<Button variant="ghost" size="sm" :loading="busy" @click="answer(current, 'not_sure', true)">
							Skip this one
						</Button>
					</div>
					<p v-if="reading" class="mt-2 text-sm" :class="reading.understood ? 'text-ink-green-3' : 'text-ink-amber-3'">
						<template v-if="reading.understood">
							Recorded as <strong>{{ reading.read_as }}</strong>
							<template v-if="reading.why"> — {{ reading.why }}</template>. Pick above if that's wrong.
						</template>
						<template v-else>
							Kept in your words for your consultant to read.
						</template>
					</p>
				</div>

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

		<!-- Everything answered: what it comes to, not a replay of the form. -->
		<section v-else class="space-y-8">
			<div>
				<h1 class="text-2xl font-semibold text-ink-gray-9">
					That's everything — here's what it means for {{ o?.client_name }}
				</h1>
				<p class="mt-2 text-base leading-relaxed text-ink-gray-6">
					Worked out from your answers. Change any answer and this follows.
				</p>
			</div>

			<div class="grid gap-3 sm:grid-cols-3">
				<div v-for="card in cards" :key="card.label" class="rounded-lg border border-outline-gray-2 p-4">
					<div class="text-3xl font-semibold tabular-nums text-ink-gray-9">{{ card.count }}</div>
					<div class="mt-0.5 text-base text-ink-gray-7">{{ card.label }}</div>
					<div class="mt-2 text-sm leading-relaxed text-ink-gray-5">{{ card.examples }}</div>
				</div>
			</div>

			<div class="flex flex-wrap items-center justify-between gap-3">
				<Button variant="ghost" size="md" @click="showAnswers = !showAnswers">
					{{ showAnswers ? "Hide your answers" : `Review your answers (${total})` }}
				</Button>
				<Button variant="solid" size="md" icon-right="arrow-right" @click="router.push({ name: 'company' })">
					Next: company details
				</Button>
			</div>

			<ul
				v-if="showAnswers"
				class="divide-y divide-outline-gray-1 overflow-hidden rounded-lg border border-outline-gray-2"
			>
				<li
					v-for="(q, i) in data.questions"
					:key="q.key"
					class="flex items-center gap-3 px-4 py-3 hover:bg-surface-gray-1"
				>
					<span class="min-w-0 flex-1">
						<span class="block text-base text-ink-gray-6">{{ q.label }}</span>
						<span class="block truncate text-base font-medium text-ink-gray-9">{{ shown(q) }}</span>
					</span>
					<Button variant="ghost" size="sm" :disabled="data.locked" @click="index = i">Change</Button>
				</li>
			</ul>
		</section>
	</div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"
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
const words = ref("")
const openText = ref(false)
const writing = ref(false)
const reading = ref(null)

const showAnswers = ref(false)
const o = computed(() => state.overview)

/** What the answers came to: the steps, the settings, the decisions. */
const cards = computed(() => {
	const steps = o.value?.steps || []
	const plan = o.value?.plan || []
	const of = (kind) => plan.filter((line) => line.kind === kind)
	const names = (list, key) => list.slice(0, 3).map((x) => x[key]).join(", ") + (list.length > 3 ? "…" : "")
	return [
		{ count: steps.length, label: "kinds of data to collect", examples: names(steps, "area") },
		{ count: of("Setting").length, label: "things we'll switch on", examples: names(of("Setting"), "title") },
		{ count: of("Decision").length, label: "decisions for you", examples: names(of("Decision"), "title") },
	]
})

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
	// "Not sure" is rarely the whole truth, so it opens a box to say the rest.
	if (value === "not_sure") {
		openText.value = true
		nextTick(() => document.querySelector(".fvs-words, textarea")?.focus())
		return
	}
	// One choice answers and moves on; several stay open until Continue.
	if (q.type !== "Several choices") {
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

async function sendWords() {
	const text = words.value.trim()
	if (!text || busy.value) return
	busy.value = true
	reading.value = null
	try {
		const out = await api("answer_in_words", {
			onboarding: state.id,
			question: current.value.key,
			text,
		})
		setOverview(out.overview)
		reading.value = out
		words.value = ""
		await load()
		// Read confidently: move on. Otherwise stay, so they can pick instead.
		if (out.understood) setTimeout(() => (reading.value = null) || goNext(), 1200)
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
watch(current, (q) => {
	number.value = q?.type === "Number" ? q.answer || "" : ""
	words.value = ""
	reading.value = null
	// A question already answered in words opens with them showing.
	openText.value = q?.answer === "not_sure"
})

onMounted(() => window.addEventListener("keydown", onKey))
onBeforeUnmount(() => window.removeEventListener("keydown", onKey))

load()
</script>
