<template>
	<div class="space-y-6">
		<div>
			<h1 class="text-2xl font-semibold text-ink-gray-9">Start Embark for this customer</h1>
			<p class="mt-2 text-base leading-relaxed text-ink-gray-6">
				This site belongs to one customer. Choose the package they bought and create their login. They will
				see only the steps their package needs, and nothing else of ERPNext until you approve their data.
			</p>
		</div>

		<form class="ft-fill space-y-5" @submit.prevent="start">
			<FormControl v-model="form.client_name" label="Customer (company) *" placeholder="Sunrise Traders" />
			<FormControl v-model="form.package" type="select" label="Package *" :options="packageOptions" />
			<div class="grid gap-5 sm:grid-cols-2">
				<FormControl v-model="form.first_name" label="Contact first name *" />
				<FormControl v-model="form.last_name" label="Contact last name" />
				<FormControl v-model="form.email" type="email" label="Contact email *" class="sm:col-span-2" />
			</div>
			<FormControl
				v-model="form.access"
				type="select"
				label="Access"
				:options="[
					{ label: 'Portal only: they see Embark and nothing else', value: 'portal' },
					{ label: 'Portal + desk: they can also switch to ERPNext', value: 'desk' },
				]"
				description="With desk access they get their package's ERPNext roles, never System Manager. They still land in Embark."
			/>
			<FormControl
				v-model="form.send_email"
				type="checkbox"
				label="Email them the login link"
				description="Untick to get a link you can share yourself."
			/>
			<div class="flex justify-end">
				<Button type="submit" variant="solid" size="md" icon-right="arrow-right" :loading="saving" :disabled="!ready">
					Start onboarding
				</Button>
			</div>
		</form>
	</div>
</template>

<script setup>
import { computed, reactive, ref } from "vue"
import { FormControl, toast } from "frappe-ui"

import { api, errorText } from "../data/api"
import { setOverview } from "../data/store"

const props = defineProps({ packages: { type: Array, required: true } })
const emit = defineEmits(["invited"])

const form = reactive({ client_name: "", package: "", first_name: "", last_name: "", email: "", send_email: true, access: "portal" })
const saving = ref(false)

const packageOptions = computed(() => [
	{ label: "Select…", value: "" },
	...props.packages.map((p) => ({ label: `${p.name} · ${p.modules} · ${Number(p.hours)} hours`, value: p.name })),
])
const ready = computed(() => form.client_name.trim() && form.package && form.first_name.trim() && form.email.trim())

async function start() {
	saving.value = true
	try {
		const { access, ...fields } = form
		const result = await api("start_onboarding", {
			...fields,
			send_email: form.send_email ? 1 : 0,
			desk_access: access === "desk" ? 1 : 0,
		})
		setOverview(result.overview)
		emit("invited", result.invite)
		toast.success("Onboarding started")
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		saving.value = false
	}
}
</script>
