<template>
	<div class="space-y-3 rounded-lg border border-outline-gray-2 bg-surface-gray-1 p-4">
		<div class="flex flex-wrap items-center justify-between gap-2">
			<div class="flex items-center gap-2">
				<Badge theme="blue" label="Consultant" />
				<span class="text-base text-ink-gray-7">
					<template v-if="o.portal_user">
						Customer login: <span class="font-medium">{{ o.portal_user }}</span>
						<span class="ml-1 text-ink-gray-5">({{ o.portal_user_has_desk ? "portal + desk" : "portal only" }})</span>
					</template>
					<template v-else>The customer has no login yet.</template>
				</span>
			</div>
			<div class="flex flex-wrap gap-2">
				<Button v-if="o.has_data" icon-left="download" @click="download">Download prepared data</Button>
				<Button @click="inviteOpen = true">{{ o.portal_user ? "Send login link again" : "Invite customer" }}</Button>
				<template v-if="o.status === 'Submitted'">
					<Button @click="returnOpen = true">Return to customer</Button>
					<Button variant="solid" :loading="busy" @click="decide('Approved')">Approve</Button>
				</template>
			</div>
		</div>

		<Callout v-if="state.invite && !state.invite.emailed" tone="info">
			Share this link with {{ state.invite.user }} to set their password:
			<code class="mt-1 block break-all text-sm">{{ state.invite.setup_link }}</code>
			<button class="mt-1 text-sm underline" @click="copy(state.invite.setup_link)">Copy link</button>
		</Callout>
		<Callout v-if="o.status === 'Approved'" tone="success">
			<strong>Approved.</strong> Next, complete ERPNext's setup wizard in the
			<a href="/app" class="underline">desk</a> with the company details, then import the prepared data.
		</Callout>

		<Dialog v-model="inviteOpen" :options="{ title: o.portal_user ? 'Send login link again' : 'Invite customer' }">
			<template #body-content>
				<div class="ft-fill space-y-4">
					<FormControl v-model="invite.email" type="email" label="Email *" />
					<div class="grid grid-cols-2 gap-3">
						<FormControl v-model="invite.first_name" label="First name *" />
						<FormControl v-model="invite.last_name" label="Last name" />
					</div>
					<FormControl
						v-model="invite.desk_access"
						type="checkbox"
						label="Also give desk access"
						description="Their package's ERPNext roles, never System Manager. They still land in Embark."
					/>
					<FormControl v-model="invite.send_email" type="checkbox" label="Email them the login link" />
				</div>
			</template>
			<template #actions>
				<Button variant="solid" class="w-full" :loading="busy" :disabled="!invite.email || !invite.first_name" @click="sendInvite">
					{{ invite.send_email ? "Send invitation" : "Create login link" }}
				</Button>
			</template>
		</Dialog>

		<Dialog v-model="returnOpen" :options="{ title: 'Return to customer' }">
			<template #body-content>
				<FormControl v-model="notes" type="textarea" :rows="4" label="What should they fix? *" />
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
import { reactive, ref } from "vue"
import { Badge, Dialog, FormControl, toast } from "frappe-ui"

import Callout from "./Callout.vue"
import { api, errorText } from "../data/api"
import { loadOverview, state } from "../data/store"

const props = defineProps({ o: { type: Object, required: true } })

const busy = ref(false)
const inviteOpen = ref(false)
const returnOpen = ref(false)
const notes = ref("")
const invite = reactive({
	email: props.o.portal_user || "",
	first_name: "",
	last_name: "",
	send_email: true,
	desk_access: props.o.portal_user_has_desk,
})

async function sendInvite() {
	busy.value = true
	try {
		state.invite = await api("invite_customer", {
			onboarding: props.o.name,
			...invite,
			send_email: invite.send_email ? 1 : 0,
			desk_access: invite.desk_access ? 1 : 0,
		})
		inviteOpen.value = false
		toast.success(state.invite.emailed ? `Invitation sent to ${state.invite.user}` : "Login link created")
		loadOverview()
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		busy.value = false
	}
}

async function decide(decision) {
	busy.value = true
	try {
		await api("review", { onboarding: props.o.name, decision, notes: decision === "Returned" ? notes.value : undefined })
		returnOpen.value = false
		toast.success(decision === "Approved" ? "Approved" : "Returned to the customer")
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

async function copy(text) {
	try {
		await navigator.clipboard.writeText(text)
		toast.success("Link copied")
	} catch {
		toast.error("Couldn't copy; select the link and copy it instead.")
	}
}
</script>
