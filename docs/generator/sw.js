/* 서비스워커 — 오프라인 캐시 + 백그라운드 자동 갱신
 * 빌드 시 20260617-224556 / druginfo-gen 치환. 버전이 바뀌면 옛 캐시 무효화 → 다음 실행 때 새 버전 적용.
 */
const VERSION = "20260617-224556";
const APP = "druginfo-gen";
const CACHE = `${APP}-${VERSION}`;

// 오프라인 핵심 리소스 (앱 HTML + 매니페스트). qrcode/jsQR은 이미 HTML에 인라인됨.
const CORE = ["./", "./index.html", "./manifest.json"];
const TAILWIND = "https://cdn.tailwindcss.com";

self.addEventListener("install", (e) => {
  e.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(CORE);
    // 크로스오리진(Tailwind)은 no-cors로 받아 opaque 응답 캐시 (오프라인 스타일 유지)
    try {
      const res = await fetch(TAILWIND, { mode: "no-cors" });
      await cache.put(TAILWIND, res);
    } catch (_) {}
    self.skipWaiting();
  })());
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    // 같은 앱의 옛 버전 캐시 정리
    const keys = await caches.keys();
    await Promise.all(
      keys.filter(k => k.startsWith(APP + "-") && k !== CACHE).map(k => caches.delete(k))
    );
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  e.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(req, { ignoreSearch: true });
    // 캐시 우선 + 백그라운드 갱신(stale-while-revalidate): 다음 실행 때 최신 자동 반영
    const network = fetch(req).then(res => {
      if (res && (res.ok || res.type === "opaque")) cache.put(req, res.clone()).catch(() => {});
      return res;
    }).catch(() => null);
    return cached || (await network) || cache.match("./index.html");
  })());
});
