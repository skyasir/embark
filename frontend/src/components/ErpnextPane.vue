<template>
	<div class="space-y-5 pb-10">
		<div>
			<h2 class="text-base font-semibold text-ink-gray-8">ERPNext</h2>
			<p class="text-sm text-ink-gray-5">What this step builds, and what it looks like once it exists.</p>
		</div>

		<!-- The record this step produces, before it exists. -->
		<div v-if="task?.doctype" class="rounded-lg border border-outline-gray-2">
			<div class="flex items-center gap-2 border-b border-outline-gray-1 bg-surface-gray-1 px-3 py-2">
				<FeatherIcon :name="task.icon || 'file-text'" class="size-3.5 shrink-0 text-ink-gray-5" />
				<span class="min-w-0 flex-1 truncate text-sm font-medium text-ink-gray-8">{{ task.title }}</span>
				<Badge theme="blue" size="sm" :label="task.doctype" />
			</div>
			<div class="px-3 py-2">
				<p v-if="task.description" class="text-sm leading-relaxed text-ink-gray-6">{{ task.description }}</p>
				<div class="mt-2 flex items-center gap-2">
					<div class="h-1 flex-1 overflow-hidden rounded-full bg-surface-gray-2">
						<div
							class="h-full rounded-full bg-surface-gray-7 transition-all"
							:style="{ width: `${(100 * task.answered) / Math.max(task.total, 1)}%` }"
						/>
					</div>
					<span class="shrink-0 text-sm tabular-nums text-ink-gray-5">
						{{ task.answered }}/{{ task.total }}
					</span>
				</div>
			</div>
		</div>

		<!-- Before anything is written: what, and why it is safe. -->
		<div v-if="check?.ready" class="rounded-lg border border-outline-amber-2 bg-surface-amber-1 px-3 py-3">
			<div class="flex items-start gap-2">
				<FeatherIcon name="shield" class="mt-0.5 size-4 shrink-0 text-ink-amber-3" />
				<div class="min-w-0">
					<p class="text-base font-medium text-ink-gray-8">{{ check.about_to }}</p>
					<ul class="mt-1 space-y-0.5">
						<li v-for="(reason, i) in check.safe_because" :key="i" class="text-sm text-ink-gray-7">
							{{ reason }}
						</li>
					</ul>
					<table v-if="check.fields.length" class="mt-2 w-full text-sm">
						<tbody>
							<tr v-for="f in check.fields" :key="f.field" class="align-top">
								<td class="w-2/5 py-0.5 pr-3 text-ink-gray-5">{{ f.field }}</td>
								<td class="py-0.5 text-ink-gray-8">{{ f.value }}</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>
		</div>

		<!-- After: the record, as ERPNext holds it. -->
		<div v-if="record" class="overflow-hidden rounded-lg border border-outline-green-2">
			<div class="flex items-center gap-2 border-b border-outline-green-2 bg-surface-green-1 px-3 py-2">
				<FeatherIcon name="check-circle" class="size-4 shrink-0 text-ink-green-3" />
				<span class="min-w-0 flex-1 truncate text-sm font-semibold uppercase tracking-wide text-ink-green-3">
					{{ record.doctype }} created
				</span>
			</div>
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-outline-gray-1 text-left text-ink-gray-5">
						<th class="px-3 py-1.5 font-medium">Field</th>
						<th class="px-3 py-1.5 font-medium">Value</th>
					</tr>
				</thead>
				<tbody>
					<tr class="border-b border-outline-gray-1">
						<td class="px-3 py-1.5 text-ink-gray-5">Name</td>
						<td class="px-3 py-1.5 font-medium text-ink-gray-9">{{ record.name }}</td>
					</tr>
					<tr v-for="f in record.fields" :key="f.field" class="border-b border-outline-gray-1 last:border-0">
						<td class="px-3 py-1.5 align-top text-ink-gray-5">{{ f.field }}</td>
						<td class="px-3 py-1.5 align-top text-ink-gray-8">{{ f.value }}</td>
					</tr>
				</tbody>
			</table>
			<div class="flex items-center justify-between gap-2 border-t border-outline-gray-1 px-3 py-2">
				<span class="truncate text-sm text-ink-gray-5">Owner: {{ record.owner }}</span>
				<a :href="record.url" target="_blank" rel="noopener">
					<Button size="sm" variant="ghost" icon-right="external-link" label="Open in ERPNext" />
				</a>
			</div>
		</div>

		<p v-else-if="!check?.ready" class="rounded-lg border border-outline-gray-2 px-3 py-4 text-sm text-ink-gray-5">
			Answer this step's questions and Embark will create the record here, with every field it wrote.
		</p>
	</div>
</template>

<script setup>
import { Badge, Button, FeatherIcon } from "frappe-ui"

defineProps({
	task: { type: Object, default: null },
	record: { type: Object, default: null },
	check: { type: Object, default: null },
})
</script>
