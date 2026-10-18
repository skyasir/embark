<template>
	<div v-if="loading" class="flex justify-center py-24">
		<LoadingIndicator class="size-6 text-ink-gray-5" />
	</div>

	<!-- Onboarding in three stages: who the company is, which parts of ERPNext
	     it runs, and then only the setup those parts call for. -->
	<div v-else-if="board" class="flex h-full flex-col gap-3">
		<nav class="flex shrink-0 flex-wrap items-center gap-0.5 text-sm">
			<template v-for="(s, i) in board.stages" :key="s.key">
				<FeatherIcon v-if="i" name="chevron-right" class="size-3.5 shrink-0 text-ink-gray-4" />
				<button
					class="flex items-center gap-2 rounded-lg px-2.5 py-1.5 transition-colors"
					:class="
						s.key === stage ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-5 hover:bg-surface-gray-2'
					"
					@click="go(s.key)"
				>
					<span
						class="flex size-5 shrink-0 items-center justify-center rounded-full text-xs"
						:class="
							s.done
								? 'bg-surface-green-2 text-ink-green-3'
								: s.key === stage
									? 'bg-surface-gray-7 text-ink-white'
									: 'bg-surface-gray-3 text-ink-gray-6'
						"
					>
						<FeatherIcon v-if="s.done" name="check" class="size-3" />
						<template v-else>{{ i + 1 }}</template>
					</span>
					<span class="font-medium">{{ s.title }}</span>
					<span class="tabular-nums text-ink-gray-4">{{ s.answered }}/{{ s.total }}</span>
				</button>
			</template>
		</nav>

		<!-- ── Stage one: the company's own details, all on one screen ────── -->
		<section v-if="stage === 'Company'" class="mx-auto flex min-h-0 w-full max-w-4xl flex-1 flex-col">
			<div
				class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white"
			>
				<div class="min-h-0 flex-1 overflow-y-auto p-6">
					<h2 class="text-2xl font-semibold leading-snug text-ink-gray-9">Company details</h2>
					<p class="mt-2 text-base leading-relaxed text-ink-gray-6">
						The business itself, as it is registered. Everything in ERPNext hangs off this record.
					</p>

					<div class="ft-fill mt-5 grid gap-5 sm:grid-cols-2">
						<div v-for="q in companyQuestions" :key="q.key" :class="wideField(q) ? 'sm:col-span-2' : ''">
							<label class="block text-base font-medium leading-snug text-ink-gray-8">{{ q.label }}</label>
							<p v-if="q.description" class="mt-1 text-sm leading-relaxed text-ink-gray-5">
								{{ q.description }}
							</p>
							<div class="mt-2">
								<AnswerField v-model="form[q.key]" :question="q" />
							</div>
							<p v-if="q.from_site" class="mt-1.5 text-sm text-ink-gray-5">From your ERPNext site.</p>
							<p v-else-if="q.example" class="mt-1.5 font-mono text-sm text-ink-gray-4">e.g. {{ q.example }}</p>
						</div>
					</div>
				</div>

				<div class="flex shrink-0 items-center justify-between gap-3 border-t border-outline-gray-2 px-6 py-3">
					<p class="text-sm text-ink-gray-5">{{ filled }} of {{ companyQuestions.length }} filled in</p>
					<div class="flex items-center gap-2">
						<Button
							v-if="canApply('Company')"
							size="sm"
							variant="subtle"
							icon-left="play"
							:loading="applying"
							@click="applyTask(stageTasks('Company')[0].task)"
						>
							Create in ERPNext
						</Button>
						<Button size="sm" variant="solid" icon-right="chevron-right" :loading="saving" @click="saveForm()">
							Save and continue
						</Button>
					</div>
				</div>
			</div>
		</section>

		<!-- ── Stage two: which parts of ERPNext this business runs ───────── -->
		<section v-else-if="stage === 'Modules'" class="mx-auto flex min-h-0 w-full max-w-5xl flex-1 flex-col">
			<div
				class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white"
			>
				<div v-if="moduleQuestion" class="min-h-0 flex-1 overflow-y-auto p-6">
					<h2 class="text-2xl font-semibold leading-snug text-ink-gray-9">{{ moduleQuestion.label }}</h2>
					<p class="mt-2 text-base leading-relaxed text-ink-gray-6">{{ moduleQuestion.description }}</p>

					<div class="mt-6">
						<AnswerField v-model="modules" :question="moduleQuestion" layout="cards" />
					</div>
				</div>

				<div class="flex shrink-0 items-center justify-between gap-3 border-t border-outline-gray-2 px-6 py-3">
					<Button size="sm" variant="ghost" icon-left="chevron-left" @click="go('Company')">Back</Button>
					<div class="flex items-center gap-3">
						<p class="text-sm text-ink-gray-5">{{ moduleCount }} chosen</p>
						<Button
							size="sm"
							variant="solid"
							icon-right="chevron-right"
							:loading="saving"
							:disabled="!moduleCount"
							@click="saveModules()"
						>
							Save and continue
						</Button>
					</div>
				</div>
			</div>
		</section>

		<!-- ── Stage three: only what those modules call for ──────────────── -->
		<div v-else class="flex min-h-0 flex-1 gap-5">
			<aside class="hidden w-[23rem] shrink-0 flex-col lg:flex">
				<div
					class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white"
				>
					<div class="shrink-0 border-b border-outline-gray-2 px-4 py-4">
						<h1 class="text-lg font-semibold text-ink-gray-9">Setup questions</h1>
						<div class="mt-2 flex items-center justify-between gap-2">
							<span class="text-sm text-ink-gray-5">
								{{ setupStage.answered }} of {{ setupStage.total }} questions answered
							</span>
							<span class="shrink-0 text-sm font-medium text-ink-gray-7">{{ setupPercent }}%</span>
						</div>
						<div class="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-gray-2">
							<div
								class="h-full rounded-full bg-surface-gray-7 transition-all duration-300"
								:style="{ width: `${setupPercent}%` }"
							/>
						</div>
					</div>

					<nav class="min-h-0 flex-1 space-y-0.5 overflow-y-auto p-2">
						<div v-for="task in stageTasks('Setup')" :key="task.task">
							<button
								class="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left hover:bg-surface-gray-2"
								@click="toggle(task.task)"
							>
								<FeatherIcon
									:name="open === task.task ? 'chevron-down' : 'chevron-right'"
									class="size-4 shrink-0 text-ink-gray-4"
								/>
								<span
									class="min-w-0 flex-1 text-base font-medium leading-snug"
									:class="task.answered === task.total ? 'text-ink-gray-5' : 'text-ink-gray-8'"
								>
									{{ task.title }}
								</span>
								<FeatherIcon
									v-if="task.answered === task.total"
									name="check-circle"
									class="size-4 shrink-0 text-ink-green-3"
								/>
							</button>

							<ul v-if="open === task.task" class="ml-6 space-y-0.5 border-l border-outline-gray-2 pl-2">
								<li v-for="q in task.questions" :key="q.key">
									<button
										class="flex w-full items-start gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm leading-snug transition-colors"
										:class="
											q.key === current?.key
												? 'bg-surface-gray-3 font-medium text-ink-gray-9'
												: 'text-ink-gray-6 hover:bg-surface-gray-2'
										"
										@click="goTo(q.key)"
									>
										<FeatherIcon
											:name="q.answer ? 'check-circle' : 'circle'"
											class="mt-0.5 size-3.5 shrink-0"
											:class="q.answer ? 'text-ink-green-3' : 'text-ink-gray-4'"
										/>
										<span class="min-w-0 flex-1">{{ q.label }}</span>
									</button>
								</li>
							</ul>
						</div>
					</nav>
				</div>
			</aside>

			<section v-if="current" class="mx-auto flex min-h-0 w-full min-w-0 max-w-4xl flex-1 flex-col">
				<div
					class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white"
				>
					<div class="min-h-0 flex-1 overflow-y-auto p-6">
						<Badge theme="gray" size="sm" :label="`Question ${position} of ${setupStage.total}`" />

						<h2 class="mt-3 text-2xl font-semibold leading-snug text-ink-gray-9">{{ current.label }}</h2>
						<p v-if="current.description" class="mt-2 text-base leading-relaxed text-ink-gray-6">
							{{ current.description }}
						</p>

						<div v-if="current.doctype || currentTask.doctype" class="mt-4 flex flex-wrap items-center gap-2">
							<span class="text-sm text-ink-gray-5">Doctype:</span>
							<Badge theme="blue" size="sm" :label="current.doctype || currentTask.doctype" />
							<span v-if="current.field" class="font-mono text-sm text-ink-gray-5">{{ current.field }}</span>
						</div>

						<!-- Taken from the site, not asked for. Said plainly, because
						     an answer nobody gave is one nobody has checked. -->
						<div
							v-if="current.from_site"
							class="mt-4 flex items-start gap-2 rounded-lg border border-outline-gray-2 bg-surface-gray-1 px-3 py-2"
						>
							<FeatherIcon name="download" class="mt-0.5 size-3.5 shrink-0 text-ink-gray-5" />
							<p class="text-sm leading-relaxed text-ink-gray-6">
								ERPNext already had this, so it is filled in from your site. Change it if it is wrong.
							</p>
						</div>

						<div
							v-if="current.example"
							class="mt-5 rounded-lg border border-outline-gray-2 bg-surface-gray-1 px-4 py-3"
						>
							<p class="text-sm font-medium text-ink-gray-5">Example</p>
							<p class="mt-1 font-mono text-base text-ink-gray-8">{{ current.example }}</p>
						</div>

						<div class="mt-6">
							<p class="text-sm font-medium uppercase tracking-wide text-ink-gray-5">Your answer</p>
							<div class="ft-fill mt-2">
								<AnswerField v-model="draft" :question="current" @enter="next()" />
							</div>
						</div>

						<div
							v-if="lastCheck?.ready"
							class="mt-6 rounded-lg border border-outline-gray-2 bg-surface-gray-1 px-4 py-3"
						>
							<div class="flex items-start gap-2">
								<FeatherIcon name="shield" class="mt-0.5 size-4 shrink-0 text-ink-gray-5" />
								<div class="min-w-0">
									<p class="text-base font-medium text-ink-gray-8">{{ lastCheck.about_to }}</p>
									<ul class="mt-1.5 space-y-1">
										<li v-for="(reason, i) in lastCheck.safe_because" :key="i" class="text-sm text-ink-gray-6">
											{{ reason }}
										</li>
									</ul>
								</div>
							</div>
						</div>

						<div v-if="lastRecord" class="mt-6 overflow-hidden rounded-lg border border-outline-green-2">
							<div class="flex items-center gap-2 border-b border-outline-green-2 bg-surface-green-1 px-3 py-2">
								<FeatherIcon name="check-circle" class="size-4 shrink-0 text-ink-green-3" />
								<span class="min-w-0 flex-1 truncate text-sm font-semibold text-ink-green-3">
									{{ lastRecord.doctype }} {{ lastRecord.name }} is in ERPNext
								</span>
								<a :href="lastRecord.url" target="_blank" rel="noopener">
									<Button size="sm" variant="ghost" icon-right="external-link" label="Open" />
								</a>
							</div>
						</div>
					</div>

					<div class="flex shrink-0 items-center justify-between border-t border-outline-gray-2 px-6 py-3">
						<Button size="sm" variant="ghost" icon-left="chevron-left" @click="previous()">
							{{ position === 1 ? "Back to modules" : "Previous" }}
						</Button>
						<div class="flex items-center gap-2">
							<Button
								v-if="writes(currentTask) && currentTask.answered === currentTask.total && isStaff"
								size="sm"
								variant="subtle"
								icon-left="play"
								:loading="applying"
								@click="applyTask(currentTask.task)"
							>
								Create in ERPNext
							</Button>
							<Button
								size="sm"
								variant="solid"
								icon-right="chevron-right"
								:loading="saving"
								:disabled="position === setupStage.total"
								@click="next()"
							>
								Next
							</Button>
						</div>
					</div>
				</div>
			</section>

			<section v-else class="flex flex-1 items-center justify-center">
				<p class="max-w-md text-center text-base text-ink-gray-5">
					The modules you chose need no further setup. Go back a stage to add one.
				</p>
			</section>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, watch } from "vue"
import { Badge, Button, FeatherIcon, LoadingIndicator, toast } from "frappe-ui"

import AnswerField from "../components/AnswerField.vue"
import { api, errorText } from "../data/api"
import { showInErpnext, state } from "../data/store"

const board = ref(null)
const loading = ref(true)
const saving = ref(false)
const applying = ref(false)
const stage = ref("Company")
const open = ref("")
const at = ref(0)
const draft = ref("")
const form = ref({})
const modules = ref("")
const lastRecord = ref(null)
const lastCheck = ref(null)

const isStaff = computed(() => state.overview?.is_staff)

function stageTasks(key) {
	return (board.value?.tasks || []).filter((t) => t.stage === key)
}

function stageOf(key) {
	return (board.value?.stages || []).find((s) => s.key === key) || { answered: 0, total: 0, done: false }
}

// ── Stage one: the company's own details ───────────────────────────────────
const companyQuestions = computed(() => stageTasks("Company").flatMap((t) => t.questions))
const filled = computed(() => companyQuestions.value.filter((q) => (form.value[q.key] || "").trim()).length)

/** An answer that is a sentence gets the whole row; the short ones pair up. */
function wideField(q) {
	return q.type === "Multiple Choice" || /name|address/i.test(q.field || "")
}

// ── Stage two: the modules ─────────────────────────────────────────────────
const moduleQuestion = computed(() => stageTasks("Modules").flatMap((t) => t.questions)[0] || null)
const moduleCount = computed(() => modules.value.split(",").filter((v) => v.trim()).length)

// ── Stage three: what those modules call for ───────────────────────────────
const setupStage = computed(() => stageOf("Setup"))
const setupPercent = computed(() =>
	setupStage.value.total ? Math.round((100 * setupStage.value.answered) / setupStage.value.total) : 0
)
/** Every setup question in order, so Previous and Next walk the whole stage. */
const flat = computed(() => stageTasks("Setup").flatMap((t) => t.questions.map((q) => ({ ...q, task: t.task }))))
const current = computed(() => flat.value[at.value] || null)
const position = computed(() => at.value + 1)
const currentTask = computed(
	() => (board.value?.tasks || []).find((t) => t.task === current.value?.task) || { questions: [] }
)

/** A step writes something if it, or any of its questions, names a record. */
function writes(task) {
	return Boolean(task?.doctype || (task?.questions || []).some((q) => q.doctype))
}

function canApply(key) {
	const task = stageTasks(key)[0]
	return isStaff.value && writes(task) && task.answered === task.total
}

async function load() {
	loading.value = true
	try {
		board.value = await api("wizard", { onboarding: state.id })
		fillForm()
		// Pick up at the first stage that is not finished.
		stage.value = (board.value.stages || []).find((s) => !s.done)?.key || "Setup"
		const firstUnanswered = flat.value.findIndex((q) => !q.answer)
		at.value = firstUnanswered >= 0 ? firstUnanswered : 0
		open.value = current.value?.task || stageTasks("Setup")[0]?.task || ""
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		loading.value = false
	}
}

/** The form and the module picker start from what was answered before. */
function fillForm() {
	form.value = Object.fromEntries(companyQuestions.value.map((q) => [q.key, q.answer || ""]))
	modules.value = moduleQuestion.value?.answer || ""
}

function go(key) {
	stage.value = key
	if (key === "Setup" && !current.value) at.value = 0
}

function toggle(task) {
	open.value = open.value === task ? "" : task
}

function goTo(key) {
	const i = flat.value.findIndex((q) => q.key === key)
	if (i >= 0) at.value = i
}

watch(current, (q) => {
	draft.value = q?.answer || ""
	lastCheck.value = null
	if (q) open.value = q.task
})

watch(currentTask, async (task) => {
	if (!task?.task || !writes(task) || task.answered !== task.total || !isStaff.value) return
	try {
		lastCheck.value = await api("wizard_check", { onboarding: state.id, task: task.task })
	} catch {
		lastCheck.value = null
	}
})

async function saveForm() {
	saving.value = true
	try {
		board.value = await api("wizard_answers", {
			onboarding: state.id,
			answers: JSON.stringify(form.value),
		})
		fillForm()
		go("Modules")
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		saving.value = false
	}
}

async function saveModules() {
	saving.value = true
	try {
		board.value = await api("wizard_answer", {
			onboarding: state.id,
			question: moduleQuestion.value.key,
			value: modules.value,
		})
		fillForm()
		// The questions ahead are decided here, so start at the first one open.
		const firstUnanswered = flat.value.findIndex((q) => !q.answer)
		at.value = firstUnanswered >= 0 ? firstUnanswered : 0
		go("Setup")
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		saving.value = false
	}
}

async function save() {
	if (!current.value || draft.value === (current.value.answer || "")) return
	saving.value = true
	try {
		board.value = await api("wizard_answer", {
			onboarding: state.id,
			question: current.value.key,
			value: draft.value,
		})
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		saving.value = false
	}
}

async function next() {
	await save()
	if (at.value < flat.value.length - 1) at.value += 1
}

async function previous() {
	await save()
	if (at.value > 0) {
		at.value -= 1
		return
	}
	// The first setup question follows from the modules, so back goes there.
	go("Modules")
}

async function applyTask(task) {
	applying.value = true
	try {
		const out = await api("wizard_apply", { onboarding: state.id, task })
		board.value = out.board
		lastRecord.value = out.record
		lastCheck.value = null
		// The live pane on Ask opens on whatever was just written, so the
		// record is waiting there rather than having to be gone and found.
		if (out.record?.url) showInErpnext(out.record.url)
		toast.success(`${out.record.doctype} ${out.record.name} is in ERPNext`)
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		applying.value = false
	}
}

load()
</script>
