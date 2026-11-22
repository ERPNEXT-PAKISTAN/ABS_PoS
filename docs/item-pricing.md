# Item purchase costs and profit calculator

Open an item History popup in ABS PoS and select **Pricing / profit**. The item card or cart UOM is selected initially. Costs are shown in company currency per stock UOM; choose another configured UOM for the proposed selling price.

## Purchase costs

- Source: the latest eight distinct, submitted, non-return Purchase Invoices in the active POS company with positive stock quantity for this item, subject to native document and field permissions.
- Historical invoice `base_net_amount` already reflects its company-currency conversion and excludes tax. `stock_qty` already accounts for the original purchase-UOM conversion.
- Latest invoice unit cost = total matching positive-line base net amount / matching stock quantity within the newest qualifying invoice.
- Weighted average cost = sum of matching base net amounts / sum of matching stock quantities across the eight invoices. This is not an unweighted average of unit prices.
- Other items and non-positive quantities are excluded. Returns are excluded at invoice selection. Free-goods lines may contribute zero amount with positive quantity.
- This is purchase-invoice cost, not stock valuation or landed cost. Freight, recoverable tax and valuation adjustments are not added. No live FX lookup mixes current exchange rates with historical purchase amounts.
- If no cost is available, choose Manual and enter a positive cost per stock UOM. A zero selling price cannot be saved through this calculator.

## Profit field

The editable Profit / markup % adds a percentage of cost: `selling net price = unit cost × (1 + markup / 100)`. For cost 100 and markup 30%, the net selling price is 130. That is approximately 23.08% gross margin, not 30% margin or net business profit. Overheads and other expenses are not deducted. The effective gross margin shown uses the rounded selling price.

The default is Latest purchase. Choose Weighted average or Manual when that is the intended pricing basis. Target-UOM cost uses the Item's current conversion factor. The selling price saved by this calculator rounds half-up to the nearest whole currency unit. For currencies or products requiring fractional prices, use native Item Price until configurable calculator precision is added.

The server recalculates the preview after input changes. Client-provided selling prices are not accepted by the save API. Empty/negative/non-finite numeric inputs and invalid UOMs are rejected.

## Tax handling

- Tax-exclusive input rates: the calculator saves the net selling price; invoice taxes continue through native ERPNext rules.
- One ordinary included-in-price On Net Total percentage tax with no Item-specific tax templates: the calculator adds the configured tax to the markup target, rounds the stored price to a whole unit, and derives the effective net price from that rounded amount. Cost 100 + 30% markup with 15% included tax gives a stored price of 150 and an effective net price of 130.43.
- Compound or Item-specific inclusive tax: preview the net target, but saving is blocked. Use native Item Price and review the actual invoice tax calculation.
- A price list in another currency is shown separately but not overwritten from company-currency costs. Configure/review conversion in native ERPNext.

## Saving and permissions

Purchase Invoice read AND report permission and access to the stock-quantity/base-net-amount fields are required even for cost preview. Purchase prices are not exposed to other cashiers. Existing native profile, company, warehouse and Item access checks still apply.

Saving requires System Manager plus native Item Price create/write access and ABS Item Pricing Policy permissions. Save is an explicit action in the popup, not automatic on typing, opening the report or checkout.

The active POS Profile supplies the selling price list. Only an enabled, selling-only, matching-currency price list is eligible. The update targets a generic, active, exact-UOM Item Price, never a customer-, supplier- or batch-specific price. Ambiguous active variants, an unresolved blank-UOM generic price or a future-only scheduled price stop saving and point to the native Item Price form. Existing valid dates are retained when updating; a new entry starts today.

The price list can be shared across companies/counters: the interface states that the change affects future sales using that list. Use separate price lists when businesses need independent prices. Pricing rules and customer-specific prices may override this generic rate.

A reviewed snapshot guards against changed purchase costs, prices, tax setup, UOM conversion, policy or active profile. Save rechecks the context under database locks and uses native Item Price validation. Price and policy writes belong to one request transaction. Stock documents, existing invoices and current carts are not rewritten. Matching item cards are refreshed; review cart prices before paying.

Markup %, cost basis and manual stock-UOM cost are saved per company/item/price list/UOM in **ABS Item Pricing Policy**, with native change tracking and a link to the saved Item Price. Only System Managers have policy access by default. No new permissions on purchase or sales documents are granted.

## Validation and deployment

A local backup precedes the app-scoped new DocType sync. No full-site migration is required for this local delivery; the unrelated Analytics Studio migration issue is not bypassed. Future normal app installation/migration syncs this DocType as usual.

46 combined backend tests cover checkout/history plus markup, effective margin, inclusive tax, Decimal rounding, quantity weighting, mixed line quantities, permission/field denial, company/status/return filters, and stale-save/native-write contracts. In addition, native Item Price and pricing-policy creation was validated against a temporary unused price list and the transaction was rolled back, so no customer selling price was changed. Local populated purchase data and read-only calculator HTTP previews are checked separately. Production build passes with no new TypeScript diagnostics against the inherited baseline.

Browser access is unavailable in the current session. Real modal interaction, saving via the browser and a subsequent invoice preview/receipt are acceptance checks before customer rollout. Native save validation paths are implemented, but an actual operational price change has deliberately not been executed during development.
