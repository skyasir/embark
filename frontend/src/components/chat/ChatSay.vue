<template>
	<p class="whitespace-pre-line text-base leading-relaxed text-ink-gray-8">{{ props.text }}</p>
</template>

<script setup>
// Plain words. The model reaches for this when there is nothing to show.
defineProps({ props: { type: Object, required: true } })
</script>
