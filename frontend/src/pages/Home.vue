<template>
	<StartOnboarding v-if="o && o.needs_start" :packages="o.packages" @invited="(r) => (state.invite = r)" />
	<div v-else-if="o" class="space-y-6">
		<ConsultantPanel v-if="o.is_staff" :o="o" />
		<div>
			<h1 class="text-2xl font-semibold text-ink-gray-9">Let's get {{ o.client_name }} ready for ERPNext</h1>
			<p class="mt-2 text-base leading-relaxed text-ink-gray-6">
				Work through the steps below. We check your data as you go, so the implementation hours can be
				spent setting up ERPNext, not fixing spreadsheets.
			</p>
		</div>

		<Callout v-if="o.status === 'Returned'" tone="warning">
			<strong>Your consultant sent this back with a note.</strong>
			<p class="mt-1 whitespace-pre-line">{{ o.review_notes }}</p>
		</Callout>
		<Callout v-else-if="o.status === 'Submitted'" tone="success">
			<strong>Sent for review.</strong> Your consultant is checking your data and will be in touch to
			schedule the implementation.
		</Callout>
		<Callout v-else-if="o.status === 'Approved'" tone="success">
			<strong>All set.</strong> Your data has been approved and is ready for the implementation.
		</Callout>

		<div class="rounded-lg border border-outline-gray-2 p-5">
			<div class="flex flex-wrap items-start justify-between gap-4">
				<div>
					<div class="text-sm text-ink-gray-5">Your implementation package</div>
					<div class="mt-1 text-lg font-semibold text-ink-gray-9">{{ o.package.name }}</div>
					<div class="text-base text-ink-gray-7">{{ o.package.modules }}</div>
				</div>
				<Badge theme="blue" size="lg" :label="`${Number(o.package.hours)} hours`" />
			</div>
			<div class="mt-5">
				<div class="mb-2 flex items-baseline justify-between text-base">
					<span class="font-medium text-ink-gray-8">Readiness</span>
					<span class="tabular-nums text-ink-gray-6">
						{{ readySteps }} of {{ requiredSteps }} required steps ready
					</span>
				</div>
				<div class="h-2 overflow-hidden rounded-full bg-surface-gray-2">
					<div
						class="h-full rounded-full transition-all"
						:class="o.readiness === 100 ? 'bg-surface-green-3' : 'bg-surface-gray-7'"
						:style="{ width: `${o.readiness}%` }"
					/>
				</div>
				<div class="mt-1 text-right text-2xl font-semibold tabular-nums text-ink-gray-9">
					{{ o.readiness }}%
				</div>
			</div>
		</div>

		<ol class="divide-y divide-outline-gray-1 overflow-hidden rounded-lg border border-outline-gray-2">
			<StepRow
				:number="1"
				title="Tell us about your business"
				:description="`What you do, so we only ask for what matters. ${o.interview.answered} of ${o.interview.total} answered.`"
				:to="{ name: 'interview' }"
				:status="o.interview.done ? 'Ready' : 'Not Started'"
			/>
			<StepRow
				:number="2"
				title="Company details"
				description="Your company name, country, currency and financial year."
				:to="{ name: 'company' }"
				:status="o.company_complete ? 'Ready' : 'Not Started'"
			/>
			<StepRow
				v-for="(step, i) in o.steps"
				:key="step.area"
				:number="i + 3"
				:title="step.area"
				:description="step.description"
				:to="{ name: 'area', params: { area: step.area } }"
				:status="step.status"
				:errors="step.errors"
				:required="step.required"
				:rows="step.rows"
			/>
		</ol>

		<div class="flex flex-wrap items-center justify-between gap-3">
			<p class="text-base text-ink-gray-6">
				<template v-if="o.status === 'Submitted'">The data has been sent for review.</template>
				<template v-else-if="o.status === 'Approved'">The data has been approved.</template>
				<template v-else-if="o.can_submit">Everything required is ready.</template>
				<template v-else>Finish every required step to send your data for review.</template>
			</p>
			<Button
				v-if="!['Submitted', 'Approved'].includes(o.status)"
				variant="solid"
				size="md"
				icon-right="arrow-right"
				:disabled="!o.can_submit"
				:loading="submitting"
				@click="submit"
			>
				Send for review
			</Button>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { Badge, toast } from "frappe-ui"

import Callout from "../components/Callout.vue"
import ConsultantPanel from "../components/ConsultantPanel.vue"
import StartOnboarding from "../components/StartOnboarding.vue"
import StepRow from "../components/StepRow.vue"
import { api, errorText } from "../data/api"
import { loadOverview, setOverview, state } from "../data/store"

const o = computed(() => state.overview)
const submitting = ref(false)

const requiredSteps = computed(() => 2 + o.value.steps.filter((s) => s.required).length)
const readySteps = computed(
	() =>
		Number(o.value.interview.done) +
		Number(o.value.company_complete) +
		o.value.steps.filter((s) => s.required && s.status === "Ready").length
)

async function submit() {
	submitting.value = true
	try {
		setOverview(await api("submit_for_review", { onboarding: o.value.name }))
		toast.success("Sent for review")
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		submitting.value = false
	}
}

// Coming back from a step, pick up its new status.
onMounted(() => {
	if (o.value) loadOverview()
})
</script>
