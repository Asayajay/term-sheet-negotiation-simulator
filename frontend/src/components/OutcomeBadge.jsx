const LABELS = {
  deal: "Deal",
  no_deal: "No deal",
  error: "Error",
  pending: "Pending",
  running: "Running",
};

export default function OutcomeBadge({ outcome, status }) {
  const key = outcome || status || "pending";
  return <span className={`badge ${key}`}>{LABELS[key] || key}</span>;
}
