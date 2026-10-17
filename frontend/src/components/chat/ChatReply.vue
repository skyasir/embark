<template>
	<!-- One answer, its parts stacked. Everything the model draws hangs here,
	     because the language renders a single root and an answer is usually a
	     sentence and a thing to do. -->
	<div class="space-y-2">
		<component :is="rendered" />
	</div>
</template>

<script setup>
import { computed, h } from "vue"

const componentProps = defineProps({
	props: { type: Object, required: true },
	renderNode: { type: Function, required: true },
})

const rendered = computed(() => () => h("div", { class: "space-y-2" }, componentProps.renderNode(componentProps.props.parts)))
</script>
