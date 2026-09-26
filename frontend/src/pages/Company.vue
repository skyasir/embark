<template>
	<div v-if="o" class="space-y-6">
		<div>
			<h1 class="text-2xl font-semibold text-ink-gray-9">Company details</h1>
			<p class="mt-2 text-base leading-relaxed text-ink-gray-6">
				These set up your company in ERPNext: its currency, its financial year and how its accounts are
				arranged. Fields marked * are needed.
			</p>
		</div>

		<Callout v-if="o.locked" tone="info">Your data is with your consultant, so it can't be changed now.</Callout>

		<form class="ft-fill space-y-5" @submit.prevent="save">
			<div class="grid gap-5 sm:grid-cols-2">
				<FormControl v-model="form.company_name" label="Company name *" placeholder="As registered" :disabled="o.locked" class="sm:col-span-2" />
				<FormControl v-model="form.country" type="select" label="Country *" :options="countryOptions" :disabled="o.locked" />
				<FormControl v-model="form.default_currency" type="select" label="Currency *" :options="currencyOptions" :disabled="o.locked" />
				<FormControl
					v-model="form.fiscal_year_start"
					type="date"
					label="Financial year starts on *"
					description="For example 01-04-2026 in India, 01-01-2026 in most other countries."
					:disabled="o.locked"
				/>
				<FormControl
					v-model="form.chart_of_accounts"
					type="select"
					label="Chart of accounts"
					:options="[
						{ label: 'Standard', value: 'Standard' },
						{ label: 'Standard with account numbers', value: 'Standard with Account Numbers' },
					]"
					description="ERPNext's standard chart for your country. Your consultant can adjust it."
					:disabled="o.locked"
				/>
				<FormControl
					v-model="form.tax_id"
					label="Tax registration number"
					placeholder="GSTIN, VAT or TRN"
					:disabled="o.locked"
				/>
				<FormControl v-model="form.company_email" type="email" label="Company email" :disabled="o.locked" />
				<FormControl v-model="form.company_phone" label="Company phone" :disabled="o.locked" />
				<FormControl
					v-model="form.company_address"
					type="textarea"
					label="Registered address"
					:rows="3"
					:disabled="o.locked"
					class="sm:col-span-2"
				/>
			</div>

			<div v-if="!o.locked" class="flex justify-end gap-2 pt-2">
				<Button size="md" @click="$router.push({ name: 'home' })">Back</Button>
				<Button type="submit" variant="solid" size="md" icon-right="arrow-right" :loading="saving">
					Save and continue
				</Button>
			</div>
		</form>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { FormControl, toast } from "frappe-ui"

import Callout from "../components/Callout.vue"
import { api, errorText } from "../data/api"
import { setOverview, state } from "../data/store"

const router = useRouter()
const o = computed(() => state.overview)
// Empty strings, not nulls: the select shows its placeholder only for "".
const form = reactive(
	Object.fromEntries(Object.entries(o.value?.company || {}).map(([k, v]) => [k, v ?? ""]))
)
form.chart_of_accounts ||= "Standard"
const choices = reactive({ countries: [], currencies: [] })
const saving = ref(false)

const blank = { label: "Select…", value: "" }
const countryOptions = computed(() => [blank, ...choices.countries.map((c) => ({ label: c, value: c }))])
const currencyOptions = computed(() => [blank, ...choices.currencies.map((c) => ({ label: c, value: c }))])

async function save() {
	saving.value = true
	try {
		const overview = await api("save_company_details", { onboarding: o.value.name, values: { ...form } })
		setOverview(overview)
		if (!overview.company_complete) {
			toast.warning("Saved. Fill in the fields marked * to finish this step.")
			return
		}
		toast.success("Company details saved")
		const next = overview.steps.find((s) => s.status !== "Ready")
		router.push(next ? { name: "area", params: { area: next.area } } : { name: "home" })
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		saving.value = false
	}
}

onMounted(async () => {
	Object.assign(choices, await api("get_company_choices"))
})
</script>
