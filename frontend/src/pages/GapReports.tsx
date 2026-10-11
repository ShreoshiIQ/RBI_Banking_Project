import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LoadState, PageHead, Panel, StatusPill, date } from "../components/ui";
import { useApi } from "../hooks";
import type { GapReportListItem } from "../types";

const FILTERS = ["all", "pending_review", "approved", "rejected"] as const;

export function GapReports() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const { data, loading, error } = useApi<{ items: GapReportListItem[]; total: number }>("/gap-reports?limit=100");
  const items = data?.items.filter((r) => filter === "all" || r.review_status === filter) ?? [];

  return (
    <>
      <PageHead title="Gap reports" sub="Verified assessments of regulatory obligations against bank policy. Open a report to see citations, the remediation plan, and review history." />
      <Panel
        actions={
          <label className="row" style={{ gap: 6 }}>
            <span className="muted">Review status</span>
            <select id="report-filter" value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)}>
              {FILTERS.map((f) => <option key={f} value={f}>{f.replace(/_/g, " ")}</option>)}
            </select>
          </label>
        }
      >
        <LoadState loading={loading} error={error} empty={!loading && items.length === 0} />
        {items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Reference</th><th>Assessment</th><th>Review</th><th>Created</th><th>Report ID</th></tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.report_id} className="clickable" tabIndex={0}
                    onClick={() => navigate(`/reports/${encodeURIComponent(r.report_id)}`)}
                    onKeyDown={(e) => e.key === "Enter" && navigate(`/reports/${encodeURIComponent(r.report_id)}`)}>
                    <td>{r.regulatory_reference}</td>
                    <td><StatusPill value={r.assessment_status} /></td>
                    <td><StatusPill value={r.review_status} /></td>
                    <td className="num">{date(r.created_at)}</td>
                    <td className="mono muted">{r.report_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}
