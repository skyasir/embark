<template>
	<div v-if="loading" class="flex justify-center py-24">
		<LoadingIndicator class="size-6 text-ink-gray-5" />
	</div>

	<div v-else-if="board" class="flex h-full gap-6">
		<!-- ── The whole setup, grouped by what it builds ─────────────── -->
		<aside class="hidden w-72 shrink-0 overflow-y-auto lg:block">
			<div class="pb-6">
				<h1 class="text-xl font-semibold text-ink-gray-9">Setup Wizard</h1>
				<div class="mt-2 flex items-center justify-between">
					<span class="text-sm text-ink-gray-5">
						{{ board.answered }} of {{ board.total }} questions answered
					</span>
					<span class="text-sm font-medium text-ink-gray-7">{{ board.percent }}% Done</span>
				</div>
				<div class="mt-2 h-1 overflow-hidden rounded-full bg-surface-gray-2">
					<div
						class="h-full rounded-full bg-surface-gray-7 transition-all duration-300"
						:style="{ width: `${board.percent}%` }"
					/>
				</div>
			</div>

			<nav class="space-y-1">
				<div v-for="task in board.tasks" :key="task.task">
					<button
						class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-surface-gray-1"
						@click="toggle(task.task)"
					>
						<FeatherIcon
							:name="open === task.task ? 'chevron-down' : 'chevron-right'"
							class="size-3.5 shrink-0 text-ink-gray-4"
						/>
						<span
							class="min-w-0 flex-1 truncate text-base"
							:class="task.answered === task.total ? 'text-ink-gray-5' : 'text-ink-gray-8'"
						>
							{{ task.title }}
						</span>
						<FeatherIcon
							v-if="task.answered === task.total"
							name="check-circle"
							class="size-3.5 shrink-0 text-ink-green-3"
						/>
					</button>

					<ul v-if="open === task.task" class="ml-5 space-y-0.5 border-l border-outline-gray-2 pl-2">
						<li v-for="q in task.questions" :key="q.key">
							<button
								class="flex w-full items-start gap-2 rounded px-2 py-1 text-left text-sm transition-colors"
								:class="
									q.key === current?.key
										? 'bg-surface-gray-2 text-ink-gray-9'
										: 'text-ink-gray-5 hover:bg-surface-gray-1'
								"
								@click="goTo(q.key)"
							>
								<FeatherIcon
									:name="q.answer ? 'check-circle' : 'circle'"
									class="mt-0.5 size-3 shrink-0"
									:class="q.answer ? 'text-ink-green-3' : 'text-ink-gray-4'"
								/>
								<span class="min-w-0 flex-1 truncate">{{ q.label }}</span>
							</button>
						</li>
					</ul>
				</div>
			</nav>
		</aside>

		<!-- ── One question at a time ──────────────────────────────────── -->
		<section v-if="current" class="min-w-0 flex-1 overflow-y-auto">
			<div class="mx-auto max-w-3xl pb-10">
				<Badge theme="gray" size="sm" :label="`Question ${position} of ${board.total}`" />

				<h2 class="mt-3 text-2xl font-semibold leading-snug text-ink-gray-9">{{ current.label }}</h2>
				<p v-if="current.description" class="mt-2 text-base leading-relaxed text-ink-gray-6">
					{{ current.description }}
				</p>

				<div v-if="currentTask.doctype" class="mt-4 flex flex-wrap items-center gap-2">
					<span class="text-sm text-ink-gray-5">Doctype:</span>
					<Badge theme="blue" size="md" :label="currentTask.doctype" />
					<span v-if="current.field" class="font-mono text-sm text-ink-gray-5">{{ current.field }}</span>
				</div>

				<div
					v-if="current.example"
					class="mt-5 rounded-lg border border-outline-gray-2 bg-surface-gray-1 px-4 py-3"
				>
					<p class="text-sm font-medium text-ink-gray-5">Example</p>
					<p class="mt-0.5 font-mono text-base text-ink-gray-8">{{ current.example }}</p>
				</div>

				<div class="mt-6">
					<p class="text-sm font-medium uppercase tracking-wide text-ink-gray-5">Your answer</p>
					<div class="ft-fill mt-2">
						<select
							v-if="current.type === 'Select'"
							v-model="draft"
							class="w-full rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-2 text-base text-ink-gray-8"
						>
							<option value="">Choose…</option>
							<option v-for="c in current.choices" :key="c.value" :value="c.value">{{ c.label }}</option>
						</select>
						<select
							v-else-if="current.type === 'Yes / No'"
							v-model="draft"
							class="w-full rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-2 text-base text-ink-gray-8"
						>
							<option value="">Choose…</option>
							<option value="Yes">Yes</option>
							<option value="No">No</option>
						</select>

						<!-- Several answers at once: one row each, pressed on and off. -->
						<div v-else-if="picker.length" class="space-y-2">
							<button
								v-for="(choice, i) in picker"
								:key="choice.value"
								class="flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors"
								:class="
									isPicked(choice.value)
										? 'border-outline-gray-4 bg-surface-gray-2 text-ink-gray-9'
										: 'border-outline-gray-2 text-ink-gray-7 hover:bg-surface-gray-1'
								"
								@click="pick(choice.value)"
							>
								<span
									class="flex size-5 shrink-0 items-center justify-center rounded border text-xs"
									:class="
										isPicked(choice.value)
											? 'border-outline-gray-5 bg-surface-gray-7 text-ink-white'
											: 'border-outline-gray-3 text-ink-gray-4'
									"
								>
									<FeatherIcon v-if="isPicked(choice.value)" name="check" class="size-3" />
									<template v-else-if="i < 9">{{ i + 1 }}</template>
								</span>
								<span class="min-w-0 flex-1">{{ choice.label }}</span>
							</button>
							<p class="pt-1 text-sm text-ink-gray-5">
								Pick as many as apply. {{ picked.length }} chosen.
							</p>
						</div>
						<Autocomplete
							v-else-if="current.type === 'Link'"
							:options="linkOptions"
							:model-value="draft"
							placeholder="Start typing…"
							@update:model-value="(v) => (draft = v?.value ?? '')"
						/>
						<FormControl
							v-else
							v-model="draft"
							:type="current.type === 'Date' ? 'date' : current.type === 'Number' ? 'number' : 'text'"
							placeholder="Enter your answer..."
							@keydown.enter="next()"
						/>
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
							<ul class="mt-1 space-y-0.5">
								<li v-for="(reason, i) in lastCheck.safe_because" :key="i" class="text-sm text-ink-gray-6">
									{{ reason }}
								</li>
							</ul>
						</div>
					</div>
				</div>

				<div
					v-if="lastRecord"
					class="mt-6 overflow-hidden rounded-lg border border-outline-green-2"
				>
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

				<div class="mt-8 flex items-center justify-between">
					<Button variant="ghost" icon-left="chevron-left" :disabled="position === 1" @click="previous()">
						Previous
					</Button>
					<div class="flex items-center gap-2">
						<Button
							v-if="currentTask.answered === currentTask.total && isStaff"
							variant="subtle"
							icon-left="play"
							:loading="applying"
							@click="applyTask()"
						>
							Create in ERPNext
						</Button>
						<Button variant="solid" icon-right="chevron-right" :loading="saving" @click="next()">
							Next
						</Button>
					</div>
				</div>
			</div>
		</section>

	</div>
</template>

<script setup>
import { computed, ref, watch } from "vue"
import { Autocomplete, Badge, Button, FeatherIcon, FormControl, LoadingIndicator, toast } from "frappe-ui"

import { api, errorText } from "../data/api"
import { state } from "../data/store"

const board = ref(null)
const loading = ref(true)
const saving = ref(false)
const applying = ref(false)
const open = ref("")
const at = ref(0)
const draft = ref("")
const lastRecord = ref(null)
const lastCheck = ref(null)
const linkOptions = ref([])

const isStaff = computed(() => state.overview?.is_staff)

/** Only a question that takes several answers is a list of rows. */
const picker = computed(() => (current.value?.type === "Multiple Choice" ? current.value.choices : []))
const picked = computed(() => (draft.value || "").split(",").map((v) => v.trim()).filter(Boolean))

function isPicked(value) {
	return picked.value.includes(value)
}

function pick(value) {
	// A second press takes it off again, so nothing is a one-way door.
	const now = isPicked(value) ? picked.value.filter((v) => v !== value) : [...picked.value, value]
	draft.value = now.join(",")
}

/** Every question in order, so Previous and Next walk the whole wizard. */
const flat = computed(() => (board.value?.tasks || []).flatMap((t) => t.questions.map((q) => ({ ...q, task: t.task }))))
const current = computed(() => flat.value[at.value] || null)
const position = computed(() => at.value + 1)
const currentTask = computed(
	() => (board.value?.tasks || []).find((t) => t.task === current.value?.task) || { questions: [] },
)

async function load() {
	loading.value = true
	try {
		board.value = await api("wizard", { onboarding: state.id })
		const firstUnanswered = flat.value.findIndex((q) => !q.answer)
		at.value = firstUnanswered >= 0 ? firstUnanswered : 0
		open.value = current.value?.task || board.value.tasks[0]?.task || ""
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		loading.value = false
	}
}

function toggle(task) {
	open.value = open.value === task ? "" : task
}

function goTo(key) {
	const i = flat.value.findIndex((q) => q.key === key)
	if (i >= 0) at.value = i
}

/** A Link question offers what the site actually has. */
async function loadLinks() {
	linkOptions.value = []
	if (current.value?.type !== "Link" || !current.value.link_doctype) return
	try {
		const rows = await api("suggestions", { doctype: current.value.link_doctype })
		linkOptions.value = (rows || []).map((name) => ({ label: name, value: name }))
	} catch {
		linkOptions.value = []
	}
}

watch(current, async (q) => {
	draft.value = q?.answer || ""
	lastCheck.value = null
	await loadLinks()
	if (q) open.value = q.task
})

watch(currentTask, async (task) => {
	if (!task?.task || task.answered !== task.total || !isStaff.value) return
	try {
		lastCheck.value = await api("wizard_check", { onboarding: state.id, task: task.task })
	} catch {
		lastCheck.value = null
	}
})

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
	if (at.value > 0) at.value -= 1
}

async function applyTask() {
	applying.value = true
	try {
		const out = await api("wizard_apply", { onboarding: state.id, task: currentTask.value.task })
		board.value = out.board
		lastRecord.value = out.record
		lastCheck.value = null
		toast.success(`${out.record.doctype} ${out.record.name} is in ERPNext`)
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		applying.value = false
	}
}

load()
</script>
