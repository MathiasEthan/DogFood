# Community Layer (T3): Voting, Comments & Integrity

**Scope:** configurable community voting, comments, hidden results during voting, randomized project ordering, rate limiting, duplicate detection and audit trails.
**Code:** `backend/events/community.py` (views and rules), `backend/events/models.py` (`CommunityVote`, `CommunityComment`, `VoteAuditLog`), `frontend/app/events/[id]/voting/page.tsx`, `frontend/components/community-voting-panel.tsx`.
**Tests:** `backend/events/test_voting.py` (every rule below has at least one test).

---

## 1. Voting model

We use **approval voting with a per-user quota**. Each eligible user may back up to *N* different projects with one vote each (organizer-configurable, `0` = unlimited), and can withdraw a vote to move it elsewhere while voting is open.

Why this and not "one vote each" or quadratic voting:

| Mechanism | Problem at hackathon scale | Decision |
| :--- | :--- | :--- |
| Single vote per user | Voters back the favourite everyone has already heard of, and good niche projects score 0 | Supported (`votes_per_user = 1`), not the default |
| Unlimited approval | "Vote for everything" makes the tally meaningless | Supported (`0`), not the default |
| Quadratic voting | Needs a credit budget people understand in seconds; hard to explain to walk-up voters | Rejected |
| **Approval, quota N (default 3)** | Simple to explain; spreads support; one voter can add at most N points in total | **Adopted** |

### Configurable rules (per event)

| Field | Default | Effect |
| :--- | :--- | :--- |
| `community_voting_start` / `community_voting_end` | unset | Voting is open only inside this window. Both are required together, and end must be after start. |
| `votes_per_user` | `3` | Quota per user per event. |
| `voting_eligibility` | `any` | `any` = any signed-in user; `registered` = only users on a team in this event. |
| `allow_self_vote` | `false` | Team members cannot vote for their own project. |
| `show_community_voting_results` | `false` | Opt in to live counts during voting. |
| `comments_enabled` | `true` | Turns comment posting on or off. |

Judges of an event can never vote in its community round, because their influence belongs to the judged track (T2).

## 2. Hidden results during voting

While voting is open, vote counts are **not returned by the API**, so they cannot be read from the page source either:

- Gallery rows return `community_vote_count: null`.
- `GET /community-results/` returns `403 {results_hidden: true, reveal_at}`.
- Only the organizer of this event and platform admins see live counts. Having the organizer role for another event does **not** unlock them.
- Counts become public automatically when `community_voting_end` passes, or immediately if the organizer opts in.

Rationale: visible tallies cause bandwagon voting, where early leaders gather more votes simply for leading.

## 3. Randomized project ordering

While voting is open, the gallery is shuffled **per viewer**:

```
seed  = SHA256(SECRET_KEY : event_id : viewer_identity)      # user id, or IP+UA when anonymous
order = sort(projects, key = SHA256(seed : project_id))
```

- **Stable** for a given viewer: refreshing doesn't reshuffle, so people can find their place again.
- **Different across viewers**: no project is always first, so position bias spreads evenly over the field.
- **Not guessable or manipulable**: the seed includes the server secret, so a team can't compute or influence where it appears.
- Search results are shuffled too. When voting is closed, the gallery falls back to most-recently-updated order. The `X-Gallery-Ordering: random|recent` response header shows which ordering was used.

Team names are also hidden on the voting page ("Anonymous Team") to reduce popularity bias.

## 4. Duplicate detection

| Layer | Mechanism |
| :--- | :--- |
| Database | `unique_together(submission, voter)` on `CommunityVote`, the final guarantee even under concurrent requests. |
| API | A second `POST` returns **409 Conflict**; the attempt is written to the audit log as `VOTE_REJECTED {reason: duplicate}`. |
| Race condition | Two simultaneous requests hitting the unique constraint are caught (`IntegrityError` → 409, `duplicate_race`). The quota check runs inside a transaction that locks the voter's row, so the quota can't be raced either. |
| Comments | The same author posting the same text (case-insensitive) on the same project within 10 minutes → 409. |

### Sock-puppet / abuse heuristics

Suspicious votes are **flagged, not silently blocked**. False positives stay with a human, and the organizer can void a flagged vote with a reason (`VOTE_VOIDED`, excluded from tallies):

| Flag | Rule |
| :--- | :--- |
| `SHARED_IP` | ≥ 3 distinct accounts from one IP voting for the same project within 24 h |
| `NEW_ACCOUNT` | Account created *after voting opened* and voting within its first hour |
| `BURST` | ≥ 5 votes by one user within 60 s |

Limitation: in Docker every browser request may appear to come from the bridge gateway IP, so `SHARED_IP` is only meaningful behind a real proxy with `TRUST_X_FORWARDED_FOR=True`. `X-Forwarded-For` is ignored by default because clients can spoof it.

## 5. Rate limiting

DRF `ScopedRateThrottle`, keyed per user (per IP for anonymous callers), with counters in the **database cache** so all gunicorn workers share them:

| Scope | Default | Env override |
| :--- | :--- | :--- |
| `community_votes` (cast / withdraw) | 30/min | `THROTTLE_COMMUNITY_VOTES` |
| `community_comments` (post) | 10/min | `THROTTLE_COMMUNITY_COMMENTS` |
| `auth` (login / register) | 20/min | `THROTTLE_AUTH` |

Requests over the limit get `429 Too Many Requests` with a `Retry-After` header.

## 6. Audit trail

Every community action is appended to `VoteAuditLog`: `VOTED`, `UNVOTED`, `VOTE_REJECTED`, `VOTE_VOIDED`, `COMMENTED`, `COMMENT_EDITED`, `COMMENT_REMOVED`, `COMMENT_REJECTED`, and `SETTINGS_CHANGED` (with a from→to diff of every voting rule).

**Tamper-evident, hash-chained, append-only:**

```
entry_hash = SHA256(prev_hash || canonical_json(event, submission, user, action, metadata, flagged, ip, timestamp))
```

- The model refuses `save()` on an existing row and refuses `delete()` (`ImmutableAuditError`).
- Each event has its own chain. `GET /admin/community-audit/verify/` recomputes it and returns the first entry whose content or link no longer matches. Editing any row directly in the database breaks every hash after it.
- Deleting a project keeps its audit rows (`on_delete=SET_NULL`).
- Only the event's organizer and admins can read the trail or export it as CSV.

## 7. Comments

- Anyone can read comments. Signed-in users can post (1–2000 characters, trimmed).
- Authors can edit their own comments (marked "edited"). Authors can remove their own comments, and the event's organizer can remove any comment (soft delete, `removed_by` recorded, audited).
- Comments are only accepted on submitted (non-draft) projects of the same event, and drafts return 404.

## 8. Cross-event isolation

Every endpoint loads the submission **through its event** (`pk=sub, team__event=event, is_draft=False`). Addressing another event's project through the wrong event URL returns 404, and quotas are counted per event.
