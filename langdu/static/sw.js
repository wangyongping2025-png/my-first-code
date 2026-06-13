// 朗读文档 PWA 的 Service Worker
// 作用：让网页可以“添加到主屏幕”并以独立窗口打开；缓存界面外壳，二次打开更快。
// 注意：朗读需要联网（语音是在线生成的），所以语音接口不走缓存。

const CACHE = "langdu-shell-v1";
const SHELL = [
  "/",
  "/static/icon-192.png",
  "/static/icon-512.png",
  "/static/apple-touch-icon.png",
  "/static/manifest.json"
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).catch(() => {})
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  // 只处理 GET；朗读/解析等接口（POST 或 /api/）一律直接走网络
  if (req.method !== "GET" || req.url.includes("/api/")) return;

  // 界面外壳：网络优先，断网时回退到缓存
  event.respondWith(
    fetch(req)
      .then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE).then((cache) => cache.put(req, copy)).catch(() => {});
        return resp;
      })
      .catch(() => caches.match(req))
  );
});
