const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  triggerNegotiation: (payload) =>
    request("/negotiations", { method: "POST", body: JSON.stringify(payload) }),
  listNegotiations: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/negotiations${qs ? `?${qs}` : ""}`);
  },
  getNegotiation: (id) => request(`/negotiations/${id}`),
  estimateBatch: (payload) =>
    request("/batch", { method: "POST", body: JSON.stringify({ ...payload, confirm: false }) }),
  runBatch: (payload) =>
    request("/batch", { method: "POST", body: JSON.stringify({ ...payload, confirm: true }) }),
  getBatch: (id) => request(`/batch/${id}`),
  getStats: () => request("/stats"),
  getTermVolatility: () => request("/analysis/term-volatility"),
  getCorrelations: () => request("/analysis/correlations"),
};

export function negotiationSocketUrl(id) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/negotiations/${id}`;
}
