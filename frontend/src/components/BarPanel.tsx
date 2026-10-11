import { useState } from "react";
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Panel } from "./ui";

export interface Series {
  key: string;
  label: string;
  color: string; // a CSS variable, e.g. var(--series-1)
}

interface Props {
  title: string;
  data: Record<string, string | number>[];
  category: string;
  series: Series[];
  format: (v: number) => string;
  domain?: [number, number];
  height?: number;
  caption?: string;
}

// Bars with a per-bar tooltip, direct value labels (contrast relief), a legend for
// two or more series, and a table view. One axis only.
export function BarPanel({ title, data, category, series, format, domain = [0, 1], height = 240, caption }: Props) {
  const [asTable, setAsTable] = useState(false);
  const [width, setWidth] = useState(0);
  // Direct labels only where each bar has room; tooltip and table carry values otherwise.
  const showLabels = width / Math.max(1, data.length * series.length) >= 44;
  return (
    <Panel
      title={title}
      actions={
        <button className="btn" onClick={() => setAsTable((t) => !t)} aria-pressed={asTable}>
          {asTable ? "Show chart" : "Show table"}
        </button>
      }
    >
      {series.length > 1 && !asTable && (
        <div className="legend" aria-label="Legend">
          {series.map((s) => (
            <span key={s.key}>
              <i style={{ background: s.color }} />
              {s.label}
            </span>
          ))}
        </div>
      )}
      {asTable ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{category}</th>
                {series.map((s) => <th key={s.key}>{s.label}</th>)}
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={String(row[category])}>
                  <td>{row[category]}</td>
                  {series.map((s) => <td key={s.key} className="num">{format(Number(row[s.key]))}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ width: "100%", height }}>
          <ResponsiveContainer onResize={(w) => setWidth(w)}>
            <BarChart data={data} margin={{ top: 22, right: 8, left: 0, bottom: 4 }} barGap={2} barCategoryGap="28%">
              <CartesianGrid vertical={false} stroke="var(--grid)" />
              <XAxis dataKey={category} tick={{ fill: "var(--muted)", fontSize: 12 }} axisLine={{ stroke: "var(--line)" }} tickLine={false} />
              <YAxis domain={domain} tickFormatter={format} tick={{ fill: "var(--muted)", fontSize: 12 }} axisLine={false} tickLine={false} width={48} />
              <Tooltip
                cursor={{ fill: "var(--surface-2)" }}
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <div className="chart-tip">
                      <strong>{label}</strong>
                      {payload.map((p) => (
                        <div key={String(p.dataKey)}>
                          {series.find((s) => s.key === p.dataKey)?.label}: <span className="mono">{format(Number(p.value))}</span>
                        </div>
                      ))}
                    </div>
                  ) : null
                }
              />
              {series.map((s) => (
                <Bar key={s.key} dataKey={s.key} fill={s.color} radius={[4, 4, 0, 0]} maxBarSize={34} stroke="var(--surface)" strokeWidth={1}>
                  {showLabels && (
                    <LabelList dataKey={s.key} position="top" formatter={(v: number) => format(v)} style={{ fill: "var(--fg)", fontSize: 11 }} />
                  )}
                </Bar>
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      {caption && <p className="notice">{caption}</p>}
    </Panel>
  );
}
