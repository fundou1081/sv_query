# Reporting a query miss without leaking RTL

> **Audience**: external users reporting wrong/missing `sv_query` answers.
> **Rule**: never upload proprietary RTL. A useful report does not require the
> original design.

## 1. What counts as a miss?

- `verified` claim that is architecturally wrong;
- `contradicted`/`unknown` that should have been verifiable;
- `drivers` / `loads` / `paths` returning the wrong node or no path;
- evidence pointing at the wrong source line;
- JSON envelope violating the documented contract.

Check [KNOWN_LIMITATIONS_EN](KNOWN_LIMITATIONS_EN.md) first; a documented limit
is not a miss.

## 2. Minimum safe report

Open a **Miss report** issue with:

1. exact `sv_query` version;
2. exact command and flags (paths removed);
3. expected conclusion;
4. actual `ok`, `rc`, `error_code`, and relevant JSON fields;
5. a minimal fixture if you can safely share one.

Do not include:

```text
proprietary module/signal names
customer/company names
absolute local paths
parameters or constants that reveal the design
credentials / tokens
```

## 3. Build a structure-preserving fixture

Start from the failing query and reduce manually:

1. Create fresh small modules; do not copy the original file wholesale.
2. Rename identifiers consistently (`top`, `u0`, `sig_a`, ...).
3. Preserve the structure that causes the bug:
   - hierarchy and instance boundaries;
   - signal widths and directions;
   - `assign` / `always_comb` / `always_ff` shape;
   - `if` / `case` / `generate` structure that matters;
   - bit selects and cross-module connections.
4. Remove unrelated logic, comments, parameters, and vendor primitives.
5. Re-run the query; the reduced fixture must reproduce the same wrong output.
6. Run the public scan below before attaching.

The fixture should be small enough to read in one screen or two, and must not
contain text from the original design beyond the minimum structure.

## 4. Local scan before sharing

From the repository root:

```bash
git grep -nE '/Users/|/home/|[A-Za-z]:\\Users\\|@[A-Za-z0-9.-]+' -- <fixture>
```

The miss-report template forbids absolute paths. Also manually check for customer
names and credentials.

## 5. Structural-only report

If the fixture cannot be shared even after renaming, submit only:

```text
module hierarchy shape
signal directions/widths
always/assign/operator pattern
query command shape
expected vs actual JSON
```

This is less precise but still actionable; it does not require source text.

## 6. What maintainers will do

1. reproduce against a clean checkout;
2. classify: known limitation / core bug / exp behavior;
3. ask for a narrower fixture if needed;
4. if safe and contributed under MIT OR Apache-2.0, add it as a regression
   fixture;
5. link the issue to the relevant claim/known-limitation update.

## 7. Privacy checklist

- [ ] no proprietary RTL
- [ ] no customer/company names
- [ ] no absolute local paths
- [ ] no credentials/tokens
- [ ] fixture is renamed and reduced
- [ ] fixture license is acceptable (MIT OR Apache-2.0)
