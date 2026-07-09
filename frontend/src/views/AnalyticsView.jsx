import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../lib/api.js";
import StatTile from "../components/StatTile.jsx";

const TERM_LABELS = {
  pre_money_valuation_usd: "Pre-money valuation",
  equity_percentage: "Equity %",
  liquidation_preference_multiple: "Liquidation pref",
  liquidation_participating: "Participating",
  board_seats_founder: "Founder board seats",
  board_seats_investor: "Investor board seats",
  board_seats_independent: "Independent board seats",
  option_pool_percentage: "Option pool %",
  vesting_years: "Vesting years",
  vesting_cliff_months: "Vesting cliff",
  pro_rata_rights: "Pro-rata rights",
  anti_dilution: "Anti-dilution",
};

const CONDITION_LABELS = {
  "founder.runway_months": "Founder runway (months)",
  "founder.competing_offers": "Founder competing offers",
  "founder.monthly_revenue_usd": "Founder monthly revenue",
  "founder.revenue_growth_rate_pct": "Founder revenue growth",
  "vc.deal_enthusiasm": "VC deal enthusiasm",
  "vc.fund_size_musd": "VC fund size",
  "vc.investment_amount_musd": "VC investment amount",
};

function ChartTooltip({ active, payload, label, formatter }) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "var(--surface-1)",
        border: "1px solid var(--border)",
        borderRadius: 6,
        padding: "8px 10px",
        fontSize: 12,
        color: "var(--text-primary)",
      }}
    >
      <div style={{ color: "var(--text-secondary)", marginBottom: 4 }}>{label}</div>
      <div>{formatter ? formatter(payload[0].value) : payload[0].value}</div>
    </div>
  );
}

export default function AnalyticsView() {
  const [stats, setStats] = useState(null);
  const [volatility, setVolatility] = useState(null);
  const [correlations, setCorrelations] = useState(null);
  const [negotiations, setNegotiations] = useState([]);
  const [outcomeMetric, setOutcomeMetric] = useState("final_valuation");
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      api.getStats(),
      api.getTermVolatility(),
      api.getCorrelations(),
      api.listNegotiations({ limit: 200 }),
    ])
      .then(([s, v, c, negs]) => {
        setStats(s);
        setVolatility(v);
        setCorrelations(c);
        setNegotiations(negs.slice().reverse()); // chronological
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="error-banner">{error}</div>;
  if (!stats) return <p className="subtitle">Loading…</p>;

  const volatilityData = volatility
    ? Object.entries(volatility)
        .map(([field, v]) => ({
          field,
          label: TERM_LABELS[field] || field,
          pct: v.pct_volatility ?? v.change_rate * 100,
          n: v.n_changes_observed,
        }))
        .sort((a, b) => b.pct - a.pct)
    : [];

  const correlationData = correlations
    ? Object.entries(correlations)
        .map(([cond, byOutcome]) => ({
          cond,
          label: CONDITION_LABELS[cond] || cond,
          value: byOutcome[outcomeMetric] ?? 0,
        }))
        .filter((d) => d.value !== 0)
        .sort((a, b) => b.value - a.value)
    : [];

  let cumulative = 0;
  const spendData = negotiations.map((n, i) => {
    cumulative += n.total_cost_usd;
    return { i: i + 1, id: n.id, cumulative: Number(cumulative.toFixed(4)) };
  });

  return (
    <div>
      <div className="grid grid-4">
        <StatTile label="Total negotiations" value={stats.total_negotiations} sub={`${stats.completed} completed`} />
        <StatTile
          label="Deal rate"
          value={stats.completed ? `${Math.round((stats.deals / stats.completed) * 100)}%` : "—"}
          sub={`${stats.deals} deals / ${stats.no_deals} no-deal`}
        />
        <StatTile
          label="Avg rounds to close"
          value={stats.avg_rounds_to_close ? stats.avg_rounds_to_close.toFixed(1) : "—"}
        />
        <StatTile label="Total API spend" value={`$${stats.total_cost_usd.toFixed(4)}`} sub="across all runs" />
      </div>

      <div className="card">
        <h2>Term volatility -- which terms moved most under pressure</h2>
        <p className="subtitle" style={{ marginTop: -6 }}>
          Average change per round-to-round proposal, normalized to % of the term's own scale.
          Terms near zero were effectively non-negotiable.
        </p>
        {volatilityData.length === 0 ? (
          <p className="subtitle">No completed negotiations yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={volatilityData} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid horizontal={false} stroke="var(--gridline)" />
              <XAxis
                type="number"
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--baseline)" }}
                tickLine={false}
                unit="%"
              />
              <YAxis
                type="category"
                dataKey="label"
                width={170}
                tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
                axisLine={{ stroke: "var(--baseline)" }}
                tickLine={false}
              />
              <Tooltip content={<ChartTooltip formatter={(v) => `${v.toFixed(2)}% avg change per round`} />} />
              <Bar dataKey="pct" fill="var(--series-blue)" radius={[0, 4, 4, 0]} maxBarSize={18} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="card">
        <div className="turn-head" style={{ marginBottom: 0 }}>
          <h2>Starting conditions vs. outcome (Pearson correlation)</h2>
          <select
            value={outcomeMetric}
            onChange={(e) => setOutcomeMetric(e.target.value)}
            style={{ width: 200 }}
          >
            <option value="final_valuation">Final valuation</option>
            <option value="final_equity_pct">Final equity %</option>
            <option value="rounds_to_close">Rounds to close</option>
            <option value="deal_reached">Deal reached</option>
          </select>
        </div>
        <p className="subtitle">
          Positive means higher starting value correlates with a higher outcome value; negative
          the opposite. Only pairs with enough data show up.
        </p>
        {correlationData.length === 0 ? (
          <p className="subtitle">Not enough completed negotiations yet to compute correlations.</p>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={correlationData} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid horizontal={false} stroke="var(--gridline)" />
              <XAxis
                type="number"
                domain={[-1, 1]}
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--baseline)" }}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="label"
                width={170}
                tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
                axisLine={{ stroke: "var(--baseline)" }}
                tickLine={false}
              />
              <ReferenceLine x={0} stroke="var(--baseline)" />
              <Tooltip content={<ChartTooltip formatter={(v) => `r = ${v.toFixed(3)}`} />} />
              <Bar dataKey="value" radius={4} maxBarSize={18}>
                {correlationData.map((d) => (
                  <Cell key={d.cond} fill={d.value >= 0 ? "var(--series-blue)" : "var(--series-red)"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="card">
        <h2>Running total API spend</h2>
        <p className="subtitle" style={{ marginTop: -6 }}>
          Cumulative actual cost across every negotiation run so far, in run order.
        </p>
        {spendData.length === 0 ? (
          <p className="subtitle">No negotiations yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={spendData} margin={{ left: 8, right: 12 }}>
              <CartesianGrid stroke="var(--gridline)" vertical={false} />
              <XAxis
                dataKey="i"
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--baseline)" }}
                tickLine={false}
                label={{ value: "negotiation #", position: "insideBottom", offset: -4, fill: "var(--text-muted)", fontSize: 11 }}
              />
              <YAxis
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--baseline)" }}
                tickLine={false}
                tickFormatter={(v) => `$${v}`}
              />
              <Tooltip content={<ChartTooltip formatter={(v) => `$${v.toFixed(4)} cumulative`} />} />
              <Line
                type="monotone"
                dataKey="cumulative"
                stroke="var(--series-blue)"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
