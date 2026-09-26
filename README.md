## Embark

*Get your data ready for ERPNext.*

Gets a customer's data ready **before** a fixed-hour, standard ERPNext
implementation starts, so the implementation hours go on configuration and
training rather than on chasing spreadsheets.

Once the customer accepts the implementation plan, a consultant creates an
**Embark Onboarding** for their package and invites them. The customer signs
in to a simple portal at `/embark` that shows only the steps their package
needs:

1. **Company details**: name, country, currency, financial year and tax number.
2. **One step per data area** (Users, Warehouses, Customers, Suppliers, Items and
   so on). The customer downloads a template or uploads their own sheet. The
   tool matches their columns to ERPNext fields and checks every row. Problems
   are explained in plain language and can be fixed on screen.
3. **Send for review**, available when every required step is ready.

The consultant then reviews the onboarding in the desk, approves it or returns
it with notes, and downloads the prepared data as ERPNext-shaped Excel files.

### How the checks work

Each data area points at a real ERPNext doctype. The rules come from that
doctype's own meta: required fields, dropdown choices, field types and links.
Links are checked across the customer's own sheets (an item's group must be in
the Item Groups sheet or be one of ERPNext's standard groups), so broken
references are caught before anything reaches ERPNext.

Nothing is written to ERPNext by this app. The customer's file is never
modified; fixes made on screen are stored separately and applied on every read.

### Setup

```bash
bench get-app <repo-url>
bench --site <site> install-app embark
```

The onboarding site needs ERPNext installed, because the checks read ERPNext's
doctypes. Installing creates two roles, **Embark Consultant** and
**Embark Customer**, plus the four packages and seven data areas of the
fast-track plan. Both packages and data areas can be edited in the desk.

To rebuild the portal after changing `frontend/`:

```bash
cd apps/embark/frontend && yarn install && yarn build
```

### Compatibility

Frappe and ERPNext v15 and v16.

### License

MIT
