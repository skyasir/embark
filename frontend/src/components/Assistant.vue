<template>
	<div v-if="o?.assistant && state.chatOpen" class="contents">
		<!-- A column beside the sidebar, not a floating box: the checklist stays
		     visible while the customer talks. -->
		<aside
			class="fixed inset-0 z-10 flex flex-col border-r border-outline-gray-1 bg-surface-white sm:static sm:z-0 sm:w-[360px] sm:shrink-0"
		>
			<header class="flex h-12 shrink-0 items-center gap-2 border-b border-outline-gray-1 px-4">
				<FeatherIcon name="message-circle" class="size-4 text-ink-gray-6" />
				<span class="flex-1 text-base font-medium text-ink-gray-9">Ask Embark</span>
				<Button variant="ghost" icon="x" label="Close" @click="state.chatOpen = false" />
			</header>

			<div ref="scroller" class="flex-1 space-y-3 overflow-y-auto px-4 py-4">
				<div v-if="!messages.length" class="space-y-3">
					<p class="text-base leading-relaxed text-ink-gray-6">
						Tell me about your business in your own words and I'll fill in the questions for you.
						You can always answer them yourself instead.
					</p>
					<button
						v-for="example in EXAMPLES"
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
					<div v-else class="mr-4 whitespace-pre-line text-ink-gray-8">{{ m.content }}</div>
				</div>

				<div v-if="busy" class="flex items-center gap-2 text-base text-ink-gray-5">
					<LoadingIndicator class="size-4" />
					Thinking…
				</div>
			</div>

			<form class="ft-fill shrink-0 border-t border-outline-gray-1 p-3" @submit.prevent="send(draft)">
				<div class="flex gap-2">
					<FormControl
						v-model="draft"
						class="flex-1"
						placeholder="We sell tiles wholesale from 3 godowns…"
						:disabled="busy"
					/>
					<Button variant="solid" icon="arrow-up" label="Send" :disabled="busy || !draft.trim()" @click="send(draft)" />
				</div>
			</form>
		</aside>
	</div>
</template>

<script setup>
import { computed, nextTick, ref } from "vue"
import { Button, FeatherIcon, FormControl, LoadingIndicator, toast } from "frappe-ui"

import { api, errorText } from "../data/api"
import { setOverview, state } from "../data/store"

const EXAMPLES = [
	"We sell auto parts wholesale from two godowns.",
	"We make furniture to order and buy the timber in.",
	"We're a services firm — no stock at all.",
]

const o = computed(() => state.overview)
const draft = ref("")
const busy = ref(false)
const messages = ref([])
const scroller = ref(null)

async function send(text) {
	const message = (text || "").trim()
	if (!message || busy.value) return
	draft.value = ""
	messages.value.push({ role: "user", content: message })
	busy.value = true
	await scrollDown()
	try {
		const result = await api("ask", {
			message,
			onboarding: state.id,
			// Only the plain turns: the server rebuilds its own tool context.
			history: JSON.stringify(messages.value.slice(-10, -1)),
		})
		messages.value.push({ role: "assistant", content: result.reply })
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

async function scrollDown() {
	await nextTick()
	if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
}
</script>
