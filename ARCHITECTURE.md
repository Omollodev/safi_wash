# Architecture

## The one idea: separate *what the data is*, *what happens*, and *how we show it*

Each app follows the same small set of files. Learn the pattern once, understand every app.

| File | Responsibility | Rule |
|------|----------------|------|
| `models.py` | Fields + tiny derived properties | No workflows, no emails, no HTTP |
| `services.py` | **Writes** — "create a job", "record a payment" | Enforce business rules; raise `JobError` / `PaymentError` |
| `selectors.py` | **Reads** — filtered/annotated queries | Never change data |
| `forms.py` | Validate user input | Never decide business rules |
| `views.py` | HTTP glue | permission → form → service → message → redirect |
| `tests/` | Executable documentation | Test services directly; test views for permissions |

```
Browser ──> urls.py ──> view ──> form (validate) ──> service (rules + DB writes) ──> models
                          └──────> selector (reads) ──> template
```

## Dependency direction (no cycles)

```
core  <-  accounts  <-  customers  <-  catalog / workforce  <-  jobs  <-  payments
                                                   notifications <- (used by jobs, payments)
portal, dashboard sit on top and may use everything.
```
`payments` knows about `jobs`; `jobs` never imports `payments` (a job reads its money through the `payments` reverse relation). This is what keeps the project easy to change.

## Key design decisions (and why they improve on the first version)

1. **Money is a ledger.** `Payment` rows (negative = refund). A job's `amount_paid` and `payment_status` are *calculated*, so they can never disagree with the payments.
2. **Timeline is a table** (`JobEvent`), not a JSON blob — queryable, append-only.
3. **Price snapshot.** `JobService.price` copies the catalogue price when added; later price edits don't rewrite history.
4. **Workflow lives in one dict** (`Job.ALLOWED_TRANSITIONS`) and one function (`services.change_status`).
5. **Derived, not stored.** Customer visits/total spent and worker "current job" are computed, removing sync bugs.
6. **Business errors are exceptions**, not `True/False`, so the user sees *why* something failed.
7. **One security policy file** (`apps/core/permissions.py`) and customer-facing queries always start from the logged-in customer.
8. **Config from environment**; split `base/dev/prod` settings; prod fails fast without a secret key.
9. **M-Pesa behind a gateway interface** (`FakeGateway` / `DarajaGateway`); callbacks are token-protected, idempotent, amount-checked and receipt-unique.

## Job workflow

```
waiting ──> in_progress ──> completed
   │          │   ▲
   │          ▼   │
   │     awaiting_extra ──> completed
   └──> cancelled <── (from waiting or in_progress)
```
A job can only complete when **every** service line is ticked done. Adding an extra service to a running job moves it to `awaiting_extra` and raises an alert until the extras are done.

## Adding a feature (worked example: "tips")

1. Add a field/model in `payments/models.py` → `makemigrations`.
2. Add `record_tip()` in `payments/services.py` with the rules.
3. Add a form + thin view + URL.
4. Write the test in `payments/tests/` first or alongside.
