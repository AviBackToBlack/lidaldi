# LidAldi Sync API Contract

Frozen contract between `offers_processing/sync_server.py` and the frontend
(T5/T6 implement the client half against this document). Fixes Bug #2/N1
(the lastVisit self-race) together with the client rules below.

## Endpoints

Base path: `/api/sync/{code}` where `code` matches `^[A-Za-z0-9]{6,8}$`.
Invalid codes → `400`. Rate limit: 30 requests/minute per client IP → `429`.
Request bodies over 10 KB → `413`. CORS is restricted to
`config.SYNC_ALLOWED_ORIGIN`.

### GET /api/sync/{code}

Read-only. **Never modifies the profile** — in particular it never advances
`lastVisit` (read vs. advance are strictly split).

Response `200`:

```json
{
  "lastVisit": 1751234567890,
  "alerts":      [ {"id": "a1", "keyword": "drill", "matchType": "anyWord", "createdAt": 1751000000000} ],
  "tombstones":  [ {"id": "a0", "at": 1751000000.0} ],
  "alertMatches": { "a1": [ {"id": "743956", "at": 1751200000.0} ] }
}
```

- Unknown code (empty profile): `{"lastVisit": 0, "alerts": [], "tombstones": [], "alertMatches": {}}`.
- Alerts whose id appears in `tombstones` are filtered out of `alerts`.
- `alertMatches` (from T3) maps alert id → matched offers, where `id` is the
  stable product id carried by `offers.json` items (T2) and `at` is the unix
  time the alert push was delivered. Entries are GC'd after 30 days and
  capped at 100 per alert. **Read-only for clients**: only
  `send_notifications.py` writes it; anything a client POSTs under
  `alertMatches` (or `notified`) is ignored.

### POST /api/sync/{code}

Request body (all fields optional):

```json
{
  "lastVisit": 1751234567890,
  "alerts": [ {"id": "a1", "keyword": "drill", "matchType": "exact|allWords|anyWord", "createdAt": 0} ],
  "deletedAlertIds": [ {"id": "a0", "at": 1751000000.0} ],
  "pushSubscription": {"endpoint": "https://...", "keys": {"p256dh": "...", "auth": "..."}}
}
```

Semantics:

- `lastVisit`: merged as `max(stored, posted)`. **Monotonic — the server
  never regresses it.** Omitting it or posting `0` leaves the stored value
  untouched, so a read-only client can safely POST (e.g. to register a push
  subscription) without advancing anyone's lastVisit.
- `alerts`: merged by id with tombstone suppression; for the same id the
  newer `createdAt` wins. Omitting the field keeps stored alerts.
- `deletedAlertIds`: appended to tombstones (30-day TTL, cap 200);
  tombstoned ids never resurrect via later alert merges.
- `pushSubscription`: upserted by `endpoint` (cap 10, oldest dropped).
- Server-owned fields `notified` and `alertMatches` in the body are ignored.

Response `200`: `{"lastVisit": <merged>, "alerts": [...], "tombstones": [...]}`.

## Client rules (fix for Bug #2 / N1)

The legacy client raced against itself: on load it POSTed `lastVisit=now`,
then GETed and adopted the server value — which it had just advanced — so
the "new since your last visit" window collapsed to empty on every synced
device. Correct clients MUST follow these rules:

1. **Read at boot, remember the boot value.** On startup, GET the profile
   and keep `bootLastVisit` = the server's `lastVisit` (or the local stored
   value if newer). "New" = `offer.first_seen > bootLastVisit` for the whole
   session.
2. **Adopt from the server only if it is older than the boot value is
   newer.** Concretely: after any GET, the client may lower nothing and
   adopts a server `lastVisit` **only if the client has not yet advanced
   this session and the server value is newer than what it read at boot**
   (another device visited later); it must never let a value it advanced
   itself shrink the current session's "new" window.
3. **Advance once per session.** After rendering with `bootLastVisit`,
   POST `lastVisit = sessionStart` exactly once per session
   (sessionStorage-guarded). Never POST `now` before the first GET.
4. Reads are GETs; a POST that isn't meant to advance lastVisit must omit
   the field or send `0`.

Sequence that must work (locked by integration test):

```
device A: GET            -> lastVisit = L0   (render "new" vs L0)
device A: POST {lastVisit: now}              (once, after render)
device A: GET            -> lastVisit = now  (ignored: A already advanced)
device B: GET            -> lastVisit = now  (B's next session renders vs now)
```

## Profile store schema (server-side, additive-only)

```json
{
  "lastVisit": 0,
  "alerts": [],
  "tombstones": [],
  "pushSubscriptions": [],
  "notified":     [ {"alertId": "a1", "id": "743956", "endpoint": "<sha256[:16]>", "at": 0} ],
  "alertMatches": { "a1": [ {"id": "743956", "at": 0} ] }
}
```

`notified` and `alertMatches` are written only by `send_notifications.py`
(per-endpoint delivery ledger, see T3).
