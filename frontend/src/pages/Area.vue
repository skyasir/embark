<template>
	<div v-if="loading" class="flex justify-center py-24">
		<LoadingIndicator class="size-6 text-ink-gray-5" />
	</div>

	<div v-else-if="data" class="space-y-6">
		<Stepper :steps="wizard" :current="step" @select="step = $event" />

		<Callout v-if="data.locked" tone="info">Your data is with your consultant, so it can't be changed now.</Callout>

		<!-- 1. Upload -->
		<section v-if="step === 0" class="space-y-6">
			<div>
				<h1 class="flex items-center gap-2.5 text-2xl font-semibold text-ink-gray-9">
					<span class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-surface-gray-2 text-ink-gray-7">
						<FeatherIcon :name="data.area.icon || 'file-text'" class="size-4" />
					</span>
					{{ data.area.name }}
				</h1>
				<p class="mt-2 text-base leading-relaxed text-ink-gray-6">
					{{ data.area.description }}
					<template v-if="!data.area.required">This step is optional.</template>
				</p>
			</div>

			<Callout v-if="data.area.help_text">{{ data.area.help_text }}</Callout>

			<div class="space-y-3">
				<h2 class="text-base font-semibold text-ink-gray-8">First, put your data in a sheet</h2>
				<p class="text-base leading-relaxed text-ink-gray-7">
					Download our template, or use your own Excel or CSV file. Any layout works as long as the
					first row has column headings; we match them for you next.
				</p>
				<div class="flex flex-wrap gap-2">
					<Button size="md" icon-left="download" @click="downloadTemplate">Download template</Button>
					<Button size="md" variant="ghost" :icon-right="showColumns ? 'chevron-up' : 'chevron-down'" @click="showColumns = !showColumns">
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
			</div>

			<!-- A handful of rows is quicker typed than exported, so both are here. -->
			<div v-if="!data.locked" class="space-y-3">
				<div class="flex gap-2">
					<Button
						size="md"
						:variant="mode === 'file' ? 'subtle' : 'ghost'"
						icon-left="upload"
						@click="mode = 'file'"
					>
						Upload a file
					</Button>
					<Button
						size="md"
						:variant="mode === 'type' ? 'subtle' : 'ghost'"
						icon-left="edit-3"
						@click="startTyping"
					>
						Type them in
					</Button>
				</div>
			</div>

			<div v-if="!data.locked && mode === 'type'" class="space-y-3">
				<h2 class="text-base font-semibold text-ink-gray-8">Type your {{ data.area.name.toLowerCase() }}</h2>
				<div class="overflow-x-auto rounded-lg border border-outline-gray-2">
					<table class="w-full text-left text-base">
						<thead class="bg-surface-gray-1 text-ink-gray-6">
							<tr>
								<th v-for="c in data.columns" :key="c.fieldname" class="px-3 py-2 font-medium">
									{{ c.label }}<span v-if="c.required" class="text-ink-red-3"> *</span>
								</th>
								<th class="w-10 px-2 py-2" />
							</tr>
						</thead>
						<tbody class="divide-y divide-outline-gray-1">
							<tr v-for="(row, i) in typed" :key="i">
								<td v-for="c in data.columns" :key="c.fieldname" class="px-1 py-1">
									<input
										v-model="row[c.fieldname]"
										class="w-full rounded border-0 bg-transparent px-2 py-1.5 text-base text-ink-gray-8 placeholder:text-ink-gray-4 focus:bg-surface-gray-1 focus:outline-none"
										:placeholder="i === 0 ? c.example || '' : ''"
										@keydown.enter.prevent="addRow(i)"
									/>
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
						Check these {{ filledCount }} {{ filledCount === 1 ? "row" : "rows" }}
					</Button>
				</div>
			</div>

			<div v-if="!data.locked && mode === 'file'" class="space-y-3">
				<h2 class="text-base font-semibold text-ink-gray-8">Then upload it here</h2>
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
				<h1 class="text-2xl font-semibold text-ink-gray-9">Match your columns</h1>
				<p class="mt-2 text-base leading-relaxed text-ink-gray-6">
					We matched the headings in your file to what ERPNext needs. Check them, change any that are
					wrong, then continue.
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
						We checked every row against ERPNext's rules. Fix anything below right here, or correct your
						file and upload it again. Your original file is never changed.
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
const mode = ref("file")
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
		{ label: "Upload", done: !!up, reachable: true },
		{ label: "Match columns", done: !!up && !missingColumns.value.length, reachable: !!up },
		{ label: "Check", done: !!up && up.errors === 0, reachable: !!up },
	]
})

const fieldOptions = computed(() => [
	{ label: "Don't use", value: "" },
	...data.value.columns.map((c) => ({ label: c.label + (c.required ? " *" : ""), value: c.fieldname })),
])

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
		mode.value = "file"
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
