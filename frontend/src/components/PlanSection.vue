<template>
	<section v-if="lines.length" class="space-y-3">
		<div class="flex flex-wrap items-end justify-between gap-2">
			<div>
				<h2 class="text-base font-semibold text-ink-gray-8">{{ title }}</h2>
				<p class="text-base text-ink-gray-6">{{ subtitle }}</p>
			</div>
			<!-- The whole point of the plan: Embark does it, you don't. -->
			<Button
				v-if="canConfigure"
				variant="solid"
				icon-left="zap"
				:loading="busyAll"
				@click="configureAll"
			>
				Set up {{ pending.length }} in ERPNext
			</Button>
		</div>
		<ul class="divide-y divide-outline-gray-1 overflow-hidden rounded-lg border border-outline-gray-2">
			<li v-for="line in lines" :key="line.key" class="px-4 py-3">
				<div class="flex items-start gap-3">
					<FeatherIcon :name="icon" class="mt-0.5 size-4 shrink-0 text-ink-gray-5" />
					<div class="min-w-0 flex-1">
						<div class="text-base font-medium text-ink-gray-9">{{ line.title }}</div>
						<div v-if="line.description" class="text-base text-ink-gray-6">{{ line.description }}</div>
						<div v-if="line.because" class="mt-0.5 text-sm text-ink-gray-5">Because {{ line.because }}.</div>
						<div v-if="line.detail" class="mt-1 text-sm text-ink-gray-5">
							<span class="font-medium">How:</span> {{ line.detail }}
						</div>
						<div v-if="line.notes" class="mt-1 text-sm text-ink-green-3">{{ line.notes }}</div>

						<!-- What the switch would become, before anyone presses it. -->
						<div v-if="shown[line.key]" class="mt-2 rounded-lg border border-outline-gray-2 bg-surface-gray-1 p-3">
							<div v-for="(change, i) in shown[line.key]" :key="i" class="mb-2 last:mb-0">
								<div class="text-sm font-medium text-ink-gray-7">{{ change.doctype }}</div>
								<table class="mt-1 w-full text-sm">
									<tbody>
										<tr v-for="(row, j) in change.lines" :key="j" class="align-top">
											<td class="py-0.5 pr-3 text-ink-gray-5">{{ row.field }}</td>
											<td class="py-0.5 pr-3 text-ink-gray-5 line-through" :class="row.before ? '' : 'opacity-40'">
												{{ row.before || "—" }}
											</td>
											<td class="py-0.5 text-ink-gray-8">{{ row.after || "—" }}</td>
										</tr>
									</tbody>
								</table>
							</div>
							<p v-if="!shown[line.key].length" class="text-sm text-ink-gray-6">
								This site is already set up this way.
							</p>
						</div>
					</div>

					<div class="flex shrink-0 items-center gap-2">
						<Button
							v-if="line.can_apply && line.status === 'Planned'"
							size="sm"
							variant="ghost"
							:loading="peeking === line.key"
							@click="peek(line)"
						>
							{{ shown[line.key] ? "Hide" : "What changes" }}
						</Button>
						<Button
							v-if="line.can_apply && line.status === 'Planned'"
							size="sm"
							:loading="busy === line.key"
							@click="configure(line)"
						>
							Set up
						</Button>
						<Badge
							v-else-if="line.status !== 'Planned'"
							:theme="line.status === 'Done' ? 'green' : 'gray'"
							:label="line.status"
							size="md"
						/>
						<Tooltip
							v-else-if="staff && kind === 'Setting'"
							text="Embark cannot do this one — it needs a number or a judgement only you have"
						>
							<span class="text-sm text-ink-gray-4">By hand</span>
						</Tooltip>
					</div>
				</div>
			</li>
		</ul>
	</section>
</template>

<script setup>
import { computed, reactive, ref } from "vue"
import { Badge, FeatherIcon, Tooltip, toast } from "frappe-ui"

import { api, errorText } from "../data/api"
import { setOverview, state } from "../data/store"

const props = defineProps({
	plan: { type: Array, required: true },
	kind: { type: String, required: true },
	title: { type: String, required: true },
	subtitle: { type: String, default: "" },
	icon: { type: String, default: "check" },
})

const lines = computed(() => props.plan.filter((line) => line.kind === props.kind))
const pending = computed(() => lines.value.filter((l) => l.can_apply && l.status === "Planned"))
const staff = computed(() => state.overview?.is_staff)
const canConfigure = computed(() => pending.value.length > 0)

const busy = ref("")
const busyAll = ref(false)
const peeking = ref("")
const shown = reactive({})

async function peek(line) {
	if (shown[line.key]) {
		delete shown[line.key]
		return
	}
	peeking.value = line.key
	try {
		const out = await api("configure_preview", { onboarding: state.id, task: line.key })
		shown[line.key] = out.changes
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		peeking.value = ""
	}
}

async function configure(line) {
	busy.value = line.key
	try {
		const out = await api("configure_step", { onboarding: state.id, task: line.key })
		setOverview(out.overview)
		delete shown[line.key]
		toast.success(out.result.already ? "Already set up that way" : `${line.title} is set up`)
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		busy.value = ""
	}
}

async function configureAll() {
	busyAll.value = true
	try {
		const out = await api("configure_all", { onboarding: state.id })
		setOverview(out.overview)
		if (out.failed.length) toast.error(`${out.failed.length} could not be set up`)
		else toast.success(`${out.configured.length} set up in ERPNext`)
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		busyAll.value = false
	}
}
</script>
