<template>
	<!-- A column of its own, beside the site it is changing: what the customer
	     says and what Embark did about it, in one scroll. -->
	<div
		v-if="o?.assistant"
		class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-white"
	>
		<div ref="scroller" class="flex-1 space-y-3 overflow-y-auto px-4 py-4">
			<div v-if="!messages.length" class="space-y-3">
				<p class="text-base leading-relaxed text-ink-gray-8">{{ opening.greeting }}</p>
				<button
					v-for="example in opening.suggestions"
					:key="example"
					class="block w-full rounded-lg border border-outline-gray-2 px-3 py-2 text-left text-base text-ink-gray-7 hover:bg-surface-gray-1"
					@click="send(example)"
				>
					{{ example }}
				</button>
			</div>

			<div v-for="(m, i) in messages" :key="i" class="text-base leading-relaxed">
				<div v-if="m.role === 'user'" class="ml-8 rounded-lg bg-surface-gray-2 px-3 py-2 text-ink-gray-8">
					{{ m.content }}
				</div>

				<!-- What it did on the way: one row per tool call, openable. -->
				<details v-else-if="m.role === 'step'" class="rounded-lg border border-outline-gray-2">
					<summary class="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm text-ink-gray-7">
						<FeatherIcon
							:name="m.step.failed ? 'alert-circle' : 'check'"
							class="size-3.5 shrink-0"
							:class="m.step.failed ? 'text-ink-red-3' : 'text-ink-green-3'"
						/>
						<span class="flex-1 truncate">{{ m.step.label || m.step.tool }}</span>
					</summary>
					<pre class="overflow-x-auto whitespace-pre-wrap border-t border-outline-gray-1 px-3 py-2 text-sm text-ink-gray-6">{{ detail(m.step) }}</pre>
				</details>

				<!-- A change to this site: nothing happens until it is applied. -->
				<div v-else-if="m.role === 'change'" class="rounded-lg border border-outline-gray-2">
					<div class="flex items-center gap-2 border-b border-outline-gray-1 bg-surface-gray-1 px-3 py-2">
						<span class="flex-1 truncate text-sm font-medium text-ink-gray-8">{{ m.set.title }}</span>
						<Badge :theme="m.set.status === 'Applied' ? 'green' : 'gray'" :label="m.set.status" size="sm" />
					</div>
					<ul class="list-disc space-y-1 px-3 py-2 pl-7 text-sm text-ink-gray-7">
						<li v-for="(c, j) in m.set.changes" :key="j">{{ c.summary }}</li>
					</ul>

					<!-- What it means, before and after, without touching the site. -->
					<div v-if="m.preview" class="border-t border-outline-gray-1 px-3 py-2">
						<div v-for="(p, j) in m.preview" :key="j" class="mb-2 last:mb-0">
							<div class="text-sm font-medium text-ink-gray-7">
								{{ p.action }} · {{ p.doctype }}
							</div>
							<table class="mt-1 w-full text-sm">
								<tbody>
									<tr v-for="(line, k) in p.lines" :key="k" class="align-top">
										<td class="py-0.5 pr-2 text-ink-gray-5">{{ line.field }}</td>
										<td class="py-0.5 pr-2 text-ink-gray-5 line-through" :class="line.before ? '' : 'opacity-40'">
											{{ line.before || "—" }}
										</td>
										<td class="py-0.5 text-ink-gray-8">{{ line.after || "—" }}</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>

					<div class="flex gap-2 border-t border-outline-gray-1 px-3 py-2">
						<Button size="sm" variant="ghost" :loading="m.loading" @click="showPreview(m)">
							{{ m.preview ? "Hide" : "What changed" }}
						</Button>
					</div>
				</div>

				<div v-else class="mr-4 whitespace-pre-line text-ink-gray-8">{{ m.content }}</div>
			</div>

			<div v-if="busy" class="flex items-center gap-2 text-base text-ink-gray-5">
				<LoadingIndicator class="size-4" />
				Thinking…
			</div>
		</div>

		<!-- One rounded box: what you type, and underneath it what is answering
		     and the button that sends it. -->
		<div class="shrink-0 border-t border-outline-gray-1 p-3">
			<div
				class="rounded-xl border bg-surface-white px-3 pb-2 pt-2.5 transition-colors"
				:class="focused ? 'border-outline-gray-3' : 'border-outline-gray-2'"
			>
				<!-- A file picked here is sent with the next message, so the
				     chat can put it on the right step and check it at once. -->
				<div
					v-if="attachment"
					class="mb-2 flex items-center gap-2 rounded-lg bg-surface-gray-2 px-2.5 py-1.5 text-sm text-ink-gray-7"
				>
					<FeatherIcon name="paperclip" class="size-3.5 shrink-0 text-ink-gray-5" />
					<span class="min-w-0 flex-1 truncate">{{ attachment.file_name }}</span>
					<button class="shrink-0 text-ink-gray-5 hover:text-ink-gray-8" aria-label="Remove" @click="attachment = null">
						<FeatherIcon name="x" class="size-3.5" />
					</button>
				</div>
				<textarea
					v-model="draft"
					rows="2"
					class="block w-full resize-none border-0 bg-transparent p-0 text-base leading-relaxed text-ink-gray-8 placeholder:text-ink-gray-4 focus:outline-none focus:ring-0"
					:placeholder="o.locked ? 'Your data is with your consultant.' : 'Tell me about your business, or send me a spreadsheet…'"
					:disabled="busy || o.locked"
					@focus="focused = true"
					@blur="focused = false"
					@keydown.enter.exact.prevent="send(draft)"
				/>
				<div class="mt-1.5 flex items-center gap-2">
					<button
						class="flex size-7 shrink-0 items-center justify-center rounded-full text-ink-gray-6 transition-colors hover:bg-surface-gray-2 disabled:opacity-40"
						:disabled="busy || uploading || o.locked"
						aria-label="Attach a spreadsheet"
						@click="picker.click()"
					>
						<LoadingIndicator v-if="uploading" class="size-4" />
						<FeatherIcon v-else name="paperclip" class="size-4" />
					</button>
					<input
						ref="picker"
						type="file"
						class="hidden"
						accept=".xlsx,.xls,.csv"
						@change="onPick"
					/>
					<span class="min-w-0 flex-1 truncate text-sm text-ink-gray-4">
						{{ o.assistant_model || "Embark"
						}}<template v-if="o.assistant_engine === 'flow'"> · Frappe Flow</template>
					</span>
					<button
						class="flex size-7 shrink-0 items-center justify-center rounded-full bg-surface-gray-3 text-ink-gray-8 transition-colors hover:bg-surface-gray-4 disabled:opacity-40"
						:disabled="busy || o.locked || (!draft.trim() && !attachment)"
						aria-label="Send"
						@click="send(draft)"
					>
						<FeatherIcon name="arrow-up" class="size-4" />
					</button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue"
import { Badge, Button, FeatherIcon, LoadingIndicator, toast } from "frappe-ui"

import { api, callMethod, errorText, uploadFile } from "../data/api"
import { setOverview, state } from "../data/store"

const o = computed(() => state.overview)
const draft = ref("")
const busy = ref(false)
const uploading = ref(false)
const focused = ref(false)
const messages = ref([])
const scroller = ref(null)
const picker = ref(null)
const attachment = ref(null)
// What it says before it is spoken to: worked out on the server from where
// this onboarding actually is, so it costs nothing and is never wrong.
const opening = ref({ greeting: "", suggestions: [] })

watch(
	() => o.value?.assistant,
	async (on) => {
		if (!on || messages.value.length) return
		try {
			opening.value = await api("chat_opening", { onboarding: state.id })
		} catch (e) {
			opening.value = { greeting: errorText(e), suggestions: [] }
		}
	},
	{ immediate: true },
)

async function send(text) {
	const sent = attachment.value
	const message = (text || "").trim() || (sent ? `I have sent you ${sent.file_name}.` : "")
	if (!message || busy.value) return
	draft.value = ""
	attachment.value = null
	messages.value.push({ role: "user", content: message })
	busy.value = true
	await scrollDown()
	try {
		const result = await api("ask", {
			message,
			onboarding: state.id,
			// Only the plain turns: the server rebuilds its own tool context.
			history: JSON.stringify(said()),
			file_url: sent?.file_url,
		})
		// Everything it did, in the order it did it.
		;(result.steps || []).forEach((step) => messages.value.push({ role: "step", step }))
		if (result.reply) messages.value.push({ role: "assistant", content: result.reply })
		if (result.change_set) messages.value.push({ role: "change", set: result.change_set, busy: false, loading: false, preview: null })
		// Answers it saved change the checklist behind the panel.
		if (result.overview) setOverview(result.overview)
	} catch (e) {
		messages.value.push({ role: "assistant", content: errorText(e) })
		toast.error(errorText(e))
	} finally {
		busy.value = false
		await scrollDown()
	}
}

/**
 * The conversation as the model should see it: what was said, not the step
 * rows or change cards drawn beside it. Those carry no `content`, and a
 * provider rejects the whole request over one message it cannot read.
 */
function said() {
	return messages.value
		.filter((m) => (m.role === "user" || m.role === "assistant") && m.content)
		.slice(-8)
		.map((m) => ({ role: m.role, content: m.content }))
}

async function onPick(e) {
	const file = e.target.files[0]
	if (!file) return
	uploading.value = true
	try {
		const uploaded = await uploadFile(file, state.id)
		attachment.value = { file_url: uploaded.file_url, file_name: file.name }
	} catch (err) {
		toast.error(errorText(err))
	} finally {
		uploading.value = false
		if (picker.value) picker.value.value = ""
	}
}

function detail(step) {
	return JSON.stringify(step.arguments || {}, null, 2) + "\n\n" + (step.outcome || "")
}

async function showPreview(message) {
	if (message.preview) {
		message.preview = null
		return
	}
	message.loading = true
	try {
		message.preview = await callMethod("embark.copilot.preview", { name: message.set.name })
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		message.loading = false
	}
}

async function scrollDown() {
	await nextTick()
	if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
}
</script>
