import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

/**
 * Cross-fade the inline boot splash into the React-rendered LabLoader.
 *
 * The splash sits outside #root so React doesn't tear it down on first
 * commit. We wait two animation frames so:
 *   1. React has committed the initial render (frame 1).
 *   2. The browser has actually painted that commit (frame 2).
 *
 * Then we trigger the CSS opacity transition and remove the element
 * once the fade lands. End result: zero black-frame gap between the
 * HTML splash and the React loader.
 */
function dismissBootSplash() {
  const el = document.getElementById("boot-splash");
  if (!el) return;
  el.classList.add("boot-splash-fade");
  // Slightly longer than the CSS transition so we don't yank the DOM
  // mid-fade on slower machines.
  window.setTimeout(() => el.remove(), 400);
}

requestAnimationFrame(() => {
  requestAnimationFrame(dismissBootSplash);
});
