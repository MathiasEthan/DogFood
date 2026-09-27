# Containerized Offline Hackathon Platform

---

##  Startup & Execution Options

You can run the platform in three ways depending on your development workflow:

### Option 1: Full Docker Compose (Containerized Production Mode)

Use this to run PostgreSQL, Django, and Next.js entirely inside Docker:

- **First Run / After Dependency Updates** (Builds images from source):
  ```bash
  docker compose up --build
  ```
- **Subsequent Runs** (Instant start without rebuilding):
  ```bash
  docker compose up -d     # Starts all containers in the background
  docker compose stop      # Pauses all containers
  docker compose start     # Instantly resumes all containers (~1 second)
  docker compose down      # Stops and removes containers
  ```

---

### Option 2: Native Local Development (Fastest, with Hot-Reloading)

Run both services directly on your host machine for instant Fast Refresh and code reload without Docker:

1. **Terminal 1: Start Django Backend**
   ```bash
   cd backend
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py createcachetable   # rate-limit counters live in the DB cache
   python manage.py runserver 8000
   ```
   *(Note: Django automatically falls back to local SQLite if PostgreSQL is not running).*

2. **Terminal 2: Start Next.js Frontend**
   ```bash
   cd frontend
   npm run dev
   ```

---

### Option 3: Hybrid Setup (PostgreSQL in Docker, Apps on Host)

If you want PostgreSQL without installing it directly on your machine:

1. **Start only the PostgreSQL container**:
   ```bash
   docker compose up db -d
   ```
2. **Run Django and Next.js locally** (using the commands in Option 2).

---

### Access Endpoints (All Modes)

Once running:
- **Frontend Web UI**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Django Admin**: [http://localhost:8000/admin/](http://localhost:8000/admin/)

---

##  Default Admin Credentials

On initial startup, `backend/entrypoint.sh` automatically seeds the default administrator if not present:

- **Username**: `admin`
- **Password**: `AdminPassword123!`
- **Role**: `admin`

*(You can customize these via `.env`)*

---

## 📡 REST API Reference

### Authentication
| Endpoint | Method | Permission | Description |
|---|---|---|---|
| `/api/auth/register/` | POST | Public | Register new account (`participant` or `organizer` only). Sets HttpOnly cookies. |
| `/api/auth/login/` | POST | Public | Authenticate with username/email and password. Sets HttpOnly cookies. |
| `/api/auth/refresh/` | POST | Public | Rotates access token using HttpOnly refresh cookie. |
| `/api/auth/logout/` | POST | Public | Invalidates token and clears HttpOnly cookies. |
| `/api/auth/me/` | GET | Authenticated | Returns authenticated user profile and assigned role. |
| `/api/auth/users/` | GET | Admin Only | Lists all registered platform users. |
| `/api/auth/users/<id>/appoint-judge/` | POST | Admin Only | Appoints the specified user as a Judge. |

### Events & Teams
| Endpoint | Method | Permission | Description |
|---|---|---|---|
| `/api/events/` | GET | Public | List all active hackathon events. |
| `/api/events/` | POST | Organizer / Admin | Create a new hackathon event (supports banner upload). |
| `/api/events/<id>/` | GET | Public | Retrieve full event details + user's current team. |
| `/api/events/<id>/teams/create/` | POST | Authenticated | Create a team for this event and receive a shareable team code. |
| `/api/events/<id>/teams/join/` | POST | Authenticated | Join a team in this event using an 8-character team code. |
| `/api/events/<id>/teams/leave/` | POST | Authenticated | Leave current team for this event. |

### Project Submissions
| Endpoint | Method | Permission | Description |
|---|---|---|---|
| `/api/events/<id>/my-submission/` | GET | Authenticated (Team Member) | Retrieve team's project submission. |
| `/api/events/<id>/submit/` | POST | Authenticated (Team Leader) | Create or update project submission before event deadline (multipart form). |
| `/api/events/<id>/submissions/` | GET | This event's organizer / judges / admin | Submissions roster (judges never see drafts). |
| `/api/events/<id>/gallery/?q=&track=` | GET | Public | Searchable gallery of non-draft projects. Randomized per viewer while voting is open (`X-Gallery-Ordering` header). |

### Judging (T2) — see [JUDGING.md](JUDGING.md)
"Organizer" below always means the organizer **of that event** (or a platform admin).

| Endpoint | Method | Permission | Description |
|---|---|---|---|
| `/api/events/<id>/rubrics/` | GET / POST | Public / Organizer | Weighted rubrics (locked once evaluations exist). |
| `/api/events/<id>/submissions/<sid>/evaluate/` | GET / POST | Event judge (assigned) | Score every rubric; COI, drafts and published results are rejected. GET starts the server-side dwell clock. |
| `/api/events/<id>/admin/assign-judges/` | POST | Organizer | COI-free, load-balanced assignment `{k_per_project}`; reports `deficits`. |
| `/api/events/<id>/admin/judging-progress/` | GET | Organizer | Judge telemetry (μ, σ, flatline), project saturation matrix. |
| `/api/events/<id>/leaderboard/` | GET | Organizer; everyone after publish | Empirical-Bayes normalized standings; public view anonymizes judges. |
| `/api/events/<id>/admin/publish-results/` | POST | Organizer | `{published: true/false}`; publishing locks scoring. |
| `/api/events/<id>/admin/export/{submissions,assignments,rubric-breakdown,feedback,evaluation-audit,leaderboard}-csv/` | GET | Organizer | Streaming CSV exports for every stage. |

### Community (T3) — see [COMMUNITY.md](COMMUNITY.md)
| Endpoint | Method | Permission | Description |
|---|---|---|---|
| `/api/events/<id>/voting/` | GET | Public | Voting window, rules, and the caller's quota / ballot / eligibility. |
| `/api/events/<id>/submissions/<sid>/vote/` | POST / DELETE | Authenticated, eligible | Cast (`201`, `409` duplicate) or withdraw a vote while voting is open. Rate limited. |
| `/api/events/<id>/community-results/` | GET | Public after voting closes | Vote ranking; `403 results_hidden` during voting unless the organizer opts in. |
| `/api/events/<id>/submissions/<sid>/comments/` | GET / POST | Public / Authenticated | Comments (duplicate + rate limited). |
| `/api/events/<id>/comments/<cid>/` | PATCH / DELETE | Author / author or organizer | Edit own; remove own or moderate. |
| `/api/events/<id>/admin/community-votes/?flagged=1` | GET | Organizer | Individual votes with abuse flags. |
| `/api/events/<id>/admin/community-votes/<vid>/void/` | POST | Organizer | Void a vote with a reason (excluded from tallies). |
| `/api/events/<id>/admin/community-audit/` | GET | Organizer | Hash-chained audit trail (`?flagged=1`, `?action=`). |
| `/api/events/<id>/admin/community-audit/verify/` | GET | Organizer | Recompute the hash chain; reports the first tampered entry. |
| `/api/events/<id>/admin/export/{community-votes,community-audit}-csv/` | GET | Organizer | CSV exports. |

Voting rules (window, votes per user, eligibility, self-voting, live counts, comments) are set with `PATCH /api/events/admin/events/<id>/` or the **Community Voting & Results** panel on the event page; every change is written to the audit trail.

### Webhooks & API Keys (T4)
| Endpoint | Method | Permission | Description |
|---|---|---|---|
| `/api/events/<id>/webhooks/` | GET / POST | Organizer | List an event's webhooks; register a new one (`target_url`, optional `subscribed_events`). The signing secret is only ever returned in full on this `POST`. |
| `/api/events/<id>/webhooks/<wid>/` | PATCH / DELETE | Organizer | Update `target_url` / `is_active` / `subscribed_events`, or remove the webhook. |
| `/api/events/<id>/webhooks/<wid>/deliveries/` | GET | Organizer | Delivery log (status, HTTP response, attempt count) for one webhook. |
| `/api/events/<id>/webhooks/<wid>/deliveries/<did>/redeliver/` | POST | Organizer | Manually retry one previously failed delivery. |
| `/api/auth/api-keys/` | GET / POST | Authenticated | List your own API keys (masked); mint a new one. The raw key is only ever returned in full on this `POST`. |
| `/api/auth/api-keys/<kid>/` | PATCH / DELETE | Owner | Pause (`is_active`) or permanently revoke a key. |

Webhooks fire a signed `POST` for `team.created`, `submission.created`, `submission.updated`, `evaluation.submitted`, `results.published`, `vote.cast` and `comment.posted`. Every delivery includes an `X-DogFood-Signature: sha256=<hmac>` header — an HMAC-SHA256 of the exact request body, keyed by that endpoint's own secret — so the receiver can verify it actually came from this platform. There's no background worker in this stack, so delivery is synchronous and best-effort; failures are logged and can be redelivered by hand.

API keys let an external tool call this REST API without a browser session: send `Authorization: ApiKey <key>` instead of relying on the login cookies. A key grants exactly the same permissions its owner already has everywhere else in the app — an organizer's key manages their events, nothing more.

---

## 🧪 Local Testing & Verification

To run backend tests locally:

```bash
cd backend
python manage.py test
```

To run frontend checks:

```bash
cd frontend
npm run typecheck
npm run build
```

## Notes
- If `DB_HOST` isn't set, the backend uses SQLite instead of PostgreSQL.
- Rate limits are configurable via `THROTTLE_COMMUNITY_VOTES`, `THROTTLE_COMMUNITY_COMMENTS` and `THROTTLE_AUTH` (defaults `30/min`, `10/min`, `20/min`).
- Only set `TRUST_X_FORWARDED_FOR=True` when running behind a trusted reverse proxy.
