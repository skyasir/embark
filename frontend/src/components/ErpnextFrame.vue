<template>
	<!-- Fills whatever it is put in. Giving it a pixel height meant measuring
	     the window and subtracting this chrome by hand, which was wrong by the
	     height of this bar. -->
	<div class="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-outline-gray-2">
		<!-- A browser's worth of chrome and no more: where you are, a way to
		     reload it, and a way out into a full tab. -->
		<div class="flex shrink-0 items-center gap-2 border-b border-outline-gray-1 bg-surface-gray-1 px-2 py-1.5">
			<FeatherIcon name="lock" class="size-3 shrink-0 text-ink-gray-4" />
			<span class="min-w-0 flex-1 truncate font-mono text-xs text-ink-gray-5">{{ path }}</span>
			<button
				class="rounded p-1 text-ink-gray-5 transition-colors hover:bg-surface-gray-3 hover:text-ink-gray-8"
				aria-label="Reload"
				@click="reload()"
			>
				<FeatherIcon name="refresh-cw" class="size-3.5" />
			</button>
			<a
				:href="path"
				target="_blank"
				rel="noopener"
				class="rounded p-1 text-ink-gray-5 transition-colors hover:bg-surface-gray-3 hover:text-ink-gray-8"
				aria-label="Open in a new tab"
			>
				<FeatherIcon name="external-link" class="size-3.5" />
			</a>
		</div>

		<iframe
			:key="key"
			:src="path"
			class="block min-h-0 w-full flex-1 bg-surface-white"
			:style="height ? { height: `${height}px`, flex: 'none' } : {}"
			title="ERPNext"
		/>
	</div>
</template>

<script setup>
import { ref, watch } from "vue"
import { FeatherIcon } from "frappe-ui"

const props = defineProps({
	// A path on this very site. Embark runs inside ERPNext, so there is nothing
	// remote to reach for and nothing to sign in to twice.
	path: { type: String, default: "/app" },
	// A pixel height when something needs one; otherwise it fills its parent.
	height: { type: Number, default: 0 },
	// Bumped when the page should be read again, address unchanged.
	seq: { type: Number, default: 0 },
})

const key = ref(0)

function reload() {
	key.value += 1
}

// Pointed somewhere new, it loads that rather than keeping the old page.
watch(() => props.path, reload)

// Nudged, it looks again even at the same address: a record that has just
// been written into a list does not change the list's address.
watch(
	() => props.seq,
	(now, before) => now !== before && reload()
)
</script>
