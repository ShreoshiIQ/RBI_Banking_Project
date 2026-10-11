import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { LoadState, PageHead, Panel, StatusPill, Tile, date } from "../components/ui";
import { useApi } from "../hooks";
import type { GapReportDetail as Detail, RemediationRegister, ReviewEvent } from "../types";

type Tab = "findings" | "remediation" | "history";

export function GapReportDetail() {
  const { reportId = "" } = useParams();
  const id = encodeURIComponent(reportId);
  const [tab, setTab] = useState<Tab>("findings");
  const report = useApi<Detail>(`/gap-reports/${id}`);
  const plan = useApi<RemediationRegister>(tab === "remediation" ? `/gap-reports/${id}/remediation-plan` : null);
  const history = useApi<{ reviews: ReviewEvent[] }>(`/gap-reports/${id}/reviews`);

  const r = report.data;
  return (
    <>
      <PageHead
        title={r?.regulatory_reference ?? "Gap report"}
        sub={r ? `Report ${r.report_id}` : undefined}
        actions={<Link to="/reports">Back to reports</Link>}
      />
      <LoadState loading={report.loading} error={report.error} />
      {r && (
        <>
          <div className="grid tiles">
            <Tile label="Assessment" value={<StatusPill value={r.assessment_status} />} />
            <Tile label="Review" value={<StatusPill value={r.review_status} />} />
            <Tile label="Requirements" value={r.report.summary.total} />
            <Tile label="Missing" value={r.report.summary.missing} note={`${r.report.summary.partial} partial · ${r.report.summary.supported} supported`} />
          </div>
          <div className="tabs" role="tablist">
            {(["findings", "remediation", "history"] as Tab[]).map((t) => (
              <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
                {t === "findings" ? "Findings" : t === "remediation" ? "Remediation plan" : "Review history"}
              </button>
            ))}
          </div>

          {tab === "findings" && (
            <Panel>
              <p>{r.report.overall_explanation}</p>
              {r.report.findings.map((f, i) => (
                <div className="finding" key={i}>
                  <div className="row"><StatusPill value={f.status} /><strong>{f.requirement}</strong></div>
                  <span>{f.explanation}</span>
                  {f.evidence.map((e) => (
                    <div className="quote" key={e.section_id + e.quote}>
                      “{e.quote}”
                      <div className="muted" style={{ fontSize: ".78rem" }}>Policy section {e.section_number} · {e.section_title}</div>
                    </div>
                  ))}
                  <span className="muted">Suggested action: {f.suggested_action}</span>
                </div>
              ))}
              <p className="notice">Evidence for human review, not a legal compliance certification.</p>
            </Panel>
          )}

          {tab === "remediation" && (
            <Panel>
              <LoadState loading={plan.loading} error={plan.error} empty={plan.data?.items.length === 0} />
              {plan.data && plan.data.items.length > 0 && (
                <>
                  <div className="table-wrap">
                    <table>
                      <thead><tr><th>Gap</th><th>Risk</th><th>Applicability</th><th>Target</th><th>Actions</th></tr></thead>
                      <tbody>
                        {plan.data.items.map((item) => (
                          <tr key={item.gap_id}>
                            <td>{item.requirement}<div><StatusPill value={item.status} /></div></td>
                            <td className="num">
                              {item.risk.score.toFixed(1)} <StatusPill value={item.risk.band} />
                              <div className="muted" style={{ fontSize: ".75rem" }}>{item.risk.domain}</div>
                            </td>
                            <td><StatusPill value={item.applicability.status} /></td>
                            <td className="num">{item.risk.target_days} days</td>
                            <td>
                              <ul style={{ margin: 0, paddingLeft: 18 }}>
                                {item.remediation.actions.map((a, i) => (
                                  <li key={i}>{a.description} <span className="muted">({a.owner_role.replace(/_/g, " ")})</span></li>
                                ))}
                              </ul>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="notice">
                    Risk model {plan.data.risk_model.version}; {plan.data.human_queue.length} of {plan.data.items.length} gaps queued for an officer.
                    Template drafts only on this page; scores order review work and are not regulatory risk ratings.
                  </p>
                </>
              )}
            </Panel>
          )}

          {tab === "history" && (
            <Panel>
              <LoadState loading={history.loading} error={history.error} empty={history.data?.reviews.length === 0} />
              {history.data && history.data.reviews.length > 0 && (
                <table>
                  <thead><tr><th>When</th><th>Reviewer</th><th>Change</th><th>Comment</th></tr></thead>
                  <tbody>
                    {history.data.reviews.map((h) => (
                      <tr key={h.id}>
                        <td className="num">{date(h.reviewed_at)}</td>
                        <td className="mono">{h.reviewer_id}</td>
                        <td><StatusPill value={h.previous_status} /> → <StatusPill value={h.new_status} /></td>
                        <td>{h.comment}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Panel>
          )}

          <ReviewBox reportId={id} status={r.review_status} onDone={() => { report.reload(); history.reload(); }} />
        </>
      )}
    </>
  );
}

function ReviewBox({ reportId, status, onDone }: { reportId: string; status: string; onDone: () => void }) {
  const { user } = useAuth();
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<"approved" | "rejected" | null>(null);

  if (user?.role !== "compliance_officer") {
    return <p className="notice">Only compliance officers can approve or reject reports.</p>;
  }
  if (status !== "pending_review") {
    return <p className="notice">This report has already been {status.replace(/_/g, " ")}.</p>;
  }

  const submit = async (decision: "approved" | "rejected") => {
    setBusy(true);
    setMessage(null);
    try {
      await api.post(`/gap-reports/${reportId}/review`, { decision, comment: comment.trim() });
      setMessage(decision === "approved" ? "Report approved." : "Report rejected.");
      setComment("");
      onDone();
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setBusy(false);
      setConfirming(null);
    }
  };

  return (
    <Panel title="Officer decision">
      <label className="field">
        Comment (required, recorded in the audit history)
        <textarea id="review-comment" value={comment} onChange={(e) => setComment(e.target.value)} maxLength={2000} />
      </label>
      <div className="row" style={{ marginTop: 10 }}>
        {confirming ? (
          <>
            <span>{confirming === "approved" ? "Approve" : "Reject"} this report? This cannot be undone.</span>
            <button className="btn primary" disabled={busy} onClick={() => submit(confirming)}>Confirm</button>
            <button className="btn" disabled={busy} onClick={() => setConfirming(null)}>Cancel</button>
          </>
        ) : (
          <>
            <button className="btn primary" disabled={!comment.trim()} onClick={() => setConfirming("approved")}>Approve</button>
            <button className="btn danger" disabled={!comment.trim()} onClick={() => setConfirming("rejected")}>Reject</button>
          </>
        )}
      </div>
      {message && <p role="status">{message}</p>}
    </Panel>
  );
}
