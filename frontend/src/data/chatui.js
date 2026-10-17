/**
 * What Ask Embark is allowed to draw.
 *
 * The chat used to answer in plain text, which meant the customer read a
 * sentence about a question and then went and found it. Now the model answers
 * in OpenUI Lang (thesysdev/openui, MIT) and the reply can carry the real
 * control — the wizard's own question, the record it just wrote.
 *
 * The model does not invent interface. It may only name one of the components
 * below, and each one is Embark's: the same question field as the Setup page,
 * saved through the same endpoint. Anything it names that is not here renders
 * as nothing, and the raw text is shown instead.
 */
import { createLibrary, defineComponent } from "@openuidev/vue-lang"
import { z } from "zod"

import ChatQuestion from "../components/chat/ChatQuestion.vue"
import ChatReply from "../components/chat/ChatReply.vue"
import ChatRecord from "../components/chat/ChatRecord.vue"
import ChatSay from "../components/chat/ChatSay.vue"
import ChatSteps from "../components/chat/ChatSteps.vue"

const Say = defineComponent({
	name: "Say",
	description: "A sentence or two of plain words. Use this for anything that is only to be read.",
	props: z.object({
		text: z.string().describe("What to say, in plain language."),
	}),
	component: ChatSay,
})

const Question = defineComponent({
	name: "Question",
	description:
		"Ask one of the setup questions, with its own answer box, so the customer can answer it here " +
		"instead of going to the Setup page. Use the question's key exactly as it was given to you.",
	props: z.object({
		key: z.string().describe("The question key, for example company_name or valuation_method."),
	}),
	component: ChatQuestion,
})

const Record = defineComponent({
	name: "Record",
	description: "Show a record that is now in ERPNext, with a link to open it.",
	props: z.object({
		doctype: z.string().describe("The ERPNext doctype, for example Company or Item Group."),
		name: z.string().describe("The name of the record."),
		note: z.string().optional().describe("One line about what it is for."),
	}),
	component: ChatRecord,
})

const Steps = defineComponent({
	name: "Steps",
	description: "A short list of what is done and what is left. Four or five lines at most.",
	props: z.object({
		items: z
			.array(
				z.object({
					label: z.string().describe("The step, in the customer's words."),
					done: z.boolean().optional().describe("True when it is already answered."),
				})
			)
			.describe("The steps, in the order they happen."),
	}),
	component: ChatSteps,
})

const Reply = defineComponent({
	name: "Reply",
	description: "One answer, with its parts one under another. This is always the root.",
	props: z.object({
		parts: z.any().describe("The components that make up the answer, in the order they are read."),
	}),
	component: ChatReply,
})

export const library = createLibrary({
	components: [Reply, Say, Question, Record, Steps],
	root: "Reply",
})

/**
 * The instructions that go with the library, generated from the library
 * itself, so a component added here is a component the model is told about.
 */
export function uiPrompt() {
	return library.prompt({
		preamble:
			"You are Embark, setting up ERPNext for a business. Answer with the components below. " +
			"Keep it short: a customer reads this, not a developer.",
		additionalRules: [
			"Answer with the program and nothing else. No sentence before it, no sentence after it, " +
				"and never a code fence.",
			'Arguments are positional. Write Question("company_name"), never Question(key="company_name").',
			"Everything you define must end up inside root's parts, or it does not show at all.",
			"Use Question whenever the next thing you need is an answer to a setup question, and let " +
				"the component show the wording — do not repeat the question in a Say as well.",
			"Never invent a component that is not listed.",
			"Never put a doctype name or a field name in front of a customer.",
		],
		examples: [
			'root = Reply([intro, ask])\nintro = Say("Let us start with who the business is.")\nask = Question("company_name")',
			'root = Reply([made])\nmade = Record("Item Group", "Corrugated Boxes", "Your products sit under this.")',
		],
	})
}
