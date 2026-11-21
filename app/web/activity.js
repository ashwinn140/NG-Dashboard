/* Authenticated interaction heartbeat. No background polling: events are
   throttled to one request per session every two minutes. */
(() => {
  let lastSent = 0;
  let lastInteraction = 0;
  const sendHeartbeat = () => {
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
  const send = () => {
    if (document.visibilityState !== "visible") return;
    lastInteraction = Date.now();
    sendHeartbeat();
  };
  const keepAliveWhileRecentlyActive = () => {
    if (document.visibilityState !== "visible" || !lastInteraction) return;
    if (Date.now() - lastInteraction >= 60 * 60 * 1000) return;
    sendHeartbeat();
  };
  ["pointerdown", "keydown", "touchstart", "wheel", "scroll"].forEach(type => {
    document.addEventListener(type, send, { passive: true, capture: true });
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && lastInteraction && Date.now() - lastInteraction < 60 * 60 * 1000) {
      sendHeartbeat();
    }
  });
  // Keep the service warm only while a visible tab has had genuine interaction
  // in the last hour. Once idle for an hour, heartbeats stop and Railway may sleep.
  window.setInterval(keepAliveWhileRecentlyActive, 240000);
})();
