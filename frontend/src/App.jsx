import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import TriggerView from "./views/TriggerView.jsx";
import LiveView from "./views/LiveView.jsx";
import ReplayView from "./views/ReplayView.jsx";
import AnalyticsView from "./views/AnalyticsView.jsx";

export default function App() {
  return (
    <div className="app-shell">
      <div className="title-row">
        <h1>Term Sheet Negotiation Simulator</h1>
      </div>
      <p className="subtitle">Two Claude agents negotiate a startup term sheet, round by round.</p>
      <nav className="nav">
        <NavLink to="/trigger" className={({ isActive }) => (isActive ? "active" : "")}>
          Trigger
        </NavLink>
        <NavLink to="/replay" className={({ isActive }) => (isActive ? "active" : "")}>
          Replay
        </NavLink>
        <NavLink to="/analytics" className={({ isActive }) => (isActive ? "active" : "")}>
          Analytics
        </NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to="/trigger" replace />} />
        <Route path="/trigger" element={<TriggerView />} />
        <Route path="/live/:id" element={<LiveView />} />
        <Route path="/replay" element={<ReplayView />} />
        <Route path="/replay/:id" element={<LiveView replay />} />
        <Route path="/analytics" element={<AnalyticsView />} />
      </Routes>
    </div>
  );
}
