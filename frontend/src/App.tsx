import { HashRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { CrossRegulation } from "./pages/CrossRegulation";
import { Evidence } from "./pages/Evidence";
import { GapReportDetail } from "./pages/GapReportDetail";
import { GapReports } from "./pages/GapReports";
import { Login } from "./pages/Login";
import { Monitor } from "./pages/Monitor";
import { Overview } from "./pages/Overview";

const NAV = [
  { to: "/", label: "Overview", end: true },
  { to: "/reports", label: "Gap reports" },
  { to: "/monitor", label: "Regulatory monitor" },
  { to: "/cross-regulation", label: "Cross-regulation" },
  { to: "/evidence", label: "Evidence" },
];

export function App() {
  const { user, loading, signOut } = useAuth();
  if (loading) return <p className="empty">Loading…</p>;
  if (!user) return <Login />;
  return (
    <HashRouter>
      <div className="shell">
        <nav className="nav" aria-label="Main">
          <div className="brand">
            RegIntel
            <small>Regulatory compliance</small>
          </div>
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}>
              {item.label}
            </NavLink>
          ))}
          <div className="spacer" />
          <div className="who">
            <span>
              {user.username} · {user.role.replace(/_/g, " ")}
            </span>
            <button className="btn" onClick={signOut}>Sign out</button>
          </div>
        </nav>
        <main className="main">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/reports" element={<GapReports />} />
            <Route path="/reports/:reportId" element={<GapReportDetail />} />
            <Route path="/monitor" element={<Monitor />} />
            <Route path="/cross-regulation" element={<CrossRegulation />} />
            <Route path="/evidence" element={<Evidence />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  );
}
