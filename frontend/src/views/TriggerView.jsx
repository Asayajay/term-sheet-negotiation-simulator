import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";

const MODELS = ["claude-haiku-4-5", "claude-sonnet-5"];

export default function TriggerView() {
  const navigate = useNavigate();
  const [model, setModel] = useState(MODELS[0]);
  const [maxRounds, setMaxRounds] = useState(6);
  const [mockMode, setMockMode] = useState(true);
  const [estimate, setEstimate] = useState(null);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);

  async function getEstimate() {
    setError(null);
    try {
      const est = await api.estimateBatch({ size: 1, model, max_rounds: Number(maxRounds), mock_mode: mockMode });
      setEstimate(est);
    } catch (e) {
      setError(e.message);
    }
  }

  async function start() {
    setStarting(true);
    setError(null);
    try {
      const res = await api.triggerNegotiation({ model, max_rounds: Number(maxRounds), mock_mode: mockMode });
      navigate(`/live/${res.negotiation_id}`);
    } catch (e) {
      setError(e.message);
      setStarting(false);
    }
  }

  return (
    <div>
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="card" style={{ maxWidth: 480 }}>
        <h2>Start a negotiation</h2>
        <div className="field">
          <label>Model</label>
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {MODELS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Max rounds (round-trips, hard cap 12)</label>
          <input
            type="number"
            min={1}
            max={12}
            value={maxRounds}
            onChange={(e) => setMaxRounds(e.target.value)}
          />
        </div>
        <div className="field">
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="checkbox"
              style={{ width: "auto" }}
              checked={mockMode}
              onChange={(e) => setMockMode(e.target.checked)}
            />
            Mock mode (dry run, zero API cost)
          </label>
        </div>

        <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
          <button className="secondary" onClick={getEstimate}>
            Estimate cost
          </button>
          <button className="primary" onClick={start} disabled={starting}>
            {starting ? "Starting…" : "Start negotiation"}
          </button>
        </div>

        {estimate ? (
          <p className="subtitle" style={{ marginTop: 16, marginBottom: 0 }}>
            Estimated ceiling cost: <strong>${estimate.estimated_cost_usd.toFixed(4)}</strong>{" "}
            for up to {estimate.max_rounds} rounds on {estimate.model}.
            {mockMode ? " (Mock mode always costs $0 -- no API calls are made.)" : ""}
          </p>
        ) : null}
      </div>

      <div className="card" style={{ maxWidth: 480 }}>
        <h2>Founder and VC starting positions</h2>
        <p className="subtitle" style={{ marginBottom: 0 }}>
          Starting parameters (runway, competing offers, risk appetite, deal enthusiasm, etc.)
          are randomized within the configured ranges for each negotiation. Run a batch from the
          CLI (<code className="mono">scripts/run_batch.py</code>) to sweep specific scenarios.
        </p>
      </div>
    </div>
  );
}
