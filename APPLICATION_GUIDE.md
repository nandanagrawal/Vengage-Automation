# Vengage Invoice Automation — Application Guide

This guide explains what the application does and how to operate it end to end: syncing from QuickBooks, adding centres, setting up each customer's products and pricing, grouping centres onto invoices, and running the monthly invoice import.

It describes the app **as it behaves today** (checked against the code). Places where the behaviour may surprise you are collected in [Things to know](#14-things-to-know-gotchas).

---

## Contents

1. [What the app does](#1-what-the-app-does)
2. [Roles and access](#2-roles-and-access)
3. [Two-factor authentication](#3-two-factor-authentication)
4. [First-time setup](#4-first-time-setup)
5. [Syncing from QuickBooks](#5-syncing-from-quickbooks)
6. [Customers](#6-customers)
7. [Centres](#7-centres)
8. [Sheet Column Catalog](#8-sheet-column-catalog)
9. [Products and services on a customer: Flat, Slab, Fixed, Input](#9-products-and-services-on-a-customer-flat-slab-fixed-input)
10. [Grouping centres onto one invoice](#10-grouping-centres-onto-one-invoice)
11. [The monthly import: upload → validate → preview → generate](#11-the-monthly-import)
12. [What gets created in QuickBooks](#12-what-gets-created-in-quickbooks)
13. [Google Drive attachments](#13-google-drive-attachments)
14. [Things to know (gotchas)](#14-things-to-know-gotchas)
15. [Dashboard, invoice status and webhooks](#15-dashboard-invoice-status-and-webhooks)
16. [Scripts and maintenance](#16-scripts-and-maintenance)
17. [Monthly checklist](#17-monthly-checklist)

---

## 1. What the app does

Each month a **RAW Data-Imaging spreadsheet** arrives with one row per centre and one column per metric (for example "Confirmed Appointment (4)"). The app turns that sheet into **draft invoices in QuickBooks Online (QBO)**, one per customer (or per group of that customer's centres), priced from each customer's own configuration.

```
QuickBooks ──Sync──▶ Customers + Products/Services (pulled into the app)
                          │
      You configure, per customer:
        • Category (Direct or Partner — see section 9)
        • Centres (names that appear in the sheet, each with its own Drive file name(s))
        • Products & services  → booking type (Flat / Slab / Fixed / Input) + rate
                               → which sheet column supplies the quantity (Flat/Slab)
                               → which centre it belongs to (Partner customers only)
        • Invoice groupings (which centres share one invoice)
        • Payment terms, etc.
                          │
Monthly sheet ──Import──▶ Validate (incl. Drive check) → [Enter quantities, if any Input rows]
                        → Preview → Generate ──▶ Draft invoices in QuickBooks
```

Key principles:

- **QuickBooks is the source of truth for customers and products.** They are pulled in; edits made in this app are local and never pushed back.
- **Pricing and quantity rules live on each customer's service row**, not on the product. The same product can be priced and mapped differently for every customer — and for a Partner customer, differently for every centre too (see [section 9](#9-products-and-services-on-a-customer-flat-slab-fixed-input)).
- **The app creates invoices in QuickBooks but does not email them.** Sending is done from QuickBooks.

---

## 2. Roles and access

| | Admin | Supervisor |
|---|---|---|
| Sign in, change own profile/password | ✅ | ✅ |
| Sync from QuickBooks, run imports | ✅ | ✅ |
| View all customers | ✅ | ✅ |
| Edit a customer, its centres and groupings | ✅ any customer | Only customers **they created** |
| Approve / reject / delete customers | ✅ | ❌ |
| Sheet Column Catalog (add / remove columns) | ✅ | ❌ (page hidden) |
| Create other users | ✅ | ❌ |

Important consequence: customers pulled from QuickBooks have **no owner**, so in practice **only admins can edit synced customers** (their services, centres and groupings).

The very first user is created through the bootstrap endpoint `POST /api/v1/auth/register/first` and must be an admin. It is blocked once any user exists. After that, admins create users through `POST /api/v1/auth/register`.

---

## 3. Two-factor authentication

Two-factor authentication (TOTP, via an authenticator app) is **mandatory for every user**, admin and supervisor alike. There is no opt-out and no per-user toggle.

**First login after this feature shipped, or for any newly-created user:**

1. Sign in with email and password as usual.
2. The app shows a **QR code** and a manual entry key. Scan the QR code with an authenticator app (Google Authenticator, Authy, 1Password, etc.) — or type the manual key in by hand if you can't scan it.
3. Enter the 6-digit code the app now shows.
4. You're given **10 backup codes**, shown once. Save them somewhere safe — each one can be used in place of a 6-digit code if you lose access to your authenticator app, and is consumed after a single use.

**Every subsequent login** asks for the current 6-digit code (or a backup code). Checking **"Remember this device"** skips the prompt on that same browser for **7 days**; it's a cookie scoped to this app's login/2FA endpoints, so it has no effect anywhere else and expires on its own.

**Backup codes:** Settings page → **Two-factor authentication** → **Regenerate backup codes** (requires the current 6-digit code) replaces all 10 codes at once — do this after using a few, since there's no partial top-up.

**Lost both your device and your backup codes?** There is no self-service recovery — ask an admin to clear your 2FA via:

```bash
curl -X POST http://localhost:8000/api/v1/auth/users/{user_id}/reset-2fa \
  -H "Authorization: Bearer <admin's access token>"
```

(or the same call through the `/docs` Swagger UI). This clears the account's TOTP secret, backup codes and remembered devices — the next login walks that user through setup again from scratch, exactly like a brand-new account. There is currently no "Users" page in the app to trigger this from a button; it's API-only.

---

## 4. First-time setup

### Run the app

```bash
# Backend
cd backend
conda activate myenv
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm run dev
```

### Backend environment (`backend/.env`)

Copy `backend/.env.example` and fill in the values. Never commit real values.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection. If unset, the app falls back to the default in `app/core/config.py`. |
| `JWT_SECRET` | Login token signing key. Use a long random string (`openssl rand -hex 32`). |
| `QBO_ENVIRONMENT` | `sandbox` or `production`. |
| `QBO_CLIENT_ID`, `QBO_CLIENT_SECRET` | Intuit app keys (use the matching sandbox/production pair). |
| `QBO_REDIRECT_URI` | Must match the Intuit developer portal exactly, e.g. `http://localhost:8000/api/auth/callback`. |
| `QBO_REALM_ID` | The QuickBooks company ID. |
| `QBO_LINE_TAX_CODE` | Tax code put on every invoice line (default `GST`). |
| `TOKEN_FILE_PATH` | Where OAuth tokens are stored after connecting (default: repo-root `tokens.json`). |
| `INTUIT_WEBHOOK_VERIFIER_TOKEN` | Enables the QuickBooks webhook endpoint (optional). |
| `GOOGLE_SERVICE_ACCOUNT_KEY_PATH` | Path to the Google service-account JSON for Drive attachments (optional). |
| `FRONTEND_URL`, `ALLOWED_ORIGINS` | Frontend origin / CORS. |

> **Keep secrets out of git.** `tokens.json` and the Google service-account key file must never be committed.

### Connect QuickBooks

1. Sign in to the app.
2. If QuickBooks isn't connected, the app shows a **Connect QuickBooks** prompt. Complete Intuit's authorisation.
3. The top bar then shows **QBO {environment} · Connected** with a **Disconnect** button.
4. If Intuit shows a redirect error, open `GET /api/auth/oauth-check` and compare the `redirect_uri` with the one registered in the Intuit developer portal (it must match character for character; `localhost` ≠ `127.0.0.1`).

---

## 5. Syncing from QuickBooks

**Where:** the **Sync** button at the top of the **Customers** page.

One click of Sync does three things:

| What is synced | Behaviour |
|---|---|
| **Customers** | Pulled from QuickBooks. New customers are created in the app as *Approved*. Existing customers are updated only if QuickBooks' copy is **newer** than the local one (last-write-wins). |
| **Products & services** ("Items") | The full QBO item catalog is upserted, **including inactive items** (stored as inactive). The tax code on each QBO item is also set to `QBO_LINE_TAX_CODE`. |
| **Invoice email activity** | A snapshot of the last 30 days of invoice email statuses, used for the Dashboard counters. Replaced on every sync. |

The result banner shows counts such as *Pulled n · Items upserted n · Items removed locally n · Email rows n*. (The banner also shows "Pushed" and "Created in QBO"; those are always 0 because customers are no longer pushed.)

### What is kept when a customer is re-synced

Fields that exist only in this app are **preserved** when QuickBooks data overwrites a customer: *Mail attachment*, *Cc*, *Bcc*, *Other*. Centres, services, groupings, **Customer Category** and **Payment terms** are never touched by sync either — QBO has no concept of them, so nothing in the sync path ever writes to them.

### What gets deleted

- A product that has been **fully deleted** in QuickBooks (no longer returned by QBO at all) is **deleted from the app on the next Sync**, and **every customer service row using it disappears with it**.
- A product that is only **made inactive** in QuickBooks stays in the app as inactive: it is hidden from the customer form's product list and is skipped when invoicing.

### Webhooks (optional, automatic updates)

If `INTUIT_WEBHOOK_VERIFIER_TOKEN` is set and the webhook URL (`POST /api/v1/webhooks/intuit`) is registered in Intuit, QuickBooks pushes changes automatically: customer create/update/merge refreshes that customer, and invoice create/update/delete keeps the app's invoice records and status current. Requests are verified by signature.

### If Sync says "No customers yet"

Customers only enter the app through Sync (the Customers page has no "add customer" button). Create the customer in QuickBooks first, then Sync.

---

## 6. Customers

**Where:** **Customers** page → search, then use the row actions (view, edit, invoice groupings, delete).

A customer must meet three conditions to be invoiced. The Validate step reports any that fail:

1. It has a **QuickBooks ID** (i.e. it was synced from QuickBooks).
2. It has a **primary email**.
3. It has **at least one active service with a valid rate** (see [section 9](#9-products-and-services-on-a-customer-flat-slab-fixed-input)).

### Fields on the customer edit page

| Section / field | Meaning |
|---|---|
| **Name and contact** | Names, Email, Cc, Bcc, phone, etc. Email is where QuickBooks addresses the invoice. |
| **Addresses** | Billing and shipping. |
| **Centres** | The centres that belong to this customer, each with its own optional Drive file name(s) — see [section 7](#7-centres). |
| **Customer Category** | **Direct Customer** (default) or **Partner** — decides whether services below are shared across all this customer's centres or mapped one-by-one to a centre. See [section 9](#9-products-and-services-on-a-customer-flat-slab-fixed-input). Not the same field as "Customer types" below. |
| **App fields → Services & rates** | The customer's products, booking types, sheet columns and prices — see [section 9](#9-products-and-services-on-a-customer-flat-slab-fixed-input). |
| **Customer types** | Free-form labels (e.g. Gold, Silver). Managed on the **Configuration** page. No effect on invoicing. |
| **Mail attachment** | Must be **on** for this customer's centres to ever be checked against Drive. Both this toggle and the centre's own Drive file name(s) field have to be set — either one being off/blank means that centre is never looked up. See [section 13](#13-google-drive-attachments). |
| **Payment terms (days)** | Invoice due date = invoice date + this many days. Default 15; must be a whole number above 0. Each customer has its own. |

### Status

Synced customers are *Approved*. A customer created by a supervisor through the API starts as *Pending* until an admin approves or rejects it. Status does not currently block invoicing.

---

## 7. Centres

A **centre** is a site under a customer. The spreadsheet has one row per centre, and the app finds each row's customer by the centre's name.

**How to add centres**

1. **Customers** → edit the customer.
2. Open the **Centres** section, add one or more names, optionally a **Drive file name(s)** value for each, and save.

**Rules**

- The name must match the sheet's **Center ID column (column 1) exactly** (case-insensitive, e.g. `VNG-IMG-14-A`).
- A centre name is **unique across the whole system**, not just within one customer. Saving a name that already exists is rejected with *"A center named '…' already exists."*
- Rows in the sheet whose Center ID matches no centre are skipped and reported.
- Removing a centre in the form deletes it when you save.

**Drive file name(s)**

A separate, optional field per centre — the exact file name(s) (extension included) to look up in the Google Drive folder when attaching raw-data files to that centre's invoice. It is **not** derived from the centre name; the two are independent. Comma-separate more than one file (e.g. `VNG-IMG-14-A.xlsx, VNG-IMG-14-A-B.xls`). A single file name may itself contain a comma (e.g. `VNG-IMG-18-F-Matrix, Lalor.xlsx`, a real suburb name) — this is handled correctly: a comma only starts a new file once the text before it already ends in `.xlsx`/`.xls`, so a comma that's part of the name itself doesn't get cut in half. Leaving it blank means this centre never triggers a Drive lookup or attachment. See [section 13](#13-google-drive-attachments) for exactly how and when this is checked.

---

## 8. Sheet Column Catalog

**Where:** sidebar → **Sheet Column Catalog** (admins only).

This is the list of **column headers that can appear in the RAW Data-Imaging sheet**. Each customer service row picks one of these as the source of its quantity, so the catalog must contain the exact header text first.

**How to add columns**

1. Open **Sheet Column Catalog**.
2. Paste one or more headers into the box — **one per line or comma-separated** — and click **+ Add**. Each becomes its own catalog entry.
3. Copy the header **exactly as written in the sheet** (for example `Confirmed Appointment (4)`). Matching at import time is case-insensitive and ignores surrounding spaces, but the wording, numbers and punctuation must be identical.

**Renaming a column:** click its name to edit it in place, then press Enter (or click away) to save. Existing customer mappings point at the column by its internal ID, so they're unaffected by a rename — but **future imports must use the new header text**, since matching is against the current name, not the old one. Renaming to a name already in the catalog is rejected.

**Removing a column:** click ✕ on it. A column that is still used by any customer's service row cannot be removed (*"this column is mapped to a customer's service"*); clear those mappings first.

A single column can be used by any number of customers and products.

---

## 9. Products and services on a customer: Flat, Slab, Fixed, Input

**Where:** customer edit page → **App fields → Services & rates** → add a row.

Products are the QuickBooks items pulled by Sync. Each row you add links one product to this customer and says **how it is billed**.

### Direct vs Partner: who a service row belongs to

Set on the customer edit page as **Customer Category**, above the Services & rates table:

- **Direct Customer** (default) — every service row applies **across all of this customer's centres**. This is the behaviour described throughout this section and is unchanged from before.
- **Partner** — the Services & rates table gains one extra column, **Centre**, at the start of every row. Each row now applies to **only that one centre** — the same product can be priced completely differently on two of a Partner customer's centres, each its own row. Every row is required to pick a centre; there is no customer-wide row for a Partner customer.

Everything else about a row — booking type, sheet column, rate, description — works identically for Direct and Partner; the centre scoping is the only difference. A customer's category can be changed at any time; existing rows keep whatever centre (or lack of one) they already had; use in the raw sheet is per-invoice, so a Partner row's centre must be a centre belonging to that same customer.

### The row, left to right

**(Centre — Partner only) → Product → Booking type → Sheet column (or Quantity, or Input) → Rate → ✕**, with a **Description** box underneath.

1. **Centre** (Partner customers only) — which of this customer's centres the row applies to.
2. **Product** — choose an active product.
3. **Booking type** — Flat, Slab, Fixed or Input (below). This decides what the next fields ask for.
4. **Sheet column** (Flat and Slab) — the catalog column this row reads its quantity from. For **Fixed** this becomes a **Quantity** box; for **Input** this field is skipped entirely (a note reads *"entered at import time"* instead).
5. **Rate** (Flat, Fixed and Input) or **tier ranges** (Slab).
6. **Description** (optional) — text that goes on the invoice line, described below.

### Flat

One rate for the whole quantity.

- **Quantity** = the value in the chosen sheet column for that centre.
- **Amount** = quantity × rate.
- **Line description**: `{Description} – {Centre Name} for {Mon YY}`. With no description it is just `{Centre Name} for {Mon YY}`.

Example: column `Confirmed Appointment (4)` = 120, rate $0.50 → one line, 120 × $0.50 = **$60.00**, described `Rockingham Radiology for Aug 26`.

### Slab

The rate depends on how large the total is. The total from the sheet column is **spread across the tiers**, and each tier becomes **its own invoice line** at that tier's rate.

You define tiers as **Start**, **End** (blank for the top, open-ended tier) and **Rate**.

Example: total **2755**, tiers `1–1000 @ $5`, `1001–2500 @ $4`, `2501+ @ $3`:

| Tier | Quantity | Amount |
|---|---|---|
| 1–1000 | 1000 | $5,000.00 |
| 1001–2500 | 1500 | $6,000.00 |
| 2501+ | 255 | $765.00 |

- Tier ranges must **not overlap**, and every tier needs a Start (≥ 1) and a Rate (> 0).
- A tier that gets zero quantity produces no line. If the total is below the first tier's start, there are no lines at all.
- **Line description**: `{Description} – {Centre Name} – {range} Booking for {Mon YY}`, for example `Imaging bookings – Rockingham Radiology – 1-1000 Booking for Aug 26`.

### Fixed

For a charge that is **not in the sheet** (monthly subscriptions, implementation or development fees). You enter a **fixed quantity**, a **rate** and a **description**. No sheet column is asked for.

- **Amount** = quantity × rate, every run, regardless of what the sheet contains.
- **Once per customer per run:** the fixed line is added to the **first invoice actually created** for that customer, not once per centre or per invoice, so a customer with several invoices is not billed twice. If that first invoice fails in QuickBooks, the charge moves to the next one.
- A customer with only fixed services still gets an invoice for each run in which one of their centres appears in the sheet.
- **Line description**: `{Description} for {Mon YY}`. With no description it uses the product name: `{Product name} for {Mon YY}`.
- Quantity and rate must both be above 0.

### Input

For a charge whose **amount isn't known until the operator types it in** — nothing read from the sheet, and nothing fixed in advance. Set up like Fixed but with **no Quantity box** at setup time; only a **Rate** and an optional **Description** are asked for. The quantity is typed in fresh **every run**, during Validate (see [section 11](#11-the-monthly-import)) — nothing about the quantity is ever stored on the row.

- If no quantity is entered for an Input row in a given run (or it's left at 0), that row simply produces **no line** — it does not block the run, it is just skipped.
- **Amount** = the quantity entered that run × rate.
- **Once per customer per run**, exactly like Fixed, for a **customer-wide** Input row (Direct customers, or a Partner row is instead billed once on the one invoice containing its own centre).
- **Line description**: identical format to Fixed — `{Description} for {Mon YY}`, or `{Product name} for {Mon YY}` with no description.
- Rate must be above 0. No sheet column, no stored quantity are allowed on an Input row.

### Description

The description is optional free text, stored per service row. For Flat and Slab it is **combined with** the automatic centre/month text (never replacing it). For Fixed and Input it is combined with the month.

### Row order = invoice line order

Drag a row by its **⠿** handle (left edge) to move it, then **Save**. Invoice lines follow this order **product by product across the whole invoice**: on a grouped invoice, every centre's line for the first row comes first, then every centre's line for the second row, and so on. Within one row, lines keep their centre order, and a Slab row's tiers stay in range order. Fixed and Input charges are placed by their row position too, not appended at the end. The Preview's line-item download uses the same order.

The standard SKU order (Olivia AI Complete Bookings → Provisional → Walk-in → Non Appointment Call Handling → Call Forwards → E-Referral Transmission → Greeting SMS → Manual SMS → Olivia Assist → Specialist Portal) can be re-applied to every customer with `scripts/set_service_order.py` — see [section 16](#16-scripts-and-maintenance).

### Using the same product more than once

A customer may have the **same product on several rows** as long as each row uses a **different sheet column** (for example one product billed off both `Provisional Appointment (5)` and `Confirmed Appointment (4)`) — or, for a Partner customer, a **different centre** (the same product and column can repeat once per centre). Each row produces its own line. The exact same product, column **and** centre combination twice is rejected. Fixed and Input rows have no column, so a customer can have several fixed/input rows for one product (one per centre, for Partner customers).

### What is required to save

| Type | Required |
|---|---|
| Flat | Sheet column, rate > 0 |
| Slab | Sheet column, at least one tier (Start ≥ 1, Rate > 0), no overlaps |
| Fixed | Quantity > 0, rate > 0, **no** sheet column |
| Input | Rate > 0, **no** sheet column, **no** stored quantity |

On a **Partner** customer, every row of every type also requires a **Centre**; on a **Direct** customer, no row may have one.

### What produces no invoice line

- A Flat/Slab row with no column set.
- A Flat/Slab row whose column **isn't present in the uploaded sheet** (skipped silently).
- An Input row with no quantity entered for that run (or 0).
- A row whose quantity comes out as 0, or whose rate is 0.
- Rows for inactive products.
- A Partner row whose centre isn't among the centres matched in the current sheet (it simply doesn't apply to that run).

If nothing at all is left for a customer, that customer's invoice is skipped with the message *"no line items — invoice skipped"*.

---

## 10. Grouping centres onto one invoice

By default a customer's centres don't share an invoice. A **grouping** says "these centres go on **one combined invoice**". Within that invoice **each centre still gets its own set of lines** (quantities are not summed across centres).

**Where to create one**

- **Customers** page → the **grid icon** on the customer's row (opens the form with that customer pre-selected), or
- **Configuration** page → **New invoice grouping**.

**Steps**

1. Choose the **Company** (customer).
2. Tick the centres to combine. Centres already in another grouping are greyed out and show *"in grouping #n"*.
3. Optionally add a **Title** (e.g. *March combined — North + East*).
4. Save. Groupings can be edited or removed later from the same page.

**Rules**

- A centre can belong to **only one grouping**.
- Only that customer's own centres can be grouped.
- A grouping with a single centre is allowed (see the note below on why you might want one).

**How invoices are then formed for a customer in one run**

| Centres | Result |
|---|---|
| Centres in the same grouping | One invoice for the group |
| Centres in different groupings | One invoice per grouping |
| Centres in **no** grouping | **All of them together on a single invoice** (see [Things to know](#14-things-to-know-gotchas)) |

The Preview step shows exactly which centres will land on which invoice before anything is created.

---

## 11. The monthly import

**Where:** sidebar → **Import** (tab **Generate**; tab **History** lists past uploads).

The steps are **Upload → Validate → Preview → Done**.

### The spreadsheet

Accepted: `.csv`, `.xlsx`, `.xls`.

- **Tab:** for `.xlsx` / `.xls` the app reads the tab named **`RAW Data-Imaging`**. If there is no tab with that name it quietly uses the workbook's first/active tab. (CSV has no tabs.)
- **Row 1** is the header row; everything below is data.
- **Column 1 — Center ID.** Matched case-insensitively to a centre's name. Blank IDs are skipped.
- **Column 2 — Center Name.** Used in line descriptions.
- **Column 3 — Center Prefix.** Fallback only; only the part before the first comma is used.
- **Column 4 onward — metrics.** The header of each must match a Sheet Column Catalog entry that a customer's service row points at (case-insensitive, spaces trimmed).
- Blank or non-numeric cells count as **0**.

### Step 1 — Upload

Choose the file. Also paste the **Google Drive folder link** here if any centre in this run has a Drive file name configured (see [section 13](#13-google-drive-attachments)) — it's checked as part of Validate, not just at the end, so it belongs here rather than later in the flow. Everything is checked before anything is created.

### Step 2 — Validate

The app checks every row and every affected customer:

| Level | Check |
|---|---|
| Row | Center ID is present |
| Row | Center ID is not repeated on another row |
| Row | Center exists in the app |
| Customer | Has a QuickBooks ID (sync it) |
| Customer | Has a primary email |
| Customer | Has at least one active service with a valid rate |
| Centre | If its customer has Mail attachment on **and** it has a Drive file name configured, that file exists in the Drive folder — **blocking**, no bypass (see [section 13](#13-google-drive-attachments)) |

If anything fails you land on **Fix validation errors**, where you can correct the cells and press **Re-validate**.

If validation passes but some matched customers have **Input**-priced services (see [section 9](#9-products-and-services-on-a-customer-flat-slab-fixed-input)), you land on **Enter quantities** first: one number box per Input row, grouped by customer (and centre, for Partner customers). Nothing here is saved — it's re-typed every run. Press **Continue** to re-check and proceed.

Once both are clean, you continue to Preview.

### Step 3 — Preview

Shows each customer, its invoice groups and each centre's values, with a warnings list. From here you can:

- **Edit values** directly. The button then reads **Submit with changes** and asks you to confirm.
- **Download** an Excel file with two sheets: **RAW Data-Imaging** (the sheet as edited) and **Invoice Data** (the lines that will be created, in QBO import layout, with the invoice date, due date and memo).

Then **Submit invoices**.

### Step 4 — Generate and Done

Generation runs in the background and the page updates on its own. The result shows centres matched/skipped and invoices created/failed, plus a list of errors and warnings. The upload's status becomes *completed*, *completed with errors* or *failed*.

**History tab:** every past upload with counts; open one to see its generated invoices (invoice number, customer, centres, status). Deleting a generated invoice here removes only the app's record — **it does not delete anything in QuickBooks**.

---

## 12. What gets created in QuickBooks

For each invoice the app sends QuickBooks:

| Field | Value |
|---|---|
| Customer | The customer's QuickBooks ID |
| Invoice date and each line's service date | **Last day of the previous month** (running in October gives 30 Sep) |
| Due date | Invoice date + the customer's **Payment terms (days)** |
| Message to customer | *"Thank you for your business and for being our valuable customer. Please find the details for the {Month}, {Year} month bookings. Hope you have a great day ahead."* |
| Memo on statement (private note) | `INVOICE {MMMYYYY}` (for example `INVOICE SEP2026`) |
| Bill-to email | The customer's primary email |
| Lines | One per Flat row, one per Slab tier, one per Fixed row, one per Input row with a quantity entered, in the customer's row order — see [section 9](#9-products-and-services-on-a-customer-flat-slab-fixed-input) |
| Tax | Every line uses `QBO_LINE_TAX_CODE` (default `GST`), amounts are tax-exclusive, and total tax is 10% of the invoice subtotal, rounded once for the whole invoice |

Invoice **numbers are assigned by QuickBooks**. The Preview shows an estimated next number from the last one the app saw.

The invoice is **created but not emailed** by the app. Review and send it from QuickBooks; once sent, the app learns the status through Sync or webhooks (see [section 15](#15-dashboard-invoice-status-and-webhooks)).

---

## 13. Google Drive attachments

Lets each invoice carry the **centre's own Excel file(s)** so they go out with the invoice email.

The mechanism needs **both** of two things set: the customer's **Mail attachment** toggle (see [section 6](#6-customers)) must be on, **and** the centre must have a **Drive file name(s)** value (see [section 7](#7-centres)). Either one missing means that centre is never looked up — turning Mail attachment off stops it for the whole customer even if its centres still list file names; a centre with no file name is skipped even when Mail attachment is on.

**One-time setup**

1. Create a Google Cloud project, enable the **Google Drive API** and create a **service account**.
2. Download its JSON key, save it on the server (outside git) and set `GOOGLE_SERVICE_ACCOUNT_KEY_PATH` to its path.
3. **Share the Drive folder with the service account's email address** (Viewer is enough). If the folder lives in a **Shared Drive**, add the service account as a **member of that Shared Drive**. A shared link alone does not grant access.

**Per centre:** set **Drive file name(s)** on the centre (customer edit page → Centres). Comma-separate more than one file for the same centre.

**Per run:** paste the Drive folder link in the **Google Drive folder link** box on the **Upload** step (see [section 11](#11-the-monthly-import)) — it's needed at Validate time now, not just Generate.

**How files are matched**

- The app lists the spreadsheet files in the folder (`.xlsx`, `.xls` or native Google Sheets).
- Matching is by the centre's configured file name **exactly**, case-insensitive, **extension included** — not derived from the centre's own name, and not a fuzzy/stem match. `VNG-IMG-14-A.xlsx` only matches a file literally named `VNG-IMG-14-A.xlsx` (or `.XLSX`, etc.) in the folder.
- If two files in the folder share the exact same name, the most recently modified wins.
- A grouped invoice gets the file(s) for **every** centre on it. If two of those centres happen to share the exact same file name, it's attached **once**, not once per centre.

**If a file is missing**

- **Validate blocks it.** A centre with a configured Drive file name that isn't found in the folder is a validation error, same severity as a missing email or QBO ID — there is no "generate anyway" bypass. Fix the file name, upload the file, or clear the centre's Drive file name field, then re-validate.
- If no Drive folder link was given at all but some matched centre needs one, that's also a blocking validation error.
- A centre with **no** Drive file name configured is never checked and never blocks anything.

---

## 14. Things to know (gotchas)

1. **Centres with no grouping are combined onto one invoice.** All of a customer's ungrouped centres in a run share a single invoice. To get a **separate invoice per centre**, create a **one-centre grouping** for each centre. (Some older comments in the code describe one invoice each; the running behaviour is the combined one.)
2. **Fully deleting a product in QuickBooks removes it, and all customer mappings using it, from the app on the next Sync.** Making it inactive is safe; deleting is not. Check who uses a product before deleting it in QuickBooks.
3. **Column names must match exactly.** A service row whose column isn't in the uploaded file quietly produces no line. If a customer is missing expected lines, compare the header in the sheet with the catalog entry character by character.
4. **The sheet tab name matters.** A tab called anything other than `RAW Data-Imaging` is ignored in favour of the first tab, without a warning.
5. **Only admins can edit synced customers.** Supervisors can edit only customers they created.
6. **Centre names are global.** The same centre name cannot be used under two customers.
7. **Lines with zero quantity or zero rate are not created.** A customer whose values are all zero gets no invoice.
8. **Edits in this app never go back to QuickBooks.** Change names, emails and addresses in QuickBooks and Sync.
9. **Deleting a generated invoice in the app does not delete it in QuickBooks.**
10. **The app does not email invoices.** Send them from QuickBooks.
11. **Service Codes** on the Configuration page are a legacy reference list. They no longer affect pricing or invoicing.
12. **Payment terms are per customer.** Set them on the customer, otherwise the default of 15 days applies.
13. **Both Mail attachment AND the centre's Drive file name must be set for that centre to be checked.** Either one alone does nothing — turning Mail attachment off stops the Drive check for that customer entirely, even if its centres still have file names configured; a centre with no file name is skipped even if Mail attachment is on. See [section 13](#13-google-drive-attachments).
14. **A Partner customer's service row is scoped to exactly one centre.** If that centre doesn't appear in a given month's sheet, the row simply produces nothing that run — this is not an error. Switching a customer between Direct and Partner does not touch existing rows' centre assignment; check them after switching.
15. **Input quantities are never remembered.** They're re-typed on every single run at Validate, even if you entered the same number last month — there is no "same as last time" shortcut.

---

## 15. Dashboard, invoice status and webhooks

**Dashboard** shows:

| Card | Meaning |
|---|---|
| Total Customers | Customers in the app |
| Imports Today | Uploads created today (UTC) |
| Invoices Sent | Invoices in the last-30-day snapshot with status *EmailSent* |
| Delivery Failures | Invoices in the snapshot with status *NeedToSend* (queued, not delivered) |

The snapshot refreshes each time you press **Sync**, so run Sync first for current numbers. A searchable table lists recent invoices with their sent status.

**Invoice status** for invoices the app created starts as *pending* and becomes *sent* once QuickBooks reports it emailed (through Sync or a webhook). An invoice deleted in QuickBooks is marked *deleted* when the webhook reports it.

**Configuration page** holds the invoice groupings ([section 10](#10-grouping-centres-onto-one-invoice)), **customer types**, and the legacy **service codes** list.

---

## 16. Scripts and maintenance

Run from `backend/`. Scripts marked *dry-run by default* only write when given `--apply`.

| Script | Purpose |
|---|---|
| `scripts/export_customer_service_matrix.py` | Exports an Excel matrix of customers × products showing each customer's price (flat rate, fixed `qty × rate`, or slab tiers). Only includes active products with valid pricing. `--out <file>` to choose the path. |
| `scripts/create_product_and_service.py` | Creates a product in QuickBooks and mirrors it locally. `--list-accounts` shows valid income accounts; *dry-run by default*; supports `--file products.json` for bulk. |
| `scripts/backfill_customer_service_columns.py` | One-off. Copied the old product-level column mapping down onto each customer service row. *Dry-run by default.* Already used during the move to per-customer columns. |
| `scripts/migrate_slab_customers.py` | One-off. Converted the old "(Slab-N)" product convention into slab tiers on a single product. *Dry-run by default.* |
| `scripts/import_excel_data.py` | Older bootstrap that created centres and customer-service rows from an Excel file (`--validate` for a dry run). It predates sheet columns and booking types, so rows it creates have **no sheet column** and need one set afterwards. |
| `scripts/set_service_order.py` | Reorders every customer's service rows (and so invoice lines) to the standard SKU order listed at the top of the script; unlisted products go after, keeping their relative order. *Dry-run by default*; needs `--database-url`. |
| `scripts/clear_invoice_uploads.py` | Deletes all uploads and the generated-invoice records made from them (`--dry-run` to preview). Does not touch QuickBooks. |

### Database migrations

```bash
cd backend
alembic upgrade head
```

Migrations added for the current feature set:

| Migration | Change |
|---|---|
| `0016` | Adds `sheet_column_id` and `description` to customer services; allows the same product on several rows with different columns. |
| `0017` | Drops the old product-level column-mapping table. **Run the backfill script before this one** on any database that still has old mappings to carry over. |
| `0018` | Adds `quantity` for Fixed pricing. |
| `0019` | Adds `centers.drive_file_names`; `customers.category` (Direct/Partner); `customer_product_and_services.center_id` for Partner centre-scoped rows; widens the row-uniqueness constraint to include it. No migration is needed for the `Input` pricing type itself — it's a plain string value, added the same way `Fixed` was in `0018`. |
| `0020` | Two-factor authentication: `users.totp_secret`/`totp_enabled`, `user_backup_codes`, `user_trusted_devices`. |
| `0021` | Adds `customer_product_and_services.position` (row / invoice-line order), backfilled from the existing order. |

If you are migrating an older database, apply `0016`, run the backfill script, then upgrade to `head`, rather than jumping straight to the latest revision.

---

## 17. Monthly checklist

**Before the month's import**

1. Create or change any customers/products in **QuickBooks**, then press **Sync** on the Customers page.
2. For any new customer: set its **Customer Category** (Direct or Partner), add its **Centres** (with Drive file name(s) if attaching), its **Services & rates** (booking type, sheet column/quantity/input, rate, description — plus a centre per row if Partner), and its **Payment terms**.
3. If the sheet has a new column: add it in **Sheet Column Catalog**, then point the relevant customer service rows at it.
4. If centres should share an invoice: create the **grouping**. If they should have separate invoices: give each its own one-centre grouping.
5. Put each centre's file(s) in the Google Drive folder, named **exactly** as configured on that centre, extension included (only if that centre has a Drive file name set).

**Running the import**

6. **Import** → upload the sheet, pasting the Drive folder link if any centre needs one → fix anything under *Fix validation errors* → **Re-validate**.
7. If any Input-priced services are in this run, enter their quantities on **Enter quantities** and **Continue**.
8. On **Preview**, check the invoice groups and totals; use **Download** for a copy.
9. **Submit invoices** and watch the result.

**After**

10. Open QuickBooks, review the draft invoices, and send them.
11. Press **Sync** to bring back sent/failed status, then check the **Dashboard**.
