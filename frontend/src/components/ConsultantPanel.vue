<template>
	<div class="space-y-3 rounded-lg border border-outline-gray-2 bg-surface-gray-1 p-4">
		<div class="flex flex-wrap items-center justify-between gap-2">
			<span class="text-base text-ink-gray-7">
				<template v-if="o.status === 'Submitted'">This onboarding is waiting for review.</template>
				<template v-else-if="o.status === 'Approved'">This onboarding has been approved.</template>
				<template v-else-if="o.status === 'Returned'">Returned, with a note for whoever fills it in.</template>
				<template v-else>{{ o.readiness }}% ready.</template>
			</span>
			<div class="flex flex-wrap gap-2">
				<Button v-if="o.has_data" icon-left="download" @click="download">Download prepared data</Button>
				<Button
					v-if="o.status === 'Approved' && o.has_data"
					icon-left="upload-cloud"
					:loading="creating"
					@click="create"
				>
					{{ o.imported_at ? "Create anything new" : "Create in ERPNext" }}
				</Button>
				<template v-if="o.status === 'Submitted'">
					<Button @click="returnOpen = true">Return for changes</Button>
					<Button variant="solid" :loading="busy" @click="decide('Approved')">Approve</Button>
				</template>
			</div>
		</div>

		<!-- What approving actually did: the data is in ERPNext, or here is why not. -->
		<Callout v-if="o.status === 'Approved' && !o.setup_done" tone="warning">
			<strong>ERPNext is not set up yet.</strong> Run the
			<a href="/app" class="underline">setup wizard</a> to create the company, then press
			<em>Create in ERPNext</em> — nothing can be created before there is a company to put it in.
		</Callout>
		<Callout v-else-if="summary" :tone="summary.failed ? 'warning' : 'success'">
			<strong>
				{{ summary.created }} {{ summary.created === 1 ? "record" : "records" }} created in ERPNext<template
					v-if="summary.skipped"
				>, {{ summary.skipped }} already there</template
				><template v-if="summary.failed">, {{ summary.failed }} refused</template>.
			</strong>
			<ul class="mt-2 space-y-1">
				<li v-for="s in told" :key="s.area" class="text-sm">
					<span class="font-medium text-ink-gray-8">{{ s.area }}</span>
					<span class="text-ink-gray-6"> — {{ line(s) }}</span>
					<ul v-if="s.failures.length" class="ml-4 mt-0.5 list-disc space-y-0.5 text-ink-gray-6">
						<li v-for="(f, i) in s.failures.slice(0, 5)" :key="i">Row {{ f.row }}: {{ f.why }}</li>
						<li v-if="s.failures.length > 5">…and {{ s.failures.length - 5 }} more</li>
					</ul>
				</li>
			</ul>
			<p class="mt-2 text-sm text-ink-gray-6">
				Open them in the <a href="/app" class="underline">desk</a>. Pressing the button again creates only
				what is not there yet.
			</p>
		</Callout>
		<Callout v-else-if="o.status === 'Approved'" tone="success">
			<strong>Approved.</strong> Press <em>Create in ERPNext</em> to turn this data into records.
		</Callout>

		<Dialog v-model="returnOpen" :options="{ title: 'Return for changes' }">
			<template #body-content>
				<FormControl v-model="notes" type="textarea" :rows="4" label="What should be fixed? *" />
			</template>
			<template #actions>
				<Button variant="solid" class="w-full" :loading="busy" :disabled="!notes.trim()" @click="decide('Returned')">
					Return with this note
				</Button>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { computed, ref } from "vue"
import { Dialog, FormControl, toast } from "frappe-ui"

import Callout from "./Callout.vue"
import { api, errorText } from "../data/api"
import { loadOverview, setOverview } from "../data/store"

const props = defineProps({ o: { type: Object, required: true } })

const busy = ref(false)
const creating = ref(false)
const returnOpen = ref(false)
const notes = ref("")

const summary = computed(() => props.o.import_summary)
// Steps worth a line: something happened, or something stopped it.
const told = computed(() =>
	(summary.value?.steps || []).filter((s) => s.created || s.skipped || s.failures.length || s.reason),
)

function line(s) {
	if (s.reason) return s.reason
	const parts = []
	if (s.created) parts.push(`${s.created} created`)
	if (s.skipped) parts.push(`${s.skipped} already there`)
	if (s.failures.length) parts.push(`${s.failures.length} refused`)
	return parts.join(", ") || "nothing to create"
}

async function decide(decision) {
	busy.value = true
	try {
		const out = await api("review", {
			onboarding: props.o.name,
			decision,
			notes: decision === "Returned" ? notes.value : undefined,
		})
		returnOpen.value = false
		if (out.overview) setOverview(out.overview)
		else await loadOverview()
		if (decision === "Returned") toast.success("Returned for changes")
		else toast.success(out.summary ? `${out.summary.created} records created in ERPNext` : "Approved")
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		busy.value = false
	}
}

async function create() {
	creating.value = true
	try {
		const out = await api("create_in_erpnext", { onboarding: props.o.name })
		setOverview(out.overview)
		toast.success(
			out.summary.created ? `${out.summary.created} records created in ERPNext` : "Everything was already there",
		)
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		creating.value = false
	}
}

function download() {
	window.location.href = `/api/method/embark.api.download_prepared_data?onboarding=${encodeURIComponent(props.o.name)}`
}
</script>
