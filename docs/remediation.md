# Risk prioritisation and remediation drafts

The remediation supervisor (`regintel.agents.supervisor`) is a LangGraph workflow:

```
intake -> prioritise -> remediate -> route -> assemble
               \-- no gaps --------------------/
```

- **Intake** normalises unsupported findings from stored gap reports and failed
  deterministic control tests into gap items. Malformed inputs are listed under
  `rejected_inputs` instead of stopping the run.
- **Prioritise** scores each gap with the versioned
  [risk model](../src/regintel/prioritization/risk_model_v1.json): finding or
  control severity, obligation type, domain criticality, deadline proximity, and
  evidence uncertainty. Every score carries its factor contributions, the model
  version, and the model file's SHA-256. The weights are illustrative and need
  calibration and approval by the compliance function.
- **Remediate** drafts actions per gap. Templates are the default. With `--llm`,
  Gemini drafts are validated: schema, citations limited to the finding's own
  sections, a redline for policy updates, and escalation for potential conflicts.
  A rejected draft is retried with the validation errors (three attempts in all),
  then the template is used and the gap is flagged `llm_abstained`.
- **Route** places critical/high gaps, potential conflicts, and LLM abstentions in
  `human_queue`. Every draft stays `pending_review`.

Run against stored reports and control-test records:

```powershell
uv run python -m regintel.agents.supervisor --reports data/processed/reports/rbi_46f_gap_report.json --as-of 2026-10-11 --output data/processed/remediation/new_register.json
```

`--control-tests` takes JSON lists of `{test_id, reference, requirement, result}`,
where `result` is the output of `regintel.evidence.controls.test_access_reviews`.
Existing output files are never overwritten.

Authenticated users can fetch a template-only plan for a stored report with
`GET /api/v1/gap-reports/{report_id}/remediation-plan?as_of=YYYY-MM-DD`. The API
makes no model calls.

## Live hallucination check (October 11, 2026, gemini-3.1-flash-lite)

Run on the stored RBI KYC 46(f) report, compared by hand against the
section 46 source text.

- **Without regulation text** (the report stores `regulatory_text: null`), the
  drafts invented no numbers, but they added requirements 46(f) does not state
  ("secure", "centralized", "for a minimum period as prescribed"), labelled
  policy wording "Section 46(f):", and dropped "when requested by the competent
  authorities" from one redline. One draft put "RBI KYC Section 46(f)" into
  `cited_section_ids`; validation rejected it and the retry was accepted.
- **Fixes**: the prompt now carries the regulation text (`--regulatory-text`
  for reports stored without it), redlines are rejected if they introduce
  numbers or durations absent from the regulation and finding, or carry
  regulation section labels, and the citation error tells the model which IDs
  are allowed.
- **After the fixes**, all three redlines track 46(f) closely, including the
  competent-authority element. Two drafts were accepted after one rejection.
  Remaining minor drift: one redline adds "required by the bank", and one
  control description borrows "identification records and transaction data"
  from 46(c) while citing 46(f). Officer review remains required.

This is a three-item spot check, not a measured hallucination rate.

The supervisor does not approve reports, edit policies, or change review status.
Scores order review work; they are not regulatory risk ratings.
