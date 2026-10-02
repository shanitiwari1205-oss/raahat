import { create } from "zustand";

export interface ZoneState {
  id: string;
  population: number;
  demand: Record<string, number>;
  urgency: number;
  vulnerability_index: number;
}

export interface HospitalState {
  id: string;
  bed_capacity: number;
  beds_used: number;
  icu_capacity: number;
  icu_used: number;
}

export interface DepotState {
  id: string;
  stock: Record<string, number>;
  budget_inr: number;
}

export interface RoadState {
  u: string;
  v: string;
  blocked: boolean;
  travel_time: number;
}

export interface WorldSnapshot {
  tick: number;
  zones: ZoneState[];
  hospitals: HospitalState[];
  depots: DepotState[];
  roads: RoadState[];
}

export interface FeedItem {
  t: number;
  message: string;
}

type ConnectionStatus = "connecting" | "connected" | "disconnected";

interface RaahatStore {
  status: ConnectionStatus;
  world: WorldSnapshot | null;
  feed: FeedItem[];
  connect: (url: string) => void;
}

const MAX_FEED_ITEMS = 40;

export const useRaahatStore = create<RaahatStore>((set, get) => ({
  status: "connecting",
  world: null,
  feed: [],
  connect: (url: string) => {
    const open = () => {
      set({ status: "connecting" });
      const ws = new WebSocket(url);

      ws.onopen = () => set({ status: "connected" });

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "state") {
            set({ world: msg.data as WorldSnapshot });
          } else if (msg.type === "feed") {
            const feed = [msg.data as FeedItem, ...get().feed].slice(0, MAX_FEED_ITEMS);
            set({ feed });
          }
        } catch {
          // malformed frame -- ignore rather than crash the live view
        }
      };

      ws.onclose = () => {
        set({ status: "disconnected" });
        setTimeout(open, 2000); // auto-reconnect, demo must survive a dropped connection
      };

      ws.onerror = () => ws.close();
    };

    open();
  },
}));
