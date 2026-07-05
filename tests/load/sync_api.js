// k6 placeholder targeting the sync API (T13 extends this).
// `make test-load` only runs it when the server is reachable; otherwise it skips.
import http from 'k6/http';
import { check } from 'k6';

const BASE = __ENV.SYNC_API_URL || 'http://localhost:8080';

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const res = http.get(`${BASE}/health`);
  check(res, { 'sync API health is 200': (r) => r.status === 200 });
}
