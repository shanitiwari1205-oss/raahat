import { create } from "zustand";

export interface ZoneState {
  id: string;
  population: number;
  demand: Record<string, number>;
  urgency: number;
  vulnerability_index: number;
  lat: number;
  lon: number;
}

export interface HospitalState {
  id: string;
  bed_capacity: number;
  beds_used: number;
  icu_capacity: number;
  icu_used: number;
  lat: number;
  lon: number;
}

export interface DepotState {
  id: string;
  stock: Record<string, number>;
  budget_inr: number;
  lat: number;
  lon: number;
}

export interface RoadState {
  u: string;
  v: string;
  blocked: boolean;
  travel_time: number;
  u_coords: { lat: number; lon: number };
  v_coords: { lat: number; lon: number };
}

export interface WorldSnapshot {
  tick: number;
  zones: ZoneState[];
  hospitals: HospitalState[];
  depots: DepotState[];
  roads: RoadState[];
}

export interface RawFlow {
  depot_id: string;
  zone_id: string;
  resource: string;
  amount: number;
  fund_amount: number;
}

export interface FeedItem {
  t: number;
  message: string;
  flows?: RawFlow[];
}

export interface FlowItem extends RawFlow {
  id: string;
  t: number; // client-side Date.now() when it arrived, for fade/prune
}

type ConnectionStatus = "connecting" | "connected" | "disconnected";

interface RaahatStore {
  status: ConnectionStatus;
  world: WorldSnapshot | null;
  feed: FeedItem[];
  activeFlows: FlowItem[];
  replayMode: boolean;
  connect: (url: string) => void;
  loadReplay: (apiBase: string) => Promise<void>;
  exitReplay: () => void;
}

const MAX_FEED_ITEMS = 40;
const FLOW_TTL_MS = 5000;
const FLOW_TICK_MS = 200;

// Module-level (not store-state) so StrictMode's intentional double-invoke of
// mount effects in dev -- and any other accidental re-mount -- can never open
// a second live socket for the same URL and double every broadcast feed item.
let activeSocket: WebSocket | null = null;
let activeUrl: string | null = null;
let flowTickerId: number | null = null;

function ensureFlowTicker(
  get: () => RaahatStore,
  set: (partial: Partial<RaahatStore>) => void,
) {
  if (flowTickerId !== null) return;
  flowTickerId = window.setInterval(() => {
    const now = Date.now();
    const remaining = get().activeFlows.filter((f) => now - f.t < FLOW_TTL_MS);
    set({ activeFlows: remaining });
    if (remaining.length === 0 && flowTickerId !== null) {
      window.clearInterval(flowTickerId);
      flowTickerId = null;
    }
  }, FLOW_TICK_MS);
}

let flowCounter = 0;

export const useRaahatStore = create<RaahatStore>((set, get) => ({
  status: "connecting",
  world: null,
  feed: [],
  activeFlows: [],
  replayMode: false,
  connect: (url: string) => {
    if (activeUrl === url && activeSocket && activeSocket.readyState <= WebSocket.OPEN) {
      return;
    }
    activeUrl = url;

    const open = () => {
      if (activeUrl !== url) return; // a newer connect() superseded this one
      set({ status: "connecting" });
      const ws = new WebSocket(url);
      activeSocket = ws;

      ws.onopen = () => set({ status: "connected", replayMode: false });

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "state") {
            set({ world: msg.data as WorldSnapshot });
          } else if (msg.type === "feed") {
            const item = msg.data as FeedItem;
            const feed = [item, ...get().feed].slice(0, MAX_FEED_ITEMS);
            let activeFlows = get().activeFlows;
            if (item.flows && item.flows.length) {
              const now = Date.now();
              const newFlows: FlowItem[] = item.flows.map((f) => ({
                ...f,
                id: `flow-${now}-${flowCounter++}`,
                t: now,
              }));
              activeFlows = [...activeFlows, ...newFlows];
            }
            set({ feed, activeFlows });
            ensureFlowTicker(get, set);
          }
        } catch {
          // malformed frame -- ignore rather than crash the live view
        }
      };

      ws.onclose = () => {
        if (activeUrl !== url) return; // superseded -- don't resurrect a stale connection
        set({ status: "disconnected" });
        setTimeout(open, 2000); // auto-reconnect, demo must survive a dropped connection
      };

      ws.onerror = () => ws.close();
    };

    open();
  },

  // Phase 6.3 demo-safety net: if the live connection drops, pull the last
  // ~60s of real broadcasts from the backend's replay buffer so the screen
  // still shows genuine (if slightly stale) activity instead of going dark
  // mid-demo while the WebSocket auto-reconnects in the background.
  loadReplay: async (apiBase: string) => {
    try {
      const res = await fetch(`${apiBase}/replay`);
      if (!res.ok) return;
      const body = await res.json() as { window_s: number; items: { type: string; data: unknown; t: number }[] };
      const states = body.items.filter((i) => i.type === "state");
      const feeds = body.items.filter((i) => i.type === "feed");
      const lastState = states[states.length - 1];
      set({
        replayMode: true,
        world: lastState ? (lastState.data as WorldSnapshot) : get().world,
        feed: feeds.map((i) => i.data as FeedItem).reverse().slice(0, MAX_FEED_ITEMS),
      });
    } catch {
      // replay is a best-effort safety net -- a failed fetch here shouldn't crash anything
    }
  },

  exitReplay: () => set({ replayMode: false }),
}));
