<template>
	<StartOnboarding v-if="o && o.needs_start" />
	<div v-else-if="o" class="space-y-6">
		<ConsultantPanel v-if="o.is_staff" :o="o" />
		<div>
			<h1 class="text-2xl font-semibold text-ink-gray-9">Let's get {{ o.client_name }} ready for ERPNext</h1>
			<p v-if="planned" class="mt-2 text-base leading-relaxed text-ink-gray-6">
				Work through the steps below. We check your data as you go, so setting up ERPNext goes quickly
				instead of turning into spreadsheet archaeology.
			</p>
			<p v-else class="mt-2 text-base leading-relaxed text-ink-gray-6">
				Start with a few questions about how you work. Your answers decide what we set up and what we
				need from you — so you are never asked for data your business doesn't use.
			</p>
		</div>

		<TallyHint />

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

		<Callout v-if="!planned" tone="info" icon="list">
			<strong>Your checklist comes from your answers.</strong>
			Finish the questions and the steps below will be the ones your business actually needs —
			nothing more.
		</Callout>

		<div v-else class="rounded-lg border border-outline-gray-2 p-5">
			<div class="mb-3 flex items-end justify-between gap-4">
				<div>
					<div class="text-base text-ink-gray-6">Readiness</div>
					<div class="text-3xl font-semibold tabular-nums text-ink-gray-9">{{ o.readiness }}%</div>
				</div>
				<div class="pb-1 text-base tabular-nums text-ink-gray-6">
					{{ readySteps }} of {{ requiredSteps }} required steps ready
				</div>
			</div>
			<div class="h-2 overflow-hidden rounded-full bg-surface-gray-2">
				<div
					class="h-full rounded-full transition-all"
					:class="o.readiness === 100 ? 'bg-surface-green-3' : 'bg-surface-gray-7'"
					:style="{ width: `${o.readiness}%` }"
				/>
			</div>
		</div>

		<ol class="divide-y divide-outline-gray-1 overflow-hidden rounded-lg border border-outline-gray-2">
			<StepRow
				icon="message-square"
				title="Tell us about your business"
				:description="`What you do, so we only ask for what matters. ${o.interview.answered} of ${o.interview.total} answered.`"
				:to="{ name: 'interview' }"
				:status="interviewStatus"
			/>
			<StepRow
				icon="briefcase"
				title="Company details"
				:description="
					o.company_from_erpnext
						? 'Taken from the company already set up in ERPNext.'
						: 'Your company name, country, currency and financial year.'
				"
				:to="{ name: 'company' }"
				:status="o.company_complete ? 'Ready' : 'Not Started'"
			/>
			<StepRow
				v-for="step in o.steps"
				:key="step.area"
				:title="step.area"
				:icon="step.icon"
				:description="step.description"
				:to="{ name: 'area', params: { area: step.area } }"
				:status="step.status"
				:errors="step.errors"
				:required="step.required"
				:rows="step.rows"
			/>
		</ol>

		<PlanSection
			:plan="o.plan"
			kind="Setting"
			icon="settings"
			title="What we'll set up in ERPNext"
			subtitle="Worked out from your answers. Nothing here is extra work for you."
		/>
		<PlanSection
			:plan="o.plan"
			kind="Decision"
			icon="help-circle"
			title="Decisions we need from you"
			subtitle="Small choices that are hard to change once you are live."
		/>
		<PlanSection
			:plan="o.plan"
			kind="Training"
			icon="play-circle"
			title="Training at handover"
			subtitle="What we walk your team through once the data is in."
		/>

		<div class="flex flex-wrap items-center justify-between gap-3">
			<p class="text-base text-ink-gray-6">
				<template v-if="o.status === 'Submitted'">The data has been sent for review.</template>
				<template v-else-if="o.status === 'Approved'">The data has been approved.</template>
				<template v-else-if="o.can_submit">Everything required is ready.</template>
				<template v-else-if="!planned">Answer the questions first, then we'll know what to ask you for.</template>
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
import PlanSection from "../components/PlanSection.vue"
import StepRow from "../components/StepRow.vue"
import TallyHint from "../components/TallyHint.vue"
import { api, errorText } from "../data/api"
import { loadOverview, setOverview, state } from "../data/store"

const o = computed(() => state.overview)
const submitting = ref(false)

// The checklist is built once the interview is answered, not before.
const planned = computed(() => o.value.steps.length > 0)

const interviewStatus = computed(() =>
	o.value.interview.done ? "Ready" : o.value.interview.answered ? "In Progress" : "Not Started"
)

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
