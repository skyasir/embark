<template>
	<div class="space-y-6">
		<div>
			<h1 class="text-2xl font-semibold text-ink-gray-9">Start Embark on this site</h1>
			<p class="mt-2 text-base leading-relaxed text-ink-gray-6">
				Embark asks about the business first, then asks only for the data that business actually needs.
				One site, one onboarding.
			</p>
		</div>

		<form class="ft-fill space-y-5" @submit.prevent="start">
			<FormControl
				v-model="clientName"
				label="Customer (company) *"
				placeholder="Sunrise Traders"
				description="Shown on every screen. You can change it later."
			/>
			<div class="flex justify-end">
				<Button
					type="submit"
					variant="solid"
					size="md"
					icon-right="arrow-right"
					:loading="saving"
					:disabled="!clientName.trim()"
				>
					Start onboarding
				</Button>
			</div>
		</form>
	</div>
</template>

<script setup>
import { ref } from "vue"
import { FormControl, toast } from "frappe-ui"

import { api, errorText } from "../data/api"
import { setOverview } from "../data/store"

const clientName = ref("")
const saving = ref(false)

async function start() {
	saving.value = true
	try {
		const result = await api("start_onboarding", { client_name: clientName.value })
		setOverview(result.overview)
		toast.success("Onboarding started")
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		saving.value = false
	}
}
</script>
