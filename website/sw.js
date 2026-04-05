/*
 * LidAldi Service Worker
 * Handles Web Push notifications for product alerts.
 */

self.addEventListener("push", function (event) {
  var data = event.data ? event.data.json() : {};
  var title = data.title || "LidAldi Alert";
  var options = {
    body: data.body || "",
    icon: data.icon || "/img/lidaldi.png",
    badge: "/img/lidaldi.png",
    data: { url: data.url || "" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var url = event.notification.data && event.notification.data.url;
  if (url) {
    event.waitUntil(clients.openWindow(url));
  }
});
