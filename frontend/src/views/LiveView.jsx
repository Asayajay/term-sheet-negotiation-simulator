import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, negotiationSocketUrl } from "../lib/api.js";
import OutcomeBadge from "../components/OutcomeBadge.jsx";
import TurnCard from "../components/TurnCard.jsx";

export default function LiveView() {
  const { id } = useParams();
  const [negotiation, setNegotiation] = useState(null);
  const [turns, setTurns] = useState([]);
  const [done, setDone] = useState(null);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const neg = await api.getNegotiation(id);
        if (cancelled) return;
        setNegotiation(neg);
        setTurns(neg.rounds || []);

        if (neg.status === "completed" || neg.status === "failed") {
          setDone({ outcome: neg.outcome, total_cost_usd: neg.total_cost_usd, error: neg.error });
          return;
        }

        const ws = new WebSocket(negotiationSocketUrl(id));
        wsRef.current = ws;
        ws.onmessage = (evt) => {
          const msg = JSON.parse(evt.data);
          if (msg.type === "round") {
            setTurns((prev) => [...prev.filter((t) => t.sequence !== msg.sequence), msg].sort((a, b) => a.sequence - b.sequence));
          } else if (msg.type === "done") {
            setDone(msg);
          } else if (msg.type === "error") {
            setError(msg.message);
          }
        };
        ws.onerror = () => setError("Websocket connection error.");
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    }
    load();

    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, [id]);

  if (error) return <div className="error-banner">{error}</div>;
  if (!negotiation) return <p className="subtitle">Loading…</p>;

  const isLive = !done;

  return (
    <div>
      <Link to="/replay" className="subtitle" style={{ display: "inline-block", marginBottom: 12 }}>
        &larr; back to replay
      </Link>
      <div className="card">
        <div className="turn-head" style={{ marginBottom: 12 }}>
          <span className="mono">{negotiation.id}</span>
          <OutcomeBadge outcome={done?.outcome} status={isLive ? "running" : undefined} />
        </div>
        <div className="grid grid-4" style={{ marginBottom: 4 }}>
          <div>
            <div className="stat-label">Model</div>
            <div>{negotiation.model}</div>
          </div>
          <div>
            <div className="stat-label">Max rounds</div>
            <div>{negotiation.max_rounds}</div>
          </div>
          <div>
            <div className="stat-label">Mode</div>
            <div>{negotiation.mock_mode ? "mock" : "live API"}</div>
          </div>
          <div>
            <div className="stat-label">Cost so far</div>
            <div>${(done?.total_cost_usd ?? turns.reduce((s, t) => s + (t.cost_usd || 0), 0)).toFixed(5)}</div>
          </div>
        </div>
      </div>

      {isLive ? (
        <p className="subtitle">
          <span style={{ color: "var(--series-blue)" }}>&#9679;</span> Watching live -- {turns.length} turn(s) so
          far…
        </p>
      ) : done.outcome === "error" ? (
        <div className="error-banner">Negotiation failed: {done.error}</div>
      ) : null}

      {turns.map((t) => (
        <TurnCard key={t.sequence} turn={t} />
      ))}

      {done && done.outcome !== "error" ? (
        <div className="card">
          <h2>Outcome</h2>
          <p>
            <OutcomeBadge outcome={done.outcome} /> after {turns.length} turn(s). Total cost: $
            {done.total_cost_usd?.toFixed(5) ?? "0.00000"}
          </p>
        </div>
      ) : null}
    </div>
  );
}
