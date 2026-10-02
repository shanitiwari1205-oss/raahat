import { useEffect, useRef, useState } from "react";
import { useRaahatStore } from "./store";
import type { RoadState } from "./store";
import { ReliefMap } from "./components/ReliefMap";
import { Hud } from "./components/Hud";
import { ControlCenter } from "./components/ControlCenter";
import { IntroOverlay } from "./components/IntroOverlay";
import { readIntroDismissed, writeIntroDismissed } from "./storage";
import { api, API_BASE, ApiError } from "./api";
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
  const { status, world, feed, activeFlows, replayMode, connect, loadReplay, exitReplay } = useRaahatStore();
  const [introOpen, setIntroOpen] = useState(() => !readIntroDismissed());
  const [mapToast, setMapToast] = useState<{ ok: boolean; message: string } | null>(null);
  const replayAttempted = useRef(false);

  useEffect(() => {
    connect(WS_URL);
  }, [connect]);

  // Phase 6.3 demo-safety net: if the live connection drops, pull the last
  // ~60s from the backend's replay buffer once (not on every reconnect
  // flicker) so the screen keeps showing real activity instead of going dark.
  useEffect(() => {
    if (status === "disconnected" && !replayAttempted.current) {
      replayAttempted.current = true;
      void loadReplay(API_BASE);
    }
    if (status === "connected") {
      replayAttempted.current = false;
    }
  }, [status, loadReplay]);

  useEffect(() => {
    if (!mapToast) return;
    const t = setTimeout(() => setMapToast(null), 4000);
    return () => clearTimeout(t);
  }, [mapToast]);

  const closeIntro = () => {
    setIntroOpen(false);
    writeIntroDismissed();
  };

  const handleRoadClick = async (road: RoadState) => {
    if (road.blocked) {
      setMapToast({ ok: false, message: `${road.u} → ${road.v} is already blocked.` });
      return;
    }
    try {
      await api.roadBlock(road.u, road.v);
      setMapToast({ ok: true, message: `Blocked ${road.u} → ${road.v}. Watch the Allocation Feed.` });
    } catch (e) {
      setMapToast({ ok: false, message: e instanceof ApiError ? e.message : "Couldn't block that road." });
    }
  };

  return (
    <div style={{ position: "relative", width: "100vw", height: "100vh", overflow: "hidden" }}>
      <ReliefMap world={world} activeFlows={activeFlows} onRoadClick={handleRoadClick} />
      <Hud status={status} world={world} feed={feed} replayMode={replayMode} onExitReplay={exitReplay} />

      {mapToast && (
        <div
          className={`action-result ${mapToast.ok ? "ok" : "err"}`}
          style={{ position: "absolute", bottom: 16, left: "50%", transform: "translateX(-50%)", pointerEvents: "none" }}
        >
          {mapToast.message}
        </div>
      )}

      <div
        style={{
          position: "absolute",
          top: 16,
          right: 16,
          width: 360,
          maxHeight: "calc(100vh - 32px)",
          display: "flex",
          flexDirection: "column",
          pointerEvents: "none",
        }}
      >
        <ControlCenter world={world} />
      </div>

      <button
        className="hard-button help-fab"
        onClick={() => setIntroOpen(true)}
        title="What is RAAHAT? / How to test it"
      >
        ?
      </button>

      <IntroOverlay open={introOpen} onClose={closeIntro} />
    </div>
  );
}
