import { LoadState, PageHead, Panel, StatusPill, date } from "../components/ui";
import { useApi } from "../hooks";

interface Impact { status: string; error?: string; summary?: Record<string, number>; changes_with_policy_candidates?: number }
interface WatchEvent {
  event_id: string; title: string; link: string; published: string | null; detected_at: string;
  classification: { kind: string; page_ids?: string[] };
  applicability: { hint: string; rule?: { rule: string } | null };
  impact?: Record<string, Impact>;
}
interface Determination { title: string; regulator: string; status: string; basis: { rule: string } }

export function Monitor() {
  const events = useApi<{ items: WatchEvent[]; total: number; available: boolean; reason?: string }>("/insights/watch-events?limit=50");
  const applicability = useApi<{ items: Determination[]; available: boolean; reason?: string }>("/insights/applicability");

  return (
    <>
      <PageHead title="Regulatory monitor"
        sub="RBI notifications picked up by the watcher, with applicability hints for the bank profile and impact analysis for tracked directions." />
      <Panel title="Notifications">
        <LoadState loading={events.loading} error={events.error} />
        {events.data && !events.data.available && <p className="empty">{events.data.reason}. Run the watcher to populate it.</p>}
        {events.data && events.data.items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Notification</th><th>Published</th><th>Classification</th><th>Applicability</th><th>Impact</th></tr></thead>
              <tbody>
                {events.data.items.map((e) => (
                  <tr key={e.event_id}>
                    <td><a href={e.link} target="_blank" rel="noreferrer">{e.title}</a></td>
                    <td className="num">{date(e.published)}</td>
                    <td>{e.classification.kind.replace(/_/g, " ")}</td>
                    <td><StatusPill value={e.applicability.hint} />
                      {e.applicability.rule && <div className="muted" style={{ fontSize: ".75rem" }}>{e.applicability.rule.rule.replace(/_/g, " ")}</div>}
                    </td>
                    <td>
                      {e.impact
                        ? Object.entries(e.impact).map(([page, v]) => (
                            <div key={page}><span className="mono">MD {page}</span> <StatusPill value={v.status === "error" ? "error" : v.status} />
                              {v.error && <div className="muted" style={{ fontSize: ".75rem" }}>{v.error.replace(/_/g, " ")}</div>}
                            </div>
                          ))
                        : <span className="muted">–</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="notice">Hints come from title keywords. RBI's PDF host may block automated downloads; blocked items are retried, and an officer can supply the PDF.</p>
      </Panel>

      <Panel title="Applicability of registered sources">
        <LoadState loading={applicability.loading} error={applicability.error} />
        {applicability.data && applicability.data.items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Source</th><th>Regulator</th><th>Status</th><th>Basis</th></tr></thead>
              <tbody>
                {applicability.data.items.map((d) => (
                  <tr key={d.title}>
                    <td>{d.title}</td>
                    <td>{d.regulator}</td>
                    <td><StatusPill value={d.status} /></td>
                    <td className="muted">{d.basis.rule.replace(/_/g, " ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="notice">Only an officer decision yields “applicable”. Gaps against presumed sources stay in the human review queue.</p>
      </Panel>
    </>
  );
}
