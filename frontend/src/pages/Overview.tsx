import { Link } from "react-router-dom";
import { BarPanel } from "../components/BarPanel";
import { LoadState, PageHead, Panel, StatusPill, Tile, date, pct } from "../components/ui";
import { useApi } from "../hooks";
import type { GapReportListItem } from "../types";

interface Summary {
  evidence: { available: boolean; silent_errors?: number; records?: { total: number; ocr: number };
    extraction?: { ocr_overall: { field_accuracy: number }; ocr_by_file: Record<string, number> };
    decisions?: Record<string, number>; defect_detection_accepted_only?: { precision: number; recall: number } };
  retrieval: { available: boolean; methods?: Record<string, Record<string, number>>; annotation_source?: string };
  gates: { available: boolean } & Record<string, unknown>;
}

interface WatchEvent { event_id: string; title: string; published: string | null;
  classification: { kind: string }; applicability: { hint: string } }

const METHODS = [
  { key: "bm25", label: "BM25", color: "var(--series-1)" },
  { key: "vector", label: "Vector", color: "var(--series-2)" },
  { key: "hybrid", label: "Hybrid", color: "var(--series-3)" },
];

export function Overview() {
  const summary = useApi<Summary>("/insights/summary");
  const reports = useApi<{ items: GapReportListItem[]; total: number }>("/gap-reports?limit=100");
  const events = useApi<{ items: WatchEvent[]; total: number; available: boolean }>("/insights/watch-events?limit=6");

  const s = summary.data;
  const pending = reports.data?.items.filter((r) => r.review_status === "pending_review").length;
  const retrieval = s?.retrieval.methods;
  const retrievalData = retrieval
    ? (["precision@5", "precision@10", "mrr@10"] as const).map((metric) => ({
        metric: metric.replace("@", " @"),
        ...Object.fromEntries(METHODS.map((m) => [m.key, retrieval[m.key][metric]])),
      }))
    : [];
  const ocrData = s?.evidence.extraction
    ? Object.entries(s.evidence.extraction.ocr_by_file).map(([file, value]) => ({
        file: file.replace("access-reviews-", "").replace(/\.(pdf|png|jpg)$/, (m) => ` ${m.slice(1).toUpperCase()}`),
        accuracy: value,
      }))
    : [];

  return (
    <>
      <PageHead title="Overview" sub="Assessment workload, measured reliability, and the latest regulatory activity." />
      <div className="grid tiles">
        <Tile label="Gap reports" value={reports.data?.total ?? "–"} note="stored assessments" />
        <Tile label="Awaiting officer review" value={pending ?? "–"} note="pending approval or rejection" />
        <Tile label="Silent evidence errors" value={s?.evidence.available ? s.evidence.silent_errors : "–"}
          note={s?.evidence.available ? `${s.evidence.records?.total} synthetic records` : "results unavailable"} />
        <Tile label="OCR field accuracy" value={s?.evidence.extraction ? pct(s.evidence.extraction.ocr_overall.field_accuracy) : "–"}
          note="live OCR, uncorroborated values go to a person" />
        <Tile label="Hybrid retrieval P@5" value={retrieval ? pct(retrieval.hybrid["precision@5"], 0) : "–"} note="AI-labelled, team-approved" />
        <Tile label="RBI notifications seen" value={events.data?.available ? events.data.total : "–"} note="watcher event log" />
      </div>
      <LoadState loading={summary.loading} error={summary.error} />

      <div className="grid two">
        {retrievalData.length > 0 && (
          <BarPanel title="Retrieval quality by method" data={retrievalData} category="metric" series={METHODS}
            format={(v) => v.toFixed(2)} caption="Six queries over 500 RBI passages. Relevance labels are AI-generated and team-approved." />
        )}
        {ocrData.length > 0 && (
          <BarPanel title="OCR field accuracy by evidence file" data={ocrData} category="file"
            series={[{ key: "accuracy", label: "Field accuracy", color: "var(--series-1)" }]} format={(v) => pct(v, 0)}
            caption="72 OCR'd records across six seeds. Every misread disagreed with the register and was routed to a person." />
        )}
      </div>

      <div className="grid two">
        <Panel title="Latest gap reports" actions={<Link to="/reports">All reports</Link>}>
          <LoadState loading={reports.loading} error={reports.error} empty={reports.data?.items.length === 0} />
          {reports.data && reports.data.items.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Reference</th><th>Assessment</th><th>Review</th></tr></thead>
                <tbody>
                  {reports.data.items.slice(0, 6).map((r) => (
                    <tr key={r.report_id}>
                      <td><Link to={`/reports/${encodeURIComponent(r.report_id)}`}>{r.regulatory_reference}</Link></td>
                      <td><StatusPill value={r.assessment_status} /></td>
                      <td><StatusPill value={r.review_status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
        <Panel title="Latest RBI notifications" actions={<Link to="/monitor">Monitor</Link>}>
          <LoadState loading={events.loading} error={events.error} empty={events.data?.items.length === 0} />
          {events.data && events.data.items.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Notification</th><th>Applicability</th></tr></thead>
                <tbody>
                  {events.data.items.map((e) => (
                    <tr key={e.event_id}>
                      <td>{e.title}<div className="muted" style={{ fontSize: ".78rem" }}>{date(e.published)} · {e.classification.kind.replace(/_/g, " ")}</div></td>
                      <td><StatusPill value={e.applicability.hint} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
