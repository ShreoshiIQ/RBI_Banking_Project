# Regulatory expansion source queue

Historical discovery notes follow. For the subsequent Phase 3 ingestion and
separate SEBI corpus, see [Phase 3 expansion](phase3_expansion.md). As of that
receipt the application DB contains 1,150 pending RBI candidates across five
source versions; SEBI remains offline. Earlier statements about unpersisted
previews and provisional scope describe the earlier discovery stage.

Five official source-page candidates are recorded in
`data/metadata/rbi_expansion_candidates.json`, separately from the ingested
PDF manifest. Source discovery does not establish that the instruments are
currently applicable to a particular institution or unaffected by later rules.

| Candidate | Official page | Scope checkpoint |
| --- | --- | --- |
| IT governance | [RBI](https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12562) | Paragraph 2 entity classes and exclusions |
| IT outsourcing | [RBI](https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12486) | Entity scope, service exclusions, transition periods |
| Digital payment security | [RBI](https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12032) | Listed bank categories and card-issuing NBFCs |
| Card issuance and conduct | [RBI](https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12300) | Separate credit-card and debit-card scopes |
| Prepaid payment instruments | [RBI](https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12156) | Issuer type and instrument-specific rules |

The source pages were inspected on October 11, 2026. Dates in the queue are
observed source metadata, not inferred latest-version guarantees. A null
update date means no date was recorded, not that amendments do not exist.

The PPI page displays an update dated September 30, 2026. This makes it a useful
version-provenance case, but comparing amendments requires independently
preserved old and new source versions. Do not simulate an older version by
removing text from the current document.

Before extraction, resolve the official PDF link from each page, preserve raw
bytes with SHA-256, record resolved URL/retrieval time and amendment dates,
confirm title/content, and check applicability for the chosen institution.
Keep older source versions. Reuse the existing RBI downloader's PDF checks;
these HTML source-page URLs must not be passed directly to its PDF-only function.

All five PDFs were downloaded on October 11, 2026 from RBI's official
`rbidocs.rbi.org.in` host. SHA-256 values and extracted page counts were verified:
IT governance 26 pages, IT outsourcing 31, digital payment security 22,
card conduct 35, and PPIs 40. The existing KYC document was preserved.
The ingestion manifest now contains six documents. New documents remain
pending applicability review and obligation extraction.

Re-run downloads from the project root with:

```powershell
uv run python scripts/download_expansion.py
```

No validated requirements, synthetic policies, or evaluation scores are
claimed by these downloads.

## Withdrawal markers found during extraction preparation

Four downloaded PDFs have a standalone `Withdrawn` watermark on every page:
IT governance, IT outsourcing, digital payment security, and card conduct.
They are preserved as historical sources, and current-obligation extraction
is blocked. The earlier download integrity checks did not verify source status.
PPI has no standalone withdrawal marker; ordinary references to withdrawal
inside its provisions are not treated as document watermarks. Absence of a
marker does not establish current applicability.

Source status checks are recorded in both manifests and the validation inventory.
Locate and verify entity-specific replacement instruments before expanding the
current obligation catalog. Do not strip the watermarks to treat these sources
as current. The extraction runner skips marked sources, and offline catalog
approval rejects them for a current reviewed catalog.

## Replacement discovery

Four commercial-bank replacement candidates were located in RBI's current
index and downloaded with their source-page snapshots and hashes:

- [Outsourcing, 2025](https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13139): 44 pages.
- [Card issuance and conduct, 2025](https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13155): 34 pages.
- [Digital payment security, 2026](https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13642): 32 pages.
- [Cybersecurity and technology risk, 2026](https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13643): 56 pages.

Provenance is in `data/metadata/rbi_replacement_candidates.json`. No standalone
withdrawal marker was found in these four PDFs. This does not prove legal
applicability. Commercial banks are a provisional discovery scope, not a
confirmed user institution profile. These mappings remain candidates pending
review of entity exclusions, commencement, repeal, saving, and amendment rules.
Other institution types require their own replacement mappings.

The ingestion manifest now has ten preserved sources, including the four
withdrawn historical documents. No new obligations have been approved or
persisted to PostgreSQL.

## File-only extraction previews

Run `uv run python -m regintel.ingestion.extract_expansion` from the project
root. This uses the existing clause and obligation extractors with support
for chapter headings containing dashes and titles. Existing preview files
are preserved rather than overwritten. KYC extraction artifacts and the
database are untouched.

The four replacement PDFs produced these unreviewed previews under
`data/processed/expansion_previews`:

| Source | Clause candidates | Obligation candidates |
| --- | ---: | ---: |
| Outsourcing | 98 | 159 |
| Card issuance and conduct | 97 | 227 |
| Digital payment security | 73 | 156 |
| Cybersecurity and technology risk | 233 | 296 |

Each preview includes the source clauses, candidate catalog, deferred passages,
and validation report. IDs are deterministic local preview IDs, explicitly
marked `local_preview_not_database`; they are not existing PostgreSQL foreign
keys. Do not feed previews into database persistence without reconciling
document/version/clause identities. All human review statuses remain pending.

The first three numbered sections are deferred as preliminary/applicability
text. Definitions elsewhere, repeal provisions, footnotes, compound statements,
and segmentation errors can still appear as candidates. These counts measure
output volume, not accuracy, completeness, applicability, or certification.

## Expansion review queues

Run `uv run python -m regintel.ingestion.triage_expansion` to create separate
triage reports and pending decision templates in `data/processed/expansion_reviews`.
Existing files are preserved on reruns. Use each triage JSON as the report input
to `regintel.ingestion.catalog_review` with its corresponding decisions file.

Source-clause heuristics route 60 of the 938 candidates as context: seven
definitions, 47 repeal/saving, and six applicability/scope candidates. The
remaining 878 are potential operational controls, not validated requirements.
Classification applies to the containing clause, so annex text or extraction
boundary errors can inherit that category. Review the included complete
section evidence against the PDF before recording a disposition. No automatic
approval, rejection, actor resolution, or database update occurs.

## Working demo scope and applicability packet

The working institution is a fictional domestic scheduled commercial bank
offering customer accounts, digital payments, credit/debit cards, and outsourced
IT services. It excludes small finance banks, payments banks, local area banks,
RRBs, NBFCs, and foreign-bank branch assumptions. This engineering scope is
recorded in `data/metadata/demo_institution_profile.json` and does not itself
establish legal applicability. PPI issuance is outside the initial demo scope.

Run `uv run python -m regintel.ingestion.applicability_packet` to regenerate
`data/processed/expansion_reviews/applicability_packet.json`. The packet contains
31 exact extracted passages across the four replacement sources, with clause
numbers, PDF page ranges, source URLs, and quote hashes. Commencement, scope,
exceptions, and repeal/saving clauses remain pending review. Verify the quotes
against the PDFs and assess each activity-specific requirement separately.
