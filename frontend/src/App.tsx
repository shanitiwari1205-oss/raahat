import { useEffect } from "react";
import { useRaahatStore } from "./store";
import { ReliefMap } from "./components/ReliefMap";
import { Hud } from "./components/Hud";
import "./design-system.css";

// VITE_WS_URL overrides for local dev (backend on a separate port, see .env.local).
// In production (one Vercel project, same-origin), default to /server/ws so no
// env var needs to be set at deploy time -- see vercel.json's rewrite rules.
function defaultWsUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/server/ws`;
}

const WS_URL = import.meta.env.VITE_WS_URL ?? defaultWsUrl();

export default function App() {
  const { status, world, feed, connect } = useRaahatStore();

  useEffect(() => {
    connect(WS_URL);
  }, [connect]);

  return (
    <div style={{ position: "relative", width: "100vw", height: "100vh", overflow: "hidden" }}>
      <ReliefMap world={world} />
      <Hud status={status} world={world} feed={feed} />
    </div>
  );
}
