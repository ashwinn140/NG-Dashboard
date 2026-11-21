/* Authenticated interaction heartbeat. No background polling: events are
   throttled to one request per session every two minutes. */
(() => {
  let lastSent = 0;
  const send = () => {
    if (document.visibilityState !== "visible") return;
    const now = Date.now();
    if (now - lastSent < 120000) return;
    const csrf = window.__ME?.csrf || window.NG_CSRF || "";
    if (!csrf) return;
    lastSent = now;
    fetch("/api/activity/heartbeat", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRF-Token": csrf }
    }).catch(() => {});
  };
  ["pointerdown", "keydown", "touchstart", "wheel", "scroll"].forEach(type => {
    document.addEventListener(type, send, { passive: true, capture: true });
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") send();
  });
})();
