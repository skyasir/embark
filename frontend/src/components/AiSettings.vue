<template>
	<Dialog v-model="show" :options="{ title: 'Configure AI' }">
		<template #body-content>
			<div v-if="loading" class="flex justify-center py-8">
				<LoadingIndicator class="size-5 text-ink-gray-5" />
			</div>
			<div v-else class="ft-fill space-y-4">
				<p class="text-base leading-relaxed text-ink-gray-6">
					The chat fills in the interview for a customer who would rather describe their business than
					click through the questions. It can do nothing else: it never writes to ERPNext, and the plan
					is still worked out from the answers.
				</p>

				<FormControl
					v-model="form.enabled"
					type="checkbox"
					label="Offer the chat on this site"
				/>
				<FormControl
					v-model="preset"
					type="select"
					label="Where the AI runs"
					:options="presetOptions"
					description="Pick one and paste a key. Groq and Google give keys away free."
					@update:model-value="usePreset"
				/>

				<div v-if="chosen?.how" class="rounded-lg bg-surface-gray-2 px-3 py-2 text-sm text-ink-gray-7">
					{{ chosen.how }}
					<a
						v-if="chosen.link"
						:href="chosen.link"
						target="_blank"
						rel="noopener"
						class="underline hover:text-ink-gray-9"
					>
						Get a key
					</a>
				</div>

				<div v-if="preset === 'Something else'" class="space-y-4">
					<FormControl
						v-model="form.provider"
						type="select"
						label="Provider"
						:options="['OpenAI compatible', 'Anthropic']"
					/>
					<FormControl v-model="form.base_url" label="Address" placeholder="https://api.openai.com/v1" />
				</div>

				<FormControl v-model="form.model" label="Model" placeholder="gpt-4o-mini" />
				<FormControl
					v-model="form.api_key"
					type="password"
					label="API key"
					:placeholder="settings.has_key ? 'Saved — leave blank to keep it' : 'sk-…'"
					description="Kept encrypted on this site. A local model needs no key."
				/>
			</div>
		</template>
		<template #actions>
			<Button variant="solid" class="w-full" :loading="saving" @click="save">Save</Button>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue"
import { Button, Dialog, FormControl, LoadingIndicator, toast } from "frappe-ui"

import { api, errorText } from "../data/api"
import { loadOverview } from "../data/store"

const show = defineModel({ type: Boolean })

// The endpoints worth naming, so nobody has to look one up. Free tiers first.
const PRESETS = [
	{
		label: "Groq (free)",
		provider: "OpenAI compatible",
		base_url: "https://api.groq.com/openai/v1",
		model: "llama-3.3-70b-versatile",
		how: "Free, fast, and good at tools. Sign in with Google and copy the key.",
		link: "https://console.groq.com/keys",
	},
	{
		label: "Google Gemini (free tier)",
		provider: "OpenAI compatible",
		base_url: "https://generativelanguage.googleapis.com/v1beta/openai",
		model: "gemini-2.0-flash",
		how: "A free tier that is plenty for onboarding a few customers.",
		link: "https://aistudio.google.com/apikey",
	},
	{
		label: "OpenAI",
		provider: "OpenAI compatible",
		base_url: "https://api.openai.com/v1",
		model: "gpt-4o-mini",
		how: "Paid, a few paise per onboarding.",
		link: "https://platform.openai.com/api-keys",
	},
	{
		label: "Anthropic (Claude)",
		provider: "Anthropic",
		base_url: "https://api.anthropic.com",
		model: "claude-sonnet-4-6",
		how: "Paid. The sharpest of these at following instructions.",
		link: "https://console.anthropic.com/settings/keys",
	},
	{
		label: "On this server (Ollama)",
		provider: "OpenAI compatible",
		base_url: "http://localhost:11434/v1",
		model: "qwen2.5:7b",
		how: "Nothing leaves the machine. Needs no key, and is the weakest of these.",
		link: "",
	},
	{ label: "Something else", provider: "OpenAI compatible", base_url: "", model: "", how: "", link: "" },
]

const preset = ref(PRESETS[0].label)
const presetOptions = PRESETS.map((p) => p.label)
const chosen = computed(() => PRESETS.find((p) => p.label === preset.value))

function usePreset(label) {
	const p = PRESETS.find((x) => x.label === label)
	if (!p || p.label === "Something else") return
	form.provider = p.provider
	form.base_url = p.base_url
	form.model = p.model
}

const loading = ref(false)
const saving = ref(false)
const settings = ref({ has_key: false })
const form = reactive({ enabled: false, provider: "OpenAI compatible", base_url: "", model: "", api_key: "" })

watch(show, async (open) => {
	if (!open) return
	loading.value = true
	try {
		settings.value = await api("ai_settings")
		Object.assign(form, { ...settings.value, api_key: "" })
		// Show the preset this site is already on, if it is one of them.
		preset.value =
			PRESETS.find((p) => p.base_url === form.base_url)?.label ||
			(form.base_url ? "Something else" : PRESETS[0].label)
		if (!form.base_url) usePreset(preset.value)
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		loading.value = false
	}
})

async function save() {
	saving.value = true
	try {
		settings.value = await api("save_ai_settings", { ...form, enabled: form.enabled ? 1 : 0 })
		toast.success(settings.value.on ? "Chat is on" : "Saved")
		show.value = false
		await loadOverview()
	} catch (e) {
		toast.error(errorText(e))
	} finally {
		saving.value = false
	}
}
</script>
