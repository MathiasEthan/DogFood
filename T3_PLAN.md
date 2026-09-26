# T3 - Public Feature Plan: Community Voting

## 1. Database Model Updates (`backend/events/models.py`)

**Update `Event` Model:**
- Add `community_voting_start` (DateTimeField, optional): Start time for community voting.
- Add `community_voting_end` (DateTimeField, optional): End time for community voting.
- Add `show_community_voting_results` (BooleanField, default=False): Allows admins to keep results hidden from the public during the active voting period to prevent bandwagon effects.

**New `CommunityVote` Model:**
- `submission`: ForeignKey to `ProjectSubmission`
- `voter`: ForeignKey to User
- `created_at`: Timestamp
- **Duplicate Detection**: Enforced via a `unique_together = ('submission', 'voter')` constraint, preventing a user from voting on the same submission more than once.

**New `CommunityComment` Model:**
- `submission`: ForeignKey to `ProjectSubmission`
- `author`: ForeignKey to User
- `text`: TextField for comment content
- `created_at`: Timestamp

**New `VoteAuditLog` Model (Audit Trail):**
- `submission`: ForeignKey to `ProjectSubmission`
- `voter`: ForeignKey to User
- `action`: E.g., 'VOTED', 'VOTE_REMOVED'
- `ip_address`: IP Address of the voter
- `user_agent`: Browser/Client info of the voter
- `timestamp`: Timestamp of the action
- Ensures every voting action is recorded in an immutable ledger for defense against suspected tampering.

## 2. API Endpoints & Logic (`backend/events/views.py`)

- **Voting Endpoint** (`POST /events/<id>/submissions/<id>/vote/`):
  - Validates that the current time falls within the event's `community_voting_start` and `community_voting_end`.
  - Creates `CommunityVote` and writes an entry to `VoteAuditLog`.
  - Can be toggled to delete the vote (unvote).
- **Comments Endpoint** (`GET/POST /events/<id>/submissions/<id>/comments/`):
  - Standard CRUD for comments on submissions.
- **Randomized Project Ordering**:
  - Update the submission list endpoint to return projects in a randomized order (e.g. `order_by('?')` or using a random seed based on session/day) when community voting is active, to give all projects an equal chance of being seen.
- **Rate Limiting**:
  - Implement DRF Throttling (e.g., `UserRateThrottle`) on voting and commenting endpoints to prevent spam or bot-driven requests (e.g., max 10 votes/comments per minute).

## 3. Serializers & Result Hiding (`backend/events/serializers.py`)
- Update `ProjectSubmission` serializer to include `vote_count` and `comments`.
- **Hidden Results**: If `show_community_voting_results` is `False` and voting is ongoing, the `vote_count` will be explicitly excluded or returned as `null` for regular users, and only visible to admins or after voting ends.

Let me know if this plan covers all your requirements or if you'd like to adjust any details before I proceed with the implementation!
