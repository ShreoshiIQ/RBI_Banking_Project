import { useState, type ChangeEvent } from "react";
import { api } from "../api";
import { LoadState, PageHead, Panel, StatusPill, Tile, pct } from "../components/ui";
import { useApi } from "../hooks";

interface Chunk { chunk_id: string; text: string; method: string; transcription_verified: boolean; location: Record<string, unknown> }
interface Preview { format: string; file_sha256: string; chunks: Chunk[]; warnings: { reason: string }[] }
interface Summary {
  evidence: {
    available: boolean; reason?: string; silent_errors?: number; records?: { total: number; native: number; ocr: number };
    decisions?: Record<string, number>;
    defect_detection_accepted_only?: { precision: number; recall: number; note: string };
    defect_detection_if_ocr_trusted_blindly?: { precision: number; recall: number; fp: number };
    register_mismatch_detection?: { precision: number; recall: number; tp: number };
    notice?: string;
  };
}

function location(loc: Record<string, unknown>): string {
  if (loc.kind === "xlsx") return `${loc.sheet} ${loc.cell_range}`;
  if (loc.kind === "csv") return `row ${loc.record}`;
  if (loc.kind === "pdf") return `page ${loc.page}${loc.region_scope ? " (whole page)" : ""}`;
  if (loc.kind === "image") return "whole image";
  return String(loc.kind ?? "");
}

export function Evidence() {
  const summary = useApi<Summary>("/insights/summary");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const e = summary.data?.evidence;

  const upload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    setPreview(null);
    try {
      setPreview(await api.upload<Preview>("/ingestion/evidence-preview", file));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  };

  return (
    <>
      <PageHead title="Evidence" sub="Parse evidence files with source locations, and review how the pipeline performed on the synthetic multimodal evidence pack." />
      <LoadState loading={summary.loading} error={summary.error} />
      {e?.available && (
        <>
          <div className="grid tiles">
            <Tile label="Wrong values accepted without review" value={e.silent_errors} note={`${e.records?.total} records, ${e.records?.ocr} via OCR`} />
            <Tile label="Defect detection (accepted records)" value={`${e.defect_detection_accepted_only?.precision.toFixed(2)} / ${e.defect_detection_accepted_only?.recall.toFixed(2)}`} note="precision / recall" />
            <Tile label="If OCR were trusted blindly" value={`${e.defect_detection_if_ocr_trusted_blindly?.fp} false`} note="defect findings avoided by corroboration" />
            <Tile label="Register mismatches found" value={pct(e.register_mismatch_detection?.recall, 0)} note={`${e.register_mismatch_detection?.tp} planted, precision ${e.register_mismatch_detection?.precision.toFixed(2)}`} />
          </div>
          <Panel title="Record decisions">
            <div className="table-wrap">
              <table>
                <tbody>
                  {Object.entries(e.decisions ?? {}).map(([k, v]) => (
                    <tr key={k}><td>{k.replace(/_/g, " ")}</td><td className="num">{v}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="notice">{e.notice}</p>
          </Panel>
        </>
      )}

      <Panel title="Preview an evidence file">
        <label className="field">
          PDF, DOCX, XLSX, CSV, PNG or JPG, up to 5 MB
          <input id="evidence-file" type="file" accept=".pdf,.docx,.xlsx,.csv,.png,.jpg,.jpeg" onChange={upload} disabled={busy} />
        </label>
        {busy && <p className="muted">Parsing…</p>}
        {error && <p className="error">{error}</p>}
        {preview && (
          <>
            <p className="muted">
              {preview.format.toUpperCase()} · {preview.chunks.length} extracted units · <span className="mono">{preview.file_sha256.slice(0, 16)}…</span>
            </p>
            {preview.warnings.map((w, i) => <p key={i}><StatusPill value="needs_review" /> {w.reason.replace(/_/g, " ")}</p>)}
            <div className="table-wrap">
              <table>
                <thead><tr><th>Location</th><th>Method</th><th>Text</th></tr></thead>
                <tbody>
                  {preview.chunks.slice(0, 200).map((c) => (
                    <tr key={c.chunk_id}>
                      <td className="num">{location(c.location)}</td>
                      <td><StatusPill value={c.transcription_verified ? "supported" : "needs_review"} /> {c.method}</td>
                      <td>{c.text.length > 300 ? `${c.text.slice(0, 300)}…` : c.text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        <p className="notice">Preview only: nothing is stored. Image content needs OCR, which runs in the ingestion pipeline, not here.</p>
      </Panel>
    </>
  );
}
