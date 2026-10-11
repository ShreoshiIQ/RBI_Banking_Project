import { useState, type FormEvent } from "react";
import { api } from "../api";
import { LoadState, PageHead, Panel, StatusPill, Tile } from "../components/ui";
import { useApi } from "../hooks";

interface Member { provision_id: string; regulator: string; document_title: string; ref: string; text: string }
interface Family { family_id: string; label_terms: string[]; regulators: string[]; cross_regulator: boolean; members: Member[] }
interface Candidate {
  type: string; severity: string; similarity: number; status: string; explanation: string;
  values?: Record<string, string>; provisions: Member[];
  judgement?: { agreed: boolean; votes: { relation: string; reason: string }[] };
}
interface Report {
  available: boolean; reason?: string;
  summary?: { families: number; cross_regulator_families: number; contradiction_candidates: Record<string, number> };
  corpus?: { provisions: number; documents: number };
  families: Family[]; contradiction_candidates: Candidate[];
}
interface Finding { type: string; severity: string; explanation: string }

const SAMPLE_A = "The bank shall report cyber incidents to the RBI within six hours of detection.";
const SAMPLE_B = "Regulated entities shall report cyber incidents within 24 hours of detection.";

export function CrossRegulation() {
  const report = useApi<Report>("/insights/cross-regulation?families=40");
  const [open, setOpen] = useState<string | null>(null);
  const r = report.data;
  const candidates = r?.summary ? Object.values(r.summary.contradiction_candidates).reduce((a, b) => a + b, 0) : 0;

  return (
    <>
      <PageHead title="Cross-regulation"
        sub="Obligation families link related provisions across documents so one control can be tested once against several regulators. Contradiction candidates go to legal review." />
      <LoadState loading={report.loading} error={report.error} />
      {r && !r.available && <p className="empty">{r.reason}. Run the cross-regulation analysis to populate it.</p>}
      {r?.summary && (
        <div className="grid tiles">
          <Tile label="Provisions analysed" value={r.corpus?.provisions} note={`${r.corpus?.documents} documents`} />
          <Tile label="Obligation families" value={r.summary.families} />
          <Tile label="RBI + SEBI families" value={r.summary.cross_regulator_families} />
          <Tile label="Contradiction candidates" value={candidates} note="pending legal review" />
        </div>
      )}

      {r && r.contradiction_candidates.length > 0 && (
        <Panel title="Contradiction candidates">
          {r.contradiction_candidates.map((c, i) => (
            <div className="finding" key={i}>
              <div className="row"><StatusPill value={c.severity} /><strong>{c.type.replace(/_/g, " ")}</strong>
                <span className="muted">similarity {c.similarity.toFixed(2)}</span><StatusPill value={c.status} /></div>
              <span>{c.explanation}</span>
              {c.provisions.map((p) => (
                <div className="quote" key={p.provision_id}>
                  {p.text.length > 420 ? `${p.text.slice(0, 420)}…` : p.text}
                  <div className="muted" style={{ fontSize: ".78rem" }}>{p.regulator} · {p.ref} · {p.document_title}</div>
                </div>
              ))}
              {c.judgement && (
                <span className="muted">Judge: {c.judgement.votes.map((v) => v.relation.replace(/_/g, " ")).join(" / ")} — {c.judgement.agreed ? "both votes agree" : "votes do not confirm a conflict"}</span>
              )}
            </div>
          ))}
        </Panel>
      )}

      {r && r.families.length > 0 && (
        <Panel title="Obligation families">
          <div className="table-wrap">
            <table>
              <thead><tr><th>Family</th><th>Regulators</th><th>Members</th><th /></tr></thead>
              <tbody>
                {r.families.map((f) => (
                  <FamilyRow key={f.family_id} family={f} open={open === f.family_id}
                    toggle={() => setOpen(open === f.family_id ? null : f.family_id)} />
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      <CompareTool />
    </>
  );
}

function FamilyRow({ family, open, toggle }: { family: Family; open: boolean; toggle: () => void }) {
  return (
    <>
      <tr>
        <td>{family.label_terms.join(", ") || family.family_id}</td>
        <td>{family.regulators.join(" + ")}{family.cross_regulator && <> <StatusPill value="cross-regulator" /></>}</td>
        <td className="num">{family.members.length}</td>
        <td><button className="btn" onClick={toggle} aria-expanded={open}>{open ? "Hide" : "Show"}</button></td>
      </tr>
      {open && (
        <tr>
          <td colSpan={4}>
            {family.members.map((m) => (
              <div className="quote" key={m.provision_id}>
                {m.text.length > 360 ? `${m.text.slice(0, 360)}…` : m.text}
                <div className="muted" style={{ fontSize: ".78rem" }}>{m.regulator} · {m.ref} · {m.document_title}</div>
              </div>
            ))}
          </td>
        </tr>
      )}
    </>
  );
}

function CompareTool() {
  const [a, setA] = useState(SAMPLE_A);
  const [b, setB] = useState(SAMPLE_B);
  const [result, setResult] = useState<Finding[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      const body = { a: { regulator: "A", ref: "provision A", text: a }, b: { regulator: "B", ref: "provision B", text: b } };
      const response = await api.post<{ findings: Finding[] }>("/cross-regulation/compare", body);
      setResult(response.findings);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <Panel title="Compare two provisions">
      <form onSubmit={submit} className="grid two">
        <label className="field">Provision A<textarea id="provision-a" value={a} onChange={(e) => setA(e.target.value)} maxLength={5000} /></label>
        <label className="field">Provision B<textarea id="provision-b" value={b} onChange={(e) => setB(e.target.value)} maxLength={5000} /></label>
        <div><button className="btn primary" type="submit">Check for conflicts</button></div>
      </form>
      {error && <p className="error">{error}</p>}
      {result && (result.length === 0
        ? <p>No divergence, opposite mandate, or retention–erasure tension detected.</p>
        : result.map((f, i) => <p key={i}><StatusPill value={f.severity} /> <strong>{f.type.replace(/_/g, " ")}</strong> — {f.explanation}</p>))}
      <p className="notice">Deterministic detectors only; results are candidates for legal review.</p>
    </Panel>
  );
}
