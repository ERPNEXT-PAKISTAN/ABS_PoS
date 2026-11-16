# ABS PoS foundation — milestone 1

## Delivery

The internal Frappe package remains `klik_pos`, preserving the existing installation and license notices. ABS display branding is configurable. The original project remains the Git upstream.

- Local POS: `http://127.0.0.1/abs_pos/pos`
- Setup and readiness: `http://127.0.0.1/abs_pos/setup`
- Native branding document: `http://127.0.0.1/desk/abs-pos-settings`
- Company, warehouse, currency, payment methods, cashiers, discount/rate/write-off flags and print format remain native ERPNext Company/POS Profile configuration. Setup links to those forms; it does not silently change an operational counter.
- Receipt footer applies to the new ABS Thermal Receipt format. Existing customer print formats are preserved; select ABS Thermal Receipt in the POS Profile to use it. Custom formats need their own equivalent field rendering.

## Optional ZATCA

No hard dependency or direct import of Beveren ZATCA is introduced. Setup reports Not installed / Disabled / Enabled / Unavailable per company. A company marked enabled with its integration absent is blocked at checkout instead of silently falling back. Enabled is a configuration status, not evidence of successful onboarding or compliance.

This release does not install ZATCA, fix the competing controller overrides, or activate production submission. Those remain a separate integration milestone. Installed/disabled/enabled detection is covered by mocked state tests, not a combined ZATCA runtime acceptance test.

## Access and checkout

Business customer/item/tax/history APIs require login. The deliberately public branding endpoint returns only administrator-selected display settings. Checkout uses native invoice permissions and validates profile assignment, company/warehouse read access, an open cashier shift, permitted payment methods, manual discounts, write-off limits and credit-sale policy. Invoice reads/refunds/draft actions check native access and the POS profile; non-manager invoice access is limited to the owner's invoices.

Cashier rates are recalculated from the configured selling Item Price when the profile disables rate changes. Missing configured prices stop the sale with an explanation. Business mode comes from the server profile. Item lookup uses SQL-bound values. This is a focused permission improvement, not a full audit of every original endpoint or industry workflow.

## Duplicate protection and recovery

Each cart has an ID and a bound POS Profile; checkout persists a stable request ID and the exact payload. The server's separate ABS Checkout Request table serializes identical requests using a MariaDB row lock until transaction commit. Successful response and invoice are committed together. Same-ID/different-payload requests are rejected. Failed transactions roll back so they can be corrected and retried.

The existing client cart persistence is retained but namespaced by cashier/profile. Session identity is verified before restoration. An uncertain checkout retains its exact request and offers Retry original checkout. Completed carts are cleared on recovery using their cart ID, while the submitted invoice remains available in history. Device storage is required; storage failure blocks recovery.

The legacy `beveren-cart-storage` record is left untouched and is not automatically imported: it has no reliable owner/profile identity. Checkout records and carts contain customer/transaction details, so protect shared device/browser profiles. This is online checkout recovery, not offline sales synchronization. Payment-terminal charging and external ZATCA acceptance are not transactional with MariaDB; neither is claimed solved here.

## Update and rollback

Back up the authorized local site before updating. After pulling the release, run `bench build --app klik_pos`, migrate the local site and reload the bench's web/workers. Keep the previous Git revision and database backup. A code rollback alone does not undo database changes or remove committed fiscal documents. This update adds two DocTypes and does not delete existing sales.

## Validation

- 16 backend tests: request replay/mismatch/failure, guest/unassigned-profile rejection, ZATCA states, payment/discount/shift rules, server-controlled business mode and bound item-code lookup.
- Real MariaDB two-process concurrency check: one callback executes and both callers receive the same stored response. The callback returns a test marker; no invoice/payment is created.
- Frontend identity tests: stable retries, pending-cart changes blocked, completed replay, distinct new carts and cashier isolation.
- Production Vite build passes. Full TypeScript checking still reports upstream errors; compared against the unchanged Git baseline, this change introduces no new diagnostics.
- Assigned-cashier profile/history/setup APIs and a configured priced-item invoice preview pass against the local site. No sale, payment, refund or stock posting was submitted by validation.
- Browser host unavailable: screen appearance, interactions, refresh recovery in a real browser and physical printing remain acceptance checks before customer rollout.

Commands from the app frontend directory:

```bash
node tests/checkoutIdentity.test.mjs
yarn build
```

Backend tests run in a connected Frappe test site via `unittest` or your normal Frappe test runner. Concurrency probe from bench/sites:

```bash
ABS_TEST_SITE=your-local-test-site ../env/bin/python -m klik_pos.tests.check_concurrency
```

### Local deployment note

The full-site migration reached an unrelated Analytics Studio after_migrate hook and failed because its existing desktop icon references missing Account Director and Marketing roles. No roles or permissions were changed to bypass this. ABS was deployed with an app-scoped schema/fixture/customization sync and cache/service reload. The unrelated full-site migration blocker still needs separate repair.

## ABS URLs and launcher

The React router uses `/abs_pos`. Old `/klik_pos` URLs redirect to the matching ABS route, preserving query parameters. Assets, APIs and the installed Python package intentionally remain under `klik_pos`. The desktop branding hook updates only this app's icon and retains its role restrictions, visibility and position. It runs after installation/migration and when branding is saved. The PWA manifest now starts at `/abs_pos/pos`. Existing installed browser shortcuts may need a refresh or reinstall to pick up manifest branding.

## Item invoice history

Use History on an item card, list row, or cart item. The popup offers Sales, Purchases and Selected customer. Select a customer in the POS cart to use the customer tab. New labels support Arabic/RTL and English.

History is read-only, limited to the latest eight submitted Sales Invoices or Purchase Invoices containing that item, within the active POS company's native document permissions. Read AND report permission on the relevant invoice DocType are required; purchase costs are not granted to cashiers automatically. The customer tab additionally checks Customer read permission. Child-field permissions redact restricted quantities/UOM/rates/amounts.

Draft/cancelled documents are excluded; submitted returns remain visible and marked. Order: posting date, posting time, creation and document name, descending. Distinct invoice selection prevents repeated lines consuming the eight-document limit. An invoice with different UOMs/rates for this item shows separate lines instead of an averaged price. Net rate and amount exclude tax and retain each invoice's currency. Links open the native ERPNext invoice in another tab. This does not include Purchase Orders, Purchase Receipts, Delivery Notes or unconsolidated POS Invoices.

Validation: 10 focused history tests cover company/customer/status filters, the eight-document limit, distinct selection, permission denial, restricted field redaction, repeated item lines and returns. Read-only local checks passed with populated purchase, sales and selected-customer results. Production build passed with no new TypeScript diagnostics against the existing baseline. Browser host remains unavailable, so modal appearance, click behavior and responsive layout require browser acceptance.
