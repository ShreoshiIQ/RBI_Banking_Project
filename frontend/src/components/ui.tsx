import type { ReactNode } from "react";

type Tone = "good" | "warning" | "serious" | "critical" | "neutral";

const TONES: Record<string, Tone> = {
  supported: "good", approved: "good", applicable: "good", test_passed: "good", likely_applicable: "good",
  partial: "warning", pending_review: "warning", pending: "warning", presumed_applicable: "warning",
  needs_review: "warning", undetermined: "warning", candidate: "warning", medium: "warning",
  potential_conflict: "serious", high: "serious", presumed_not_applicable: "neutral", likely_not_applicable: "neutral",
  missing: "critical", rejected: "critical", critical: "critical", not_applicable: "neutral", error: "critical",
};

export function StatusPill({ value }: { value: string | null | undefined }) {
  const text = (value ?? "unknown").replace(/_/g, " ");
  const tone = TONES[value ?? ""] ?? "neutral";
  return (
    <span className={`pill ${tone}`}>
      <span className="dot" aria-hidden="true" />
      {text}
    </span>
  );
}

export function Tile({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div className="tile">
      <span className="label">{label}</span>
      <span className="value">{value}</span>
      {note && <span className="note">{note}</span>}
    </div>
  );
}

export function Panel({ title, children, actions }: { title?: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="panel">
      {(title || actions) && (
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
          {title && <h2 style={{ margin: 0 }}>{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function PageHead({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <p className="sub">{sub}</p>}
      </div>
      {actions}
    </div>
  );
}

export function LoadState({ loading, error, empty }: { loading: boolean; error: string | null; empty?: boolean }) {
  if (loading) return <p className="empty">Loading…</p>;
  if (error) return <p className="empty error">{error}</p>;
  if (empty) return <p className="empty">Nothing to show yet.</p>;
  return null;
}

export const pct = (v: number | null | undefined, digits = 1) =>
  v == null ? "–" : `${(v * 100).toFixed(digits)}%`;

export const date = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "–";
