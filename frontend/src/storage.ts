// Per-viewer convenience only (intro dismissal) -- never load-bearing state.
// Wrapped defensively: private browsing / blocked storage must never break render.
const INTRO_DISMISSED_KEY = "raahat.intro.dismissed.v1";

export function readIntroDismissed(): boolean {
  try {
    return localStorage.getItem(INTRO_DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

export function writeIntroDismissed(): void {
  try {
    localStorage.setItem(INTRO_DISMISSED_KEY, "1");
  } catch {
    // ignore -- just won't be remembered next visit
  }
}
