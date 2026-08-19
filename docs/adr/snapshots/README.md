# ADR snapshots — frozen renderings, never the source

Rendered HTML copies of ADRs, each **frozen at the date in its filename**. The markdown in
`docs/adr/` is always authoritative.

## The rule

**A snapshot is never updated.** If the ADR changes, the snapshot is now a record of what the
decision said on that date — which is the only thing it is honestly able to be. Re-render under a
new date if a fresh copy is wanted; do not edit an existing one.

The date lives in the filename rather than in a header, so a snapshot cannot be mistaken for
current by anyone who only sees the file listing.

## Why these exist at all

A rendered ADR is easier to read and to hand to someone than the raw markdown, and this repo
publishes some of them as private artifacts. That rendering otherwise lives only in a session
scratchpad, which is cleared — after which the published page is live and unmaintainable, and the
rendering is unreproducible. Committing it fixes both.

## Why frozen, and not a live twin

**A static HTML copy of a markdown record is a doc-drift generator with nothing checking it.**
When ADR-0029 was written, three copies of that one decision existed — the markdown, a row on the
promo timeline, and a published artifact — and **all three disagreed with each other inside a
single day**, in both directions: at one point the off-repo artifact carried the correct probe
count while the source markdown carried a wrong one.

Three options were weighed (see `_project_specs/todos/active.md` item 12):

1. **A dated snapshot** — cheap, honest, and it stops pretending to track. **Chosen.**
2. **Live, plus a doccheck assertion** tying it to the ADR — the only option that stays true, and
   the check is genuinely hard to write over prose.
3. **Generate it from the markdown** at publish time, so there is one source — most correct, most
   work, and nothing else in this repo needs it yet.

If a page starts being re-published repeatedly, option 3 is the one to build; option 1 stops
being adequate the moment the snapshot count grows faster than anyone re-reads them.

## Note on the file format

The published artifact is served inside a wrapper that supplies `<!doctype>`, `<head>` and a CSS
reset. A file here is a **complete standalone document**, so it opens correctly from disk — the two
are therefore not byte-identical by design, and diffing them will show that wrapper.
