import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api.js";
import OutcomeBadge from "../components/OutcomeBadge.jsx";

export default function ReplayView() {
  const [negotiations, setNegotiations] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      const data = await api.listNegotiations({ limit: 100 });
      setNegotiations(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, []);

  if (error) return <div className="error-banner">{error}</div>;

  return (
    <div>
      <div className="card">
        <h2>Past negotiations</h2>
        {loading ? (
          <p className="subtitle">Loading…</p>
        ) : negotiations.length === 0 ? (
          <p className="subtitle">
            None yet -- trigger one from the <Link to="/trigger">Trigger</Link> view.
          </p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Model</th>
                <th>Outcome</th>
                <th>Valuation</th>
                <th>Equity %</th>
                <th>Rounds to close</th>
                <th>Cost</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {negotiations.map((n) => (
                <tr key={n.id}>
                  <td>
                    <Link to={`/replay/${n.id}`} className="mono">
                      {n.id.slice(0, 10)}…
                    </Link>
                  </td>
                  <td>{n.model}</td>
                  <td>
                    <OutcomeBadge outcome={n.outcome} status={n.status} />
                  </td>
                  <td>{n.final_valuation ? `$${Math.round(n.final_valuation).toLocaleString()}` : "—"}</td>
                  <td>{n.final_equity_pct ?? "—"}</td>
                  <td>{n.rounds_to_close ?? "—"}</td>
                  <td>${n.total_cost_usd.toFixed(5)}</td>
                  <td>{new Date(n.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
