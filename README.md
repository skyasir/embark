## Embark

*Get your data ready for ERPNext.*

Embark prepares a customer's data **before** a fixed-hour, standard ERPNext
implementation starts, so the implementation hours go on configuration and
training rather than on chasing spreadsheets.

It runs on the customer's own ERPNext site: you create the site with Embark
installed and hand it over, usually before ERPNext's setup wizard has been run.
One site, one onboarding.

### The customer's journey

1. **Tell us about your business.** A short interview: what they use today, what
   the business does, whether it keeps stock, makes anything, sells from orders,
   tracks batches or serial numbers, is tax registered. Follow-up questions
   appear only when they are relevant, and "Not sure" is always allowed.
2. **Company details**: name, country, currency, financial year and tax number.
3. **One step per kind of data** (Users, Warehouses, Customers, Suppliers,
   Items and so on) — but only the steps and columns the answers call for. A
   business that keeps no stock is never asked for warehouses, and an item
   sheet carries batch or serial columns only if they track them.
4. **Send for review**, once every required step is clean.

For each step the customer downloads a generated Excel template or uploads the
file they already keep. Their headings are matched to ERPNext fields, every row
is checked, and problems are explained in plain language and fixed on screen.

**Already on Tally?** Say so in the interview and Embark points at Frappe's
[Tally Migrator](https://github.com/frappe/tally_migrator) instead of asking for
the same masters in a spreadsheet — it opens from the portal when the app is
installed, and Embark shows how to install it when it isn't.

### Who can use it

Embark has no roles of its own. It is used by the site's **System Managers**,
and everything it reads or writes goes through ERPNext's own permissions.

A new site shows only ERPNext's setup wizard in the desk, so Embark works from
its own portal: start the onboarding, fill it in, review the data, approve it
or return it with a note, and download it in ERPNext's own shape.

Once ERPNext's setup wizard has been run, Embark is a normal app in the desk
too: a tile on the apps screen that opens the portal, and a sidebar with the
onboarding, the uploads, the data steps and the interview questions.

### The chat

Embark has one chat box. What it can do depends on who is asking: a customer's
chat fills in their interview, and a chat belonging to whoever holds the
**Embark Studio** role also changes the site — as a change set they apply and
can undo, never directly.

Point it at a provider under **Configure AI** in the portal. Anything serving
`/chat/completions` works (OpenAI, Ollama, vLLM, a Flow gateway), and Anthropic
is spoken natively. With nothing configured there is no chat at all.

**The model matters more than anything else here.** A small local model
(llama3.2:3b) mangles its own tool calls, invents question keys and picks the
wrong field types; Embark repairs what it can, and it still reads badly.
qwen2.5:7b is the smallest local model that behaves. A hosted model — GPT or
Claude — is better again, and costs a few paise per onboarding.

### How the checks work

Each data step points at a real ERPNext doctype, and the rules come from that
doctype's own meta: required fields, dropdown choices, field types and links.
Links are checked across the customer's own sheets (an item's group must be in
their Item Groups sheet, or be one of ERPNext's standard groups). On a site
whose setup wizard has not run yet, the standard units and groups that the
wizard will create are accepted, so "Nos" or "Commercial" are not flagged.

Nothing is written to ERPNext by this app. The customer's file is never
modified; fixes made on screen are stored beside it and applied on every read.

### Configuration, not code

Data steps, their columns, the interview questions and the conditions that
decide when each applies are all records you edit in the desk:

| Record | Holds |
|---|---|
| Embark Data Area | A step: its target doctype, its columns, its icon, when it applies |
| Embark Question | An interview question, its choices and when it is asked |
| Embark Onboarding | One customer: their answers, company details, progress |
| Embark Upload | One uploaded file, its column matching and its check results |

A condition is a short line read against the answers, for example
`keeps_stock == yes and tracks_batches == yes`. An unanswered or "Not sure"
question leaves the step visible, so nothing is skipped silently.

### Setup

```bash
bench get-app <repo-url>
bench --site <site> install-app embark
```

The site needs ERPNext, because the checks read ERPNext's doctypes. Installing
creates the data steps and the interview questions, all editable afterwards.

Open `/embark` on the site as the administrator to start the onboarding.

### Development

```bash
cd apps/embark && yarn install     # installs and builds the portal
cd frontend && yarn dev            # or run the portal against a bench
bench --site <site> run-tests --app embark
```

Do not run the test suite against a site you are keeping as a demo: it commits
as it goes, clears onboardings and completes the setup wizard.

### Compatibility

Frappe and ERPNext v15 and v16.

### License

**AGPL-3.0-or-later.** Embark's own code was MIT and still carries those
notices, but it now ships Frappe Flow's agent engine under
`embark/vendor/flow` — see the note there — and that is AGPL, so the app as a
whole is AGPL. Anyone who runs a modified Embark as a service has to publish
their changes.
