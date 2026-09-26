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
				<template v-if="o.status === 'Submitted'">
					<Button @click="returnOpen = true">Return for changes</Button>
					<Button variant="solid" :loading="busy" @click="decide('Approved')">Approve</Button>
				</template>
			</div>
		</div>

		<Callout v-if="o.status === 'Approved'" tone="success">
			<strong>Approved.</strong> Next, complete ERPNext's setup wizard in the
			<a href="/app" class="underline">desk</a> with the company details, then import the prepared data.
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
import { ref } from "vue"
import { Dialog, FormControl, toast } from "frappe-ui"

import Callout from "./Callout.vue"
import { api, errorText } from "../data/api"
import { loadOverview } from "../data/store"

const props = defineProps({ o: { type: Object, required: true } })

const busy = ref(false)
const returnOpen = ref(false)
const notes = ref("")

async function decide(decision) {
	busy.value = true
	try {
		await api("review", { onboarding: props.o.name, decision, notes: decision === "Returned" ? notes.value : undefined })
		returnOpen.value = false
		toast.success(decision === "Approved" ? "Approved" : "Returned for changes")
		await loadOverview()
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		busy.value = false
	}
}

function download() {
	window.location.href = `/api/method/embark.api.download_prepared_data?onboarding=${encodeURIComponent(props.o.name)}`
}
</script>
