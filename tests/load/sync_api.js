// T13 load tier: k6 vs the sync API contract (docs/sync-contract.md).
//
// Mix per iteration: valid GET/POST round-trips plus deliberate invalid
// payloads (bad sync code -> 400, boolean lastVisit -> 400, oversized
// body -> 413). Those statuses are *expected*, so they are registered via
// http.expectedStatuses and do not count towards http_req_failed.
//
// Rate limiting: the server limits 30 req/min per client IP, with no TOML
// knob to raise it (RATE_MAX is a module constant) and T13 must not touch
// application code. The server trusts X-Forwarded-For from loopback
// (nginx-style deployment), so the scenario simulates a population of
// distinct client IPs — one unique IP per iteration (~6 requests each),
// keeping every simulated client far under the 30 req/min limit. The rate
// limiter stays on the hot path of every request; its 429 behaviour itself
// is covered by unit tests (tests/unit/test_sync_server.py).
//
// Thresholds (justification): target is the single-process Python
// ThreadingHTTPServer doing an fcntl-locked read-modify-write on a tmpfs
// profile file per request, over 127.0.0.1. Per-request service time is
// ~1-5 ms; at the shaped ~40-70 req/s this leaves >50x headroom, so
// p(95)<500ms only fires on pathological serialization (lock convoy,
// event-loop stall) rather than CI noise. med<50ms is the tighter guard:
// the median is far more stable than the tail on shared CI runners
// (observed ~1.2 ms, ~40x headroom) and catches a broad slowdown that the
// loose p95 bound would let through. error rate <1% likewise: every
// response status in the scenario is deterministic.
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.SYNC_API_URL || 'http://127.0.0.1:8099';

// 400/413 are elicited on purpose by the invalid-payload probes.
http.setResponseCallback(http.expectedStatuses(200, 400, 413));

export const options = {
  scenarios: {
    mix: {
      executor: 'constant-vus',
      vus: 6,
      duration: '45s',
      gracefulStop: '10s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500', 'med<50'],
    checks: ['rate>0.99'],
  },
};

export default function () {
  // One simulated client IP per iteration (trusted XFF from loopback):
  // ~6 requests per IP, far below the 30 req/min per-IP rate limit.
  const ip = `10.${__VU % 250}.${Math.floor(__ITER / 250) % 250}.${__ITER % 250}`;
  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Forwarded-For': ip,
    },
  };
  const code = `LOAD${100 + (__VU % 100)}`; // per-VU sync code, matches ^[A-Za-z0-9]{6,8}$
  const now = Math.floor(Date.now() / 1000);

  // Valid GET (possibly empty profile).
  let res = http.get(`${BASE}/api/sync/${code}`, params);
  check(res, { 'GET valid code -> 200': (r) => r.status === 200 });

  // Valid POST: lastVisit + one alert.
  res = http.post(
    `${BASE}/api/sync/${code}`,
    JSON.stringify({
      lastVisit: now,
      alerts: [
        { id: `a${__VU}`, keyword: 'drill', matchType: 'anyWord', createdAt: now },
      ],
    }),
    params,
  );
  check(res, {
    'POST valid -> 200': (r) => r.status === 200,
    'POST merges lastVisit monotonically': (r) =>
      r.status === 200 && r.json('lastVisit') >= now,
  });

  // Valid GET after write: alert must be visible.
  res = http.get(`${BASE}/api/sync/${code}`, params);
  check(res, {
    'GET after POST -> 200 with alert': (r) =>
      r.status === 200 && r.json('alerts').length >= 1,
  });

  // Invalid sync code -> 400.
  res = http.get(`${BASE}/api/sync/bad_code!`, params);
  check(res, { 'GET invalid code -> 400': (r) => r.status === 400 });

  // Invalid payload (boolean lastVisit is rejected per contract) -> 400.
  res = http.post(`${BASE}/api/sync/${code}`, JSON.stringify({ lastVisit: true }), params);
  check(res, { 'POST boolean lastVisit -> 400': (r) => r.status === 400 });

  // Oversized body (> 10 KB) -> 413, every 10th iteration.
  if (__ITER % 10 === 0) {
    res = http.post(`${BASE}/api/sync/${code}`, 'x'.repeat(11 * 1024), params);
    check(res, { 'POST oversized body -> 413': (r) => r.status === 413 });
  }

  sleep(0.5);
}
