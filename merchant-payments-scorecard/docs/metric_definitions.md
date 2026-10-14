# Metric definitions and business rules

Every report in this project uses these definitions. The logic lives in one place, [`sql/02_clean_tables.sql`](../sql/02_clean_tables.sql), so a metric can't mean one thing in Excel and another on the dashboard.

## Data sources

| Table | Grain | Key fields |
|---|---|---|
| `merchants` | One row per merchant application | sales channel, industry, province, product, pricing plan, application / decision / first-transaction / closed dates |
| `monthly_volume` | One row per merchant × month × card type | attempted and approved transactions, approved volume, refunds, chargebacks |
| `support_tickets` | One row per support ticket | category, contact channel, opened and resolved time, CSAT score |

All data is **simulated** (see [`python/generate_data.py`](../python/generate_data.py)).

## Volume and revenue

| Metric | Definition |
|---|---|
| **Active merchant** | A merchant with at least one approved transaction in the month. |
| **Approved volume** | Dollar value of approved card transactions, before refunds. |
| **Approval rate** | Approved transactions ÷ attempted transactions. |
| **Average ticket** | Approved volume ÷ approved transactions. |
| **Net revenue** | Processing revenue + platform fees (below). |
| **Processing revenue** | Approved volume × the margin kept for that pricing plan and card type. |
| **Platform fee** | Monthly fee for each active merchant: $25 countertop terminal, $15 mobile POS, $20 online gateway. |
| **Revenue per active merchant** | Net revenue ÷ active merchants in the month. |

**Margin assumptions** (share of approved volume kept after interchange and network fees):

| Card type | Flat Rate plan | Interchange Plus plan |
|---|---|---|
| Visa / Mastercard | 0.85% | 0.30% |
| Interac Debit | 0.40% | 0.15% |
| Amex | 0.25% | 0.25% |

## Risk

| Metric | Definition |
|---|---|
| **Chargeback rate** | Chargebacks ÷ approved credit-card transactions. Interac Debit is excluded because debit has no chargebacks. |

## Onboarding and retention

| Metric | Definition |
|---|---|
| **Application approval rate** | Approved applications ÷ all applications. |
| **Days to decision** | Days from application to approve/decline decision. |
| **Activated within 30 days** | Approved merchants whose first transaction came within 30 days of approval. Only merchants approved at least 30 days before the end of the data are counted, so recent approvals aren't unfairly marked as "not activated". |
| **Days to first transaction** | Days from approval to first transaction (median reported). |
| **Retained 6 months** | Activated merchants whose account was still open 6 months (183 days) after their first transaction. Only merchants activated by December 2025 are counted, so each one has had 6 months to be measured. |
| **New merchants** | Merchants whose first transaction falls in the month. |
| **Closed merchants** | Merchants whose account closed in the month. |

## Service

| Metric | Definition |
|---|---|
| **Resolution hours** | Hours from ticket opened to ticket resolved. |
| **Within 48h SLA** | Share of resolved tickets closed within 48 hours. |
| **CSAT** | Average score (1–5) from merchants who answered the post-ticket survey (about 40% respond). |
| **Slow ticket** | A ticket that took more than 48 hours to resolve. |
| **Closed within 3 months** | For each merchant-month, whether the account closed in that month or the next 3. Only months up to March 2026 are used so every row has a full 3 months of follow-up. |

## Data-quality rules

Checked by [`sql/01_data_quality.sql`](../sql/01_data_quality.sql) on every refresh.

| Issue | Rule |
|---|---|
| Duplicate merchant records | Keep the most complete copy (one with a province). |
| Missing province | Reported as "Unknown". |
| Non-standard industry labels (e.g. "Restaurant", "e-commerce ") | Mapped to the approved label. |
| Duplicate monthly volume rows | Keep one copy. |
| Ticket resolved before it was opened | Flagged "Invalid timestamp" and left out of all service metrics. |
| Approved > attempted transactions, negative volume, refunds > volume, unknown merchant, CSAT outside 1–5 | Checked every month; none found in this data. |
