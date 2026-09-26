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
					v-model="form.provider"
					type="select"
					label="Provider"
					:options="['OpenAI compatible', 'Anthropic']"
					description="&quot;OpenAI compatible&quot; covers OpenAI, Ollama, vLLM and anything else serving /chat/completions."
				/>
				<FormControl
					v-model="form.base_url"
					label="Address"
					placeholder="https://api.openai.com/v1"
					description="A local model runs at http://localhost:11434/v1."
				/>
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
import { reactive, ref, watch } from "vue"
import { Button, Dialog, FormControl, LoadingIndicator, toast } from "frappe-ui"

import { api, errorText } from "../data/api"
import { loadOverview } from "../data/store"

const show = defineModel({ type: Boolean })

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
