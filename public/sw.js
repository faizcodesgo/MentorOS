/* MentorOS service worker — PUSH ONLY. Deliberately no fetch/cache handler
   (caching is the classic stale-JS footgun that breaks deploys). */

self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data.json(); } catch (e) {}
  event.waitUntil(
    self.registration.showNotification(data.title || "MentorOS", {
      body: data.body || "",
      icon: "/icon-192.png",
      badge: "/icon-192.png",
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((cs) => {
      for (const c of cs) if ("focus" in c) return c.focus();
      return clients.openWindow("/");
    })
  );
});
