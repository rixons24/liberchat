# LiberChat

Anonymous, location-based post-and-DM platform with ephemeral (view-once)
media, built with safety/moderation infrastructure as a first-class
concern rather than an afterthought.

## Structure

```
app/            FastAPI backend — auth, posts, DM relay, media pipeline,
                reports, moderation, admin auth
alembic/        Database migrations (Postgres via SQLAlchemy)
scripts/        Ops scripts — create_admin.py bootstraps the first
                moderator account (deliberately not a public API endpoint)
frontend/       Working PWA prototype (vanilla JS, single-file app shell)
                — wired to the real backend for auth/posts, DM/media
                still run on local mock state pending websocket+upload
                wiring in the UI
web/            Early Next.js/Tailwind component scaffolding (reference
                only — frontend/ is the actively-developed client)
docker-compose.yml, Dockerfile   Local dev / deploy setup
```

## Local setup

```bash
cp .env.example .env   # fill in real values before anything but local dev
docker compose up --build
```

This brings up Postgres, Redis, and the API on :8000. Then, separately:

```bash
docker compose exec api alembic upgrade head
docker compose exec api python scripts/create_admin.py <username>
```

Serve `frontend/index.html` from any static host (must be http/https, not
`file://`, for the service worker to register) and point `API_BASE` in its
`<script>` block at your running backend.

## Status / what's real vs. stubbed

**Fully implemented and tested against a live Postgres/Redis/S3-compatible
backend:**
- Signup (phone OTP + self-attested DOB, 18+ enforced), login, JWT auth
- Posts: create, feed, soft-delete
- Reports: filing, Tier 1 auto-suspension, mandatory-audit-note moderator
  actions, permanent ban + re-registration blocking
- Media: upload → synchronous moderation-scan-before-availability →
  session-based view-once delivery → verified deletion from storage
- DM relay: real-time WebSocket, E2EE ciphertext-only (server never sees
  plaintext)
- Admin auth: fully separate credential system from consumer accounts
  (separate table, separate JWT token type, no public registration route)

**Stubbed, needs real credentials before launch:**
- `SAFER_API_KEY` — Thorn Safer (CSAM image/video scanning) not yet wired
  to a real account
- NCMEC CyberTipline reporting — routes to a placeholder compliance alert
  (`print()`) until the app is registered as a reporting entity at
  report.cybertip.org
- SMS provider (Twilio / Africa's Talking) — OTPs currently land in Redis
  only, no real SMS is sent
- R2/S3 credentials — currently dev-tested against a local `moto` mock

**Not yet built:**
- Frontend wiring for DM/media (UI still mocked; backend endpoints exist
  and are tested)
- Legal review of Terms of Service / Community Guidelines
- Production-grade rate limiting, logging, monitoring
