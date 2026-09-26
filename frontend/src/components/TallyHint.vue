<template>
	<Callout v-if="tally" tone="info" icon="download-cloud">
		<strong>You use Tally, so you don't have to type all of this again.</strong>
		<p class="mt-1">
			Frappe's Tally Migrator reads an export from Tally Prime straight into ERPNext — customers,
			suppliers, items, accounts and opening balances. Fill in the steps below for anything Tally
			doesn't hold, and leave the rest to the migration.
		</p>

		<div v-if="tally.installed" class="mt-3">
			<Button v-if="o.can_use_desk" size="md" icon-left="external-link" @click="open">
				Open Tally Migrator
			</Button>
			<p v-else class="text-ink-gray-6">
				It opens in the desk, which is available once ERPNext's setup wizard has been run.
			</p>
		</div>

		<template v-else-if="o.is_staff">
			<p class="mt-2 text-ink-gray-6">Tally Migrator is not installed on this site yet:</p>
			<pre class="mt-1 overflow-x-auto rounded bg-surface-gray-2 px-3 py-2 text-sm text-ink-gray-8"
			>bench get-app {{ tally.repo }}
bench --site {{ site }} install-app tally_migrator</pre>
		</template>

		<p v-else class="mt-1 text-ink-gray-6">
			Your consultant will bring the Tally data across during the implementation.
		</p>
	</Callout>
</template>

<script setup>
import { computed } from "vue"
import { Button } from "frappe-ui"

import Callout from "./Callout.vue"
import { state } from "../data/store"

const o = computed(() => state.overview)
const tally = computed(() => o.value?.tally)
const site = computed(() => window.location.hostname)

function open() {
	window.location.href = tally.value.route
}
</script>
