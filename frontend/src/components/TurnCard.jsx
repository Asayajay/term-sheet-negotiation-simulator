const FIELD_LABELS = {
  pre_money_valuation_usd: "Pre-money valuation",
  equity_percentage: "Equity %",
  liquidation_preference_multiple: "Liquidation pref (x)",
  liquidation_participating: "Participating",
  board_seats_founder: "Board seats (founder)",
  board_seats_investor: "Board seats (investor)",
  board_seats_independent: "Board seats (independent)",
  option_pool_percentage: "Option pool %",
  vesting_years: "Vesting (years)",
  vesting_cliff_months: "Vesting cliff (months)",
  pro_rata_rights: "Pro-rata rights",
  anti_dilution: "Anti-dilution",
};

function formatValue(field, value) {
  if (value === null || value === undefined) return "—";
  if (field === "pre_money_valuation_usd") return `$${Number(value).toLocaleString()}`;
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

export default function TurnCard({ turn }) {
  const changedFields = new Set(Object.keys(turn.diff || {}));
  return (
    <div className={`turn ${turn.actor}`}>
      <div className="turn-head">
        <span>
          Round {turn.round_number} &middot; {turn.actor === "founder" ? "Founder" : "VC"} &middot;{" "}
          <strong style={{ textTransform: "uppercase" }}>{turn.action.replace("_", " ")}</strong>
        </span>
        {turn.cost_usd !== undefined && turn.cost_usd > 0 ? (
          <span className="mono">${turn.cost_usd.toFixed(5)}</span>
        ) : null}
      </div>
      <div className="turn-reasoning">{turn.reasoning}</div>
      {turn.terms ? (
        <table className="terms-table">
          <tbody>
            {Object.entries(FIELD_LABELS).map(([field, label]) => (
              <tr key={field}>
                <td>{label}</td>
                <td className={changedFields.has(field) ? "changed" : ""}>
                  {formatValue(field, turn.terms[field])}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}
