<template>
	<div v-if="loading" class="flex justify-center py-24">
		<LoadingIndicator class="size-6 text-ink-gray-5" />
	</div>

	<div v-else-if="data" class="space-y-6">
		<Stepper v-if="data.upload" :steps="wizard" :current="step" @select="step = $event" />

		<Callout v-if="data.locked" tone="info">Your data is with your consultant, so it can't be changed now.</Callout>

		<!-- 1. Give us the data, whichever way suits the list. -->
		<section v-if="step === 0" class="space-y-6">
			<div>
				<p class="text-sm font-medium uppercase tracking-wide text-ink-gray-4">
					Step {{ position }} of {{ o?.steps.length || 0 }}
				</p>
				<h1 class="mt-1 text-2xl font-semibold leading-snug text-ink-gray-9">{{ data.area.name }}</h1>
				<p class="mt-2 text-base leading-relaxed text-ink-gray-6">
					{{ data.area.description }}
					<template v-if="data.area.because"> We ask because {{ data.area.because }}.</template>
					<template v-if="!data.area.required"> You can skip this one.</template>
				</p>
			</div>

			<Callout v-if="data.area.help_text">{{ data.area.help_text }}</Callout>

			<!-- Two ways in. The short list is typed; the long one is a file. -->
			<div v-if="!data.locked && !mode" class="grid gap-3 sm:grid-cols-2">
				<button
					class="rounded-lg border border-outline-gray-2 p-4 text-left transition-colors hover:border-outline-gray-3 hover:bg-surface-gray-1"
					@click="startTyping"
				>
					<FeatherIcon name="edit-3" class="size-5 text-ink-gray-6" />
					<div class="mt-2 text-base font-medium text-ink-gray-9">Type them in</div>
					<div class="mt-1 text-base text-ink-gray-6">
						Quickest for a short list. We'll show you the columns.
					</div>
				</button>
				<button
					class="rounded-lg border border-outline-gray-2 p-4 text-left transition-colors hover:border-outline-gray-3 hover:bg-surface-gray-1"
					@click="mode = 'file'"
				>
					<FeatherIcon name="upload-cloud" class="size-5 text-ink-gray-6" />
					<div class="mt-2 text-base font-medium text-ink-gray-9">Upload a spreadsheet</div>
					<div class="mt-1 text-base text-ink-gray-6">
						Use the file you already keep, or our template. Any layout works.
					</div>
				</button>
			</div>

			<div v-if="!data.locked && mode" class="flex items-center gap-2">
				<Button variant="ghost" size="sm" icon-left="chevron-left" @click="mode = ''">Other way</Button>
				<span class="text-base text-ink-gray-6">
					{{ mode === "type" ? "Typing them in" : "Uploading a spreadsheet" }}
				</span>
			</div>

			<div v-if="!data.locked && mode === 'type'" class="space-y-3">
				<div class="overflow-x-auto rounded-lg border border-outline-gray-2">
					<table class="w-full text-left text-base">
						<thead class="bg-surface-gray-1 text-ink-gray-6">
							<tr>
								<th v-for="c in data.columns" :key="c.fieldname" class="px-3 py-2">
									<span class="font-medium">{{ c.label }}</span>
									<span v-if="c.required" class="text-ink-red-3"> *</span>
									<span class="block text-sm font-normal text-ink-gray-4">{{ kindOf(c) }}</span>
								</th>
								<th class="w-10 px-2 py-2" />
							</tr>
						</thead>
						<tbody class="divide-y divide-outline-gray-1">
							<tr v-for="(row, i) in typed" :key="i">
								<!-- Each cell is what the field actually is: a yes/no, a list of
								     choices, a date, a number, or a link with what exists to pick. -->
								<td v-for="c in data.columns" :key="c.fieldname" class="px-1 py-1">
									<select
										v-if="c.fieldtype === 'Check' || c.choices.length"
										v-model="row[c.fieldname]"
										class="w-full rounded border-0 bg-transparent px-2 py-1.5 text-base text-ink-gray-8 focus:bg-surface-gray-1 focus:outline-none"
									>
										<option value="">—</option>
										<option v-for="option in cellOptions(c)" :key="option" :value="option">
											{{ option }}
										</option>
									</select>
									<template v-else>
										<input
											v-model="row[c.fieldname]"
											:type="inputType(c)"
											:list="c.link_doctype ? `list-${c.fieldname}` : undefined"
											:maxlength="c.max_length || undefined"
											class="w-full rounded border-0 bg-transparent px-2 py-1.5 text-base text-ink-gray-8 placeholder:text-ink-gray-4 focus:bg-surface-gray-1 focus:outline-none"
											:placeholder="i === 0 ? c.example || '' : ''"
											@keydown.enter.prevent="addRow(i)"
										/>
										<datalist v-if="c.link_doctype" :id="`list-${c.fieldname}`">
											<option v-for="option in suggestionsFor(c)" :key="option" :value="option" />
										</datalist>
									</template>
								</td>
								<td class="px-1 py-1">
									<Button
										v-if="typed.length > 1"
										variant="ghost"
										size="sm"
										icon="x"
										label="Remove row"
										@click="typed.splice(i, 1)"
									/>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
				<div class="flex items-center justify-between">
					<Button size="md" variant="ghost" icon-left="plus" @click="addRow()">Add a row</Button>
					<Button variant="solid" size="md" :loading="busy" :disabled="!hasTyped" @click="saveTyped">
						Save {{ filledCount }} {{ filledCount === 1 ? "row" : "rows" }}
					</Button>
				</div>
			</div>

			<div v-if="!data.locked && mode === 'file'" class="space-y-3">
				<div class="flex flex-wrap gap-2">
					<Button size="md" icon-left="download" @click="downloadTemplate">Download our template</Button>
					<Button
						size="md"
						variant="ghost"
						:icon-right="showColumns ? 'chevron-up' : 'chevron-down'"
						@click="showColumns = !showColumns"
					>
						Columns we look for
					</Button>
				</div>
				<div v-if="showColumns" class="overflow-x-auto rounded-lg border border-outline-gray-2">
					<table class="w-full text-left text-base">
						<thead class="bg-surface-gray-1 text-ink-gray-6">
							<tr>
								<th class="px-3 py-2 font-medium">Column</th>
								<th class="px-3 py-2 font-medium">What to enter</th>
								<th class="px-3 py-2 font-medium">Example</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-outline-gray-1">
							<tr v-for="c in data.columns" :key="c.fieldname">
								<td class="whitespace-nowrap px-3 py-2 font-medium text-ink-gray-8">
									{{ c.label }}<span v-if="c.required" class="text-ink-red-3"> *</span>
								</td>
								<td class="px-3 py-2 text-ink-gray-6">{{ describe(c) }}</td>
								<td class="whitespace-nowrap px-3 py-2 text-ink-gray-6">{{ c.example }}</td>
							</tr>
						</tbody>
					</table>
				</div>
				<label
					class="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors"
					:class="dragging ? 'border-outline-gray-5 bg-surface-gray-1' : 'border-outline-gray-2 hover:bg-surface-gray-1'"
					@dragover.prevent="dragging = true"
					@dragleave.prevent="dragging = false"
					@drop.prevent="onDrop"
				>
					<input ref="picker" type="file" class="sr-only" :accept="ACCEPT" @change="onPick" />
					<template v-if="uploading">
						<LoadingIndicator class="size-5 text-ink-gray-5" />
						<span class="text-base text-ink-gray-7">Reading your file… {{ progress }}%</span>
					</template>
					<template v-else>
						<FeatherIcon name="upload-cloud" class="size-6 text-ink-gray-5" />
						<span class="text-base font-medium text-ink-gray-8">
							{{ data.upload ? "Drop a new file to replace it" : "Drop your file here, or click to choose" }}
						</span>
						<span class="text-sm text-ink-gray-5">Excel (.xlsx, .xls) or CSV</span>
					</template>
				</label>
			</div>

			<Callout v-if="data.upload" tone="success">
				<strong>File read successfully.</strong>
				We found {{ data.upload.rows }} {{ data.upload.rows === 1 ? "row" : "rows" }} in
				<span class="font-medium">{{ data.upload.file_name }}</span>.
				<button v-if="!data.locked" class="ml-1 text-ink-gray-6 underline hover:text-ink-gray-9" @click="remove">
					Remove it
				</button>
			</Callout>

			<div class="flex justify-between">
				<Button size="md" icon-left="chevron-left" @click="$router.push({ name: 'home' })">Overview</Button>
				<Button v-if="data.upload" variant="solid" size="md" icon-right="chevron-right" @click="step = 1">Continue</Button>
			</div>
		</section>

		<!-- 2. Match columns -->
		<section v-else-if="step === 1 && data.upload" class="space-y-6">
			<div>
				<h1 class="text-2xl font-semibold text-ink-gray-9">Does this look right?</h1>
				<p class="mt-2 text-base leading-relaxed text-ink-gray-6">
					We worked out what each of your columns is. Change any we got wrong — then we'll check the
					rows themselves.
				</p>
			</div>

			<Callout v-if="missingColumns.length" tone="warning">
				<strong>Still needed:</strong> {{ missingColumns.join(", ") }}. Choose which of your columns holds
				{{ missingColumns.length === 1 ? "it" : "them" }}, or add
				{{ missingColumns.length === 1 ? "it" : "them" }} to your file and upload it again.
			</Callout>

			<div class="ft-fill overflow-x-auto rounded-lg border border-outline-gray-2">
				<table class="w-full text-left text-base">
					<thead class="bg-surface-gray-1 text-ink-gray-6">
						<tr>
							<th class="px-3 py-2 font-medium">Column in your file</th>
							<th class="px-3 py-2 font-medium">Examples</th>
							<th class="w-60 px-3 py-2 font-medium">Goes into</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-outline-gray-1">
						<tr v-for="h in data.upload.headers" :key="h.header">
							<td class="px-3 py-2 font-medium text-ink-gray-8">{{ h.header }}</td>
							<td class="max-w-56 truncate px-3 py-2 text-ink-gray-5">{{ h.samples.join(", ") || "—" }}</td>
							<td class="px-3 py-1.5">
								<FormControl
									type="select"
									:model-value="h.fieldname || ''"
									:options="fieldOptions"
									:disabled="data.locked || busy"
									@update:model-value="(v) => mapColumn(h.header, v)"
								/>
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<div class="flex justify-between">
				<Button size="md" icon-left="chevron-left" @click="step = 0">Back</Button>
				<Button variant="solid" size="md" icon-right="chevron-right" @click="step = 2">Continue</Button>
			</div>
		</section>

		<!-- 3. Check -->
		<section v-else-if="step === 2 && data.upload" class="space-y-6">
			<div>
				<h1 class="text-2xl font-semibold text-ink-gray-9">Check your data</h1>
				<p class="mt-2 text-base leading-relaxed text-ink-gray-6">
					<template v-if="data.locked">How your data checked out against ERPNext's rules.</template>
					<template v-else>
						We checked every row against ERPNext's rules. Fix anything below right here, or go back and
						change what you gave us. Nothing you uploaded is ever altered.
					</template>
				</p>
			</div>

			<div class="grid grid-cols-3 gap-3">
				<StatTile :value="data.upload.rows" label="Rows" theme="green" />
				<StatTile :value="data.upload.errors" label="Errors" theme="red" />
				<StatTile :value="data.upload.warnings" label="Warnings" theme="blue" />
			</div>

			<Callout v-if="!data.upload.errors" tone="success">
				<strong>Everything checks out.</strong>
				{{ data.upload.rows }} {{ data.upload.rows === 1 ? "row is" : "rows are" }} ready for ERPNext.
				<template v-if="data.upload.warnings">The warnings below are worth a look but won't hold you up.</template>
			</Callout>

			<div v-if="data.upload.groups.length" class="space-y-3">
				<IssueGroup
					v-for="g in data.upload.groups"
					:key="`${g.code}-${g.fieldname}`"
					:group="g"
					:issues="issuesFor(g)"
					:column="columnFor(g.fieldname)"
					:locked="data.locked"
					:busy="busy"
					@fix="fix"
					@match="step = 1"
				/>
			</div>

			<div>
				<button
					class="flex w-full items-center justify-between gap-3 rounded-lg border border-outline-gray-2 px-4 py-3 text-left text-base text-ink-gray-8 transition-colors hover:bg-surface-gray-1"
					@click="showPreview = !showPreview"
				>
					<span>
						{{ showPreview ? "Hide" : "Show" }} what ERPNext will receive
						<span class="text-ink-gray-5">
							· {{ previewCount }} of {{ data.upload.rows }}
							{{ data.upload.rows === 1 ? "row" : "rows" }}
						</span>
					</span>
					<FeatherIcon :name="showPreview ? 'chevron-down' : 'chevron-right'" class="size-4 shrink-0 text-ink-gray-5" />
				</button>
				<div v-if="showPreview" class="mt-2 overflow-x-auto rounded-lg border border-outline-gray-2">
					<table class="w-full text-left text-sm">
						<thead class="bg-surface-gray-1 text-ink-gray-6">
							<tr>
								<th class="px-3 py-2 font-medium">Row</th>
								<th v-for="c in data.upload.preview.columns" :key="c.fieldname" class="whitespace-nowrap px-3 py-2 font-medium">
									{{ c.label }}
								</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-outline-gray-1">
							<tr v-for="r in data.upload.preview.rows" :key="r._row">
								<td class="px-3 py-1.5 tabular-nums text-ink-gray-5">{{ r._row }}</td>
								<td v-for="c in data.upload.preview.columns" :key="c.fieldname" class="whitespace-nowrap px-3 py-1.5 text-ink-gray-8">
									{{ show(r[c.fieldname], c.fieldname) }}
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>

			<div class="flex justify-between">
				<Button size="md" icon-left="chevron-left" @click="step = 1">Back</Button>
				<Button variant="solid" size="md" icon-right="chevron-right" @click="goNext">
					{{ nextStep ? `Next: ${nextStep.area}` : "Back to overview" }}
				</Button>
			</div>
		</section>
	</div>
</template>

<script setup>
import { computed, ref, watch } from "vue"
import { useRouter } from "vue-router"
import { Button, FeatherIcon, FormControl, LoadingIndicator, toast } from "frappe-ui"

import Callout from "../components/Callout.vue"
import IssueGroup from "../components/IssueGroup.vue"
import StatTile from "../components/StatTile.vue"
import Stepper from "../components/Stepper.vue"
import { api, errorText, templateUrl, uploadFile } from "../data/api"
import { loadOverview, state } from "../data/store"

const props = defineProps({ area: { type: String, required: true } })
const router = useRouter()

const ACCEPT = ".xlsx,.xls,.csv"
const data = ref(null)
const loading = ref(true)
const step = ref(0)
const busy = ref(false)
const uploading = ref(false)
const progress = ref(0)
const dragging = ref(false)
const showColumns = ref(false)
const mode = ref("")
const typed = ref([])
const showPreview = ref(false)
const picker = ref(null)

const previewCount = computed(() => data.value?.upload?.preview.rows.length || 0)

const filled = computed(() =>
	typed.value.filter((row) => Object.values(row).some((v) => (v || "").toString().trim()))
)
const filledCount = computed(() => filled.value.length)
const hasTyped = computed(() => filledCount.value > 0)

const missingColumns = computed(() =>
	(data.value?.upload?.groups || []).filter((g) => g.code === "COLUMN_MISSING").map((g) => g.label)
)

const wizard = computed(() => {
	const up = data.value?.upload
	return [
		{ label: "Your data", done: !!up, reachable: true },
		{ label: "Columns", done: !!up && !missingColumns.value.length, reachable: !!up },
		{ label: "Check", done: !!up && up.errors === 0, reachable: !!up },
	]
})

const fieldOptions = computed(() => [
	{ label: "Don't use", value: "" },
	...data.value.columns.map((c) => ({ label: c.label + (c.required ? " *" : ""), value: c.fieldname })),
])

const o = computed(() => state.overview)
const position = computed(
	() => (o.value?.steps || []).findIndex((s) => s.area === props.area) + 1
)

const nextStep = computed(() => {
	const steps = state.overview?.steps || []
	const i = steps.findIndex((s) => s.area === props.area)
	return steps.slice(i + 1).find((s) => s.status !== "Ready") || null
})

async function load() {
	loading.value = true
	try {
		data.value = await api("get_area", { onboarding: state.id, area: props.area })
		step.value = data.value.upload ? (missingColumns.value.length ? 1 : 2) : 0
	} catch (e) {
		toast.error(errorText(e))
		router.push({ name: "home" })
	} finally {
		loading.value = false
	}
}

async function run(method, args, message) {
	busy.value = true
	try {
		data.value = await api(method, { onboarding: state.id, area: props.area, ...args })
		if (message) toast.success(message)
		loadOverview()
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		busy.value = false
	}
}

/** A cell is the field it stands for: yes/no, a choice, a date, a number. */
function inputType(c) {
	if (c.fieldtype === "Date") return "date"
	if (["Int", "Float", "Currency", "Percent"].includes(c.fieldtype)) return "number"
	if (c.fieldtype === "Email") return "email"
	return "text"
}

function kindOf(c) {
	if (c.fieldtype === "Check") return "Yes or No"
	if (c.choices.length) return c.choices.slice(0, 3).join(" / ") + (c.choices.length > 3 ? "…" : "")
	if (c.link_doctype) return `An existing ${c.link_doctype.toLowerCase()}`
	if (["Int", "Float", "Currency", "Percent"].includes(c.fieldtype)) return "A number"
	if (c.fieldtype === "Date") return "A date"
	if (c.fieldtype === "Email") return "An email"
	return ""
}

function cellOptions(c) {
	return c.fieldtype === "Check" ? ["Yes", "No"] : c.choices
}

/** What already exists for a Link column: ERPNext's own records and your other sheets. */
function suggestionsFor(c) {
	return (data.value?.suggestions || {})[c.link_doctype] || []
}

function emptyRow() {
	return Object.fromEntries((data.value?.columns || []).map((c) => [c.fieldname, ""]))
}

function startTyping() {
	mode.value = "type"
	if (!typed.value.length) typed.value = [emptyRow(), emptyRow(), emptyRow()]
}

function addRow(after) {
	typed.value.splice(after === undefined ? typed.value.length : after + 1, 0, emptyRow())
}

async function saveTyped() {
	busy.value = true
	try {
		data.value = await api("enter_rows", { onboarding: state.id, area: props.area, rows: filled.value })
		typed.value = []
		mode.value = ""
		step.value = data.value.upload ? 2 : 0
		loadOverview()
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		busy.value = false
	}
}

async function onFile(file) {
	if (!file) return
	uploading.value = true
	progress.value = 0
	try {
		const f = await uploadFile(file, state.id, (p) => (progress.value = p))
		data.value = await api("attach_file", { onboarding: state.id, area: props.area, file_url: f.file_url })
		loadOverview()
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		uploading.value = false
		if (picker.value) picker.value.value = ""
	}
}

function onPick(e) {
	onFile(e.target.files[0])
}

function onDrop(e) {
	dragging.value = false
	onFile(e.dataTransfer.files[0])
}

function mapColumn(header, fieldname) {
	run("set_column", { header, fieldname: fieldname || null })
}

function fix(payload) {
	run("fix_value", payload, "Updated")
}

async function remove() {
	await run("remove_file", {}, "File removed")
	step.value = 0
}

// The server sends the template as an attachment, so the page stays put.
function downloadTemplate() {
	window.location.href = templateUrl(props.area, state.id)
}

function goNext() {
	router.push(nextStep.value ? { name: "area", params: { area: nextStep.value.area } } : { name: "home" })
}

function issuesFor(g) {
	return data.value.upload.issues.filter((i) => i.code === g.code && i.fieldname === g.fieldname)
}

function columnFor(fieldname) {
	return data.value.columns.find((c) => c.fieldname === fieldname) || null
}

function describe(c) {
	if (c.hint) return c.hint
	if (c.fieldtype === "Check") return "Yes or No."
	if (c.choices.length) return `One of: ${c.choices.join(", ")}.`
	if (c.fieldtype === "Link") return `A ${c.link_doctype}.`
	if (["Int", "Float"].includes(c.fieldtype)) return "A number."
	if (c.fieldtype === "Email") return "An email address."
	if (c.fieldtype === "Phone") return "A phone number."
	return ""
}

function show(value, fieldname) {
	if (value === null || value === undefined || value === "") return ""
	return columnFor(fieldname)?.fieldtype === "Check" ? (value ? "Yes" : "No") : value
}

watch(() => props.area, load, { immediate: true })
</script>
