# RBI notification watcher

`regintel.watch.rbi_watcher` makes one monitoring pass per run. Schedule it with
cron, Windows Task Scheduler, or a Kubernetes CronJob, or use
`--interval-minutes N` for a simple loop.

```
poll https://www.rbi.org.in/notifications_rss.xml
  -> skip notification ids already in data/processed/watch/state.json
  -> classify: tracked_amendment | title_match | untracked
  -> applicability hint from the entity profile (title keywords only)
  -> tracked: fetch the consolidated direction PDF, compare clauses with the
     preserved baseline, shortlist possibly affected synthetic policy sections
  -> append data/processed/watch/events.jsonl; write impact_<page>_<sha>.json
```

**Tracked instruments** are keyed by the Master Direction page ID that each
notification links (`BS_ViewMasDirections.aspx?id=N`). IDs come from the
preserved corpora: 13139 outsourcing, 13155 cards, 13642 digital payment
security, 13643 cybersecurity. KYC notifications are matched by title.

**Applicability hints** read entity types from the title. "Commercial Banks"
gives `likely_applicable`; only excluded entity types (payments bank, small
finance bank, AIFI, and so on) give `likely_not_applicable`; everything else
gives `needs_review`. These are triage hints, not applicability decisions.

**Safeguards**

- Only official RBI hosts are fetched, with each redirect checked and bounded
  downloads (`foundation.expansion.fetch`).
- The direction PDF must be the page's only link under
  `/rdocs/notification/PDFs/`. Site-wide content PDFs are ignored and
  ambiguity is an error.
- A response that is not a PDF, or a PDF with no extractable clauses, is never
  treated as a new version. The notification stays unseen and is retried on the
  next run.
- Downloaded PDFs are stored once under `data/raw/watch/rbi/<sha256>.pdf`.

**Source protection (October 11, 2026).** `rbidocs.rbi.org.in` currently
answers automated PDF requests with a bot-protection JavaScript challenge. The
watcher reports `source_blocked_or_not_pdf` and does not try to bypass it. An
officer can download the PDF in a browser and run the same analysis:

```powershell
uv run python -m regintel.watch.rbi_watcher --direction-pdf 13643=C:\path\to\direction.pdf
```

The RSS feed itself is reachable. The first live pass recorded 10
notifications: none amended a tracked instrument, 4 named commercial banks,
3 named only excluded entity types, and 3 need review.

Comparison and impact use the existing `changes.compare` and BM25
`changes.impact` modules. Results are review candidates: a textual change is
not a confirmed amendment, and a lexical policy match is not a confirmed
affected control.
