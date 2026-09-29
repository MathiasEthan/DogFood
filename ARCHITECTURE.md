# System Architecture & Technical Specification (ARCHITECTURE.md)

**Platform:** DogFood Hackathon Platform  
**Target Standard:** Production-Grade Hackathon Infrastructure, Cryptographic Integrity, and Platform Extensibility  
**Core Principles:** Strict Role Isolation, Mathematically Defensible Evaluation, Zero Organizer Lock-In, and Immutable Auditability

---

## 1. High-Level System Architecture

DogFood is designed as a decoupled, multi-tier web application built for high concurrency, zero external runtime CDN dependencies, and verifiable integrity throughout every stage of a hackathon lifecycle.

```mermaid
graph TD
    subgraph Clients["Clients & Consumers"]
        Browser["Modern Browser<br/>(Organizer / Judge / Participant)"]
        EmbedHost["Third-Party Web Host<br/>(iframe Widget Embed)"]
        ScriptConsumer["External Automation / CI<br/>(REST API + API Key)"]
        WebhookReceiver["External Endpoint<br/>(Signed POST Listener)"]
    end

    subgraph Edge["Edge / Reverse Proxy Tier"]
        Nginx["Reverse Proxy / Ingress<br/>(Rate Limiting & Static Files)"]
    end

    subgraph AppTier["Application Tier"]
        NextFrontend["Frontend Service<br/>(Next.js 16 + React 19 + Turbopack)"]
        DjangoBackend["Backend API Service<br/>(Django 5 + Django REST Framework)"]
    end

    subgraph CoreEngines["Core Backend Engines"]
        AuthEngine["Auth & RBAC Engine<br/>(JWT Cookie + ApiKey)"]
        JudgingEngine["Judging & Integrity Engine<br/>(Empirical Bayes Normalization)"]
        MatchingEngine["Assignment Engine<br/>(Constrained Bipartite Min-Degree)"]
        AuditEngine["Audit Engine<br/>(Merkle-like Hash Chaining)"]
        CryptoEngine["Crypto Engine<br/>(Canonical HMAC-SHA256 Signatures)"]
        PortabilityEngine["Portability Engine<br/>(JSON Archive + CSV Parsing)"]
    end

    subgraph Persistence["Persistence Tier"]
        DB[(PostgreSQL 16 / SQLite Fallback<br/>ACID Relational Storage)]
        MediaStorage["Local Media Volume<br/>(/app/media/ & Banners)"]
    end

    Browser -->|HTTPS / WSS| Nginx
    EmbedHost -->|iframe / postMessage| NextFrontend
    ScriptConsumer -->|REST API with ApiKey| Nginx
    Nginx -->|SSR / Hydration| NextFrontend
    Nginx -->|API Reverse Proxy| DjangoBackend

    DjangoBackend --> AuthEngine
    DjangoBackend --> JudgingEngine
    DjangoBackend --> MatchingEngine
    DjangoBackend --> AuditEngine
    DjangoBackend --> CryptoEngine
    DjangoBackend --> PortabilityEngine

    AuthEngine --> DB
    JudgingEngine --> DB
    MatchingEngine --> DB
    AuditEngine --> DB
    CryptoEngine --> DB
    PortabilityEngine --> DB
    DjangoBackend --> MediaStorage

    CryptoEngine -.->|HMAC-SHA256 Delivery| WebhookReceiver
```

---

## 2. Authentication, Authorization & RBAC Architecture

DogFood implements a dual authentication scheme allowing seamless, secure browser sessions alongside high-throughput scriptable API access:

1. **Browser Authentication (Cookie-Based JWT):**
   - Employs `djangorestframework-simplejwt` using encrypted, HTTP-only, `SameSite=Lax` cookies for `access` and `refresh` tokens.
   - Prevents Cross-Site Scripting (XSS) credential extraction.
   - Automatic background sliding refresh prevents session dropouts during live evaluation sessions.
2. **Programmatic API Keys (`ApiKey`):**
   - External CI/CD scripts, automated ingest pipelines, and custom bots authenticate via `Authorization: ApiKey <raw_key>`.
   - The platform generates high-entropy random keys prefixed with `dfk_` (e.g., `dfk_abc123...`).
   - Only the SHA-256 hash of the key is stored in the database. A database dump cannot compromise active API keys.
3. **Role-Based Access Control (RBAC):**
   - Four distinct user roles: `participant`, `judge`, `organizer`, and `admin`.
   - Role isolation is strictly enforced at the database and API view levels. Judges cannot modify team records; participants cannot view uncompleted scorecards or audit logs.

```mermaid
sequenceDiagram
    autonumber
    actor Client as Browser Client
    actor Script as External Script
    participant Next as Next.js 16 Frontend
    participant API as Django REST Backend
    participant DB as Relational Database

    %% Browser Flow
    Note over Client,API: Browser Session Flow (JWT in HTTP-only Cookie)
    Client->>Next: POST /login (username, password)
    Next->>API: Forward credentials
    API->>DB: Verify bcrypt password hash
    DB-->>API: User authenticated (role verified)
    API-->>Next: Set-Cookie: access_token, refresh_token (HttpOnly, SameSite=Lax)
    Next-->>Client: 200 OK (Render Authenticated Shell)

    %% Script Flow
    Note over Script,API: Programmatic Flow (Hashed API Key Header)
    Script->>API: GET /api/events/1/admin/export/bulk-archive/<br/>Header: Authorization: ApiKey dfk_secret...
    API->>API: Extract prefix & compute SHA-256(raw_key)
    API->>DB: Query ApiKey by (prefix, key_hash) & verify user.role
    DB-->>API: Valid Organizer Key
    API-->>Script: 200 OK (Lossless JSON Archive)
```

---

## 3. Event State Lifecycle & Governance Machine

An event advances through distinct phases, enforcing strict business rules at each transition:

```mermaid
stateDiagram-v2
    [*] --> Draft : Organizer creates event

    state Draft {
        [*] --> Configuring
        Configuring --> RubricsDefined : Add weighted rubrics
        RubricsDefined --> TracksConfigured : Add tracks & prizes
    }

    Draft --> RegistrationOpen : Published by Organizer
    
    state RegistrationOpen {
        [*] --> TeamFormation
        TeamFormation --> MemberJoined : Join code verification
        MemberJoined --> TeamFull : Max team size enforced
    }

    RegistrationOpen --> HackingActive : start_date reached
    
    state HackingActive {
        [*] --> DraftingProject
        DraftingProject --> SubmittingProject : Leader submits details
        SubmittingProject --> SubmissionLocked : end_date deadline passes
    }

    HackingActive --> EvaluationPhase : end_date passed

    state EvaluationPhase {
        [*] --> BipartiteMatching : Algorithmic K-Assignment
        BipartiteMatching --> PeerEvaluation : Judges evaluate blind
        PeerEvaluation --> AnomalyAuditing : Real-time outlier flags
        BipartiteMatching --> CommunityVoting : Parallel voting window (T3)
    }

    EvaluationPhase --> ResultsPublished : Organizer signs off & publishes
    
    state ResultsPublished {
        [*] --> LeaderboardUnlocked : Normalization visible
        LeaderboardUnlocked --> CertificatesIssued : Vector SVGs generated
        CertificatesIssued --> JudgeRecordsSigned : HMAC-SHA256 finalized
    }

    ResultsPublished --> [*] : Event Archived / Exported
```

---

## 4. Core Subsystem Deep Dives

### 4.1 Submission Engine & Deadline Gatekeeper
- Submissions are bound to a team via a strict one-to-one relationship (`ProjectSubmission.team`).
- Only the registered team leader (`team.leader_id == user.id`) can create or modify submissions.
- **Deadline Enforcement:** If `event.end_date` has passed, all write, update, and draft deletion attempts fail immediately with `HTTP 403 Forbidden`. The deadline is enforced strictly server-side based on timezone-aware UTC timestamps.

### 4.2 Constrained Bipartite Assignment & Anti-COI Engine
To eliminate judge fatigue and bias, the platform employs a constrained greedy min-degree bipartite matching algorithm:
- Target: Each project receives at least $K$ independent reviews (default $K=3$).
- **Conflict of Interest (COI) Filter:** A judge is strictly disqualified from receiving an assignment if:
  1. The judge is a member of the project's team.
  2. The judge was previously registered to that team.
- **Greedy Min-Degree Allocation:** Sorts projects by current review deficit ascending, selecting eligible judges with the lowest current workload to prevent variance distortion.

### 4.3 Empirical Bayes Normalization Pipeline
When evaluations are sparse, raw score averaging creates structural bias (harsh vs. lenient judges). DogFood processes all evaluations through an **Empirical Bayes Regularized Z-Score Engine**:
- Computes global prior mean $\mu_0$ and prior variance $\sigma_0^2$.
- Applies shrinkage factor ($m=3.0$) to pull individual judge distributions toward the global prior.
- Computes standardized Z-scores $z_{j,i} = \frac{s_{j,i} - \hat{\mu}_j}{\hat{\sigma}_j}$.
- Rescales normalized marks back onto a calibrated $[1.0, 10.0]$ scale and calculates the standard error of the mean ($SE_i$).

```mermaid
flowchart TD
    RawScores["Raw Rubric Marks from Judge<br/>(Rubrics 1..M with Weights W_k)"] --> WeightedSum["Weighted Evaluation Total<br/>s_{j,i} = sum(w_k * score_k)"]
    WeightedSum --> GlobalPrior["Global Event Baseline Calculation<br/>Prior Mean mu_0, Prior Variance sigma_0^2"]
    
    GlobalPrior --> BayesShrinkage["Empirical Bayes Parameter Shrinkage<br/>mu_j_hat = (n_j * mean_j + m * mu_0) / (n_j + m)<br/>sigma_j_hat computed with m=3.0"]
    
    BayesShrinkage --> ZScore["Compute Standard Score<br/>z_{j,i} = (s_{j,i} - mu_j_hat) / sigma_j_hat"]
    
    ZScore --> Rescale["Clamped Rescaling to [1.0, 10.0]<br/>S_norm = clamp(mu_0 + z * sigma_0, 1.0, 10.0)"]
    
    Rescale --> Aggregation["Project Standings Aggregate<br/>Final Score = mean(S_norm)<br/>Standard Error SE = std_dev / sqrt(K)"]
```

### 4.4 Merkle-Style Chained Community Vote Audit Log (T3)
To ensure community votes cannot be repudiated, altered, or injected by malicious actors or direct database tampering:
- Every voting action (`VOTE_CAST`, `VOTE_WITHDRAWN`, `VOTE_VOIDED`) appends an immutable entry to `VoteAuditLog`.
- Each entry contains an SHA-256 `entry_hash` derived from:
  $$\text{entry\_hash} = \text{SHA256}(\text{prev\_hash} \,||\, \text{timestamp} \,||\, \text{action} \,||\, \text{submission\_id} \,||\, \text{user\_id} \,||\, \text{ip\_address})$$
- The entire chain can be audited in $O(N)$ time via `/api/events/<id>/admin/community-audit/verify/`. If a single row is modified or deleted in the database, the hash chain breaks instantly at that row.

### 4.5 Digital Signatures & Public Verification Engine (T4 Stretch)
DogFood provides cryptographic proof of achievement and participation:
- **Canonical Serialization:** Formats JSON payloads deterministically (sorted keys, compact whitespace) via `backend/events/signing.py`.
- **HMAC-SHA256 Signatures:** Signs payloads with server secret keys to prevent tampering.
- **Vector SVG Generation:** Standalone SVG certificates generated server-side with embedded verification hashes, ornate guilloche vectors, and gold seals.
- **Judge Participation Records:** Appointed judges receive a signed record containing review count, rubric marks, average score given, and activity timestamps, publicly verifiable at `/verify/judge/<record_id>/`.

```mermaid
sequenceDiagram
    autonumber
    actor Organizer
    participant API as Django Backend
    participant Signer as Signing Engine (signing.py)
    participant DB as Database
    actor Public as Public Verifier / Third Party

    Organizer->>API: POST /api/events/1/admin/certificates/generate/
    API->>API: Calculate official winners & judge activity
    API->>Signer: Canonical JSON(payload)
    Signer->>Signer: Compute SHA-256 Digest
    Signer->>Signer: Compute HMAC-SHA256(Digest, SECRET_KEY)
    Signer-->>API: Verification Code & Signature Hash
    API->>DB: Save Certificate & JudgeParticipationRecord
    API-->>Organizer: 201 Created (Certificates & Records generated)

    Note over Public,API: Public Unauthenticated Verification
    Public->>API: GET /api/certificates/CERT-XXXX-XXXX/
    API->>Signer: Verify stored signature against canonical fields
    Signer-->>API: Valid & Untampered
    API-->>Public: 200 OK { is_valid: true, recipient: "Alice", award: "1st Place" }
```

### 4.6 Embeddable Gallery Widget & Cross-Origin Protocol (T4 Stretch)
- **Standalone Embed Endpoint:** [`/embed/events/<id>/gallery/`](frontend/app/embed/events/[id]/gallery/page.tsx) renders a headless, responsive project gallery free from site navigation or cookie dependencies.
- **Auto-Resizing Protocol:** Utilizes window `postMessage` communication to eliminate scrollbars on the host site:
  ```typescript
  window.parent.postMessage({
    type: 'dogfood:embed:resize',
    height: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)
  }, '*');
  ```
- **Real-Time Client Filtering:** Features instant text search across titles, taglines, teams, and tech stacks, combined with dynamic track selector pills.

### 4.7 Zero-Lock-In Portability Engine (T4 Stretch)
To ensure organizers have full data sovereignty:
- **Lossless Event Export (`export_event_archive`):** Generates a comprehensive JSON archive containing all event configuration, rubrics, teams, submissions, evaluations, votes, comments, and certificates, sealed with an SHA-256 checksum.
- **Event Reconstitution (`import_event_archive`):** Recreates an entire event structure on any DogFood instance from the JSON bundle, safely remapping user accounts and resolving code collisions.
- **Bulk CSV Importer (`import_teams_csv`):** Ingests bulk team and participant lists from CSV (`team_name,username,email,is_leader`), automatically creating users and assigning leadership roles in atomic transactions.

---

## 5. Webhook Dispatch Architecture

DogFood provides real-time event dispatching covering every action reachable via the UI:

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Organizer
    participant API as Django REST Framework
    participant Dispatcher as Webhook Dispatcher
    participant DB as Database
    actor HookServer as External Consumer Server

    User->>API: Action (e.g. Join Team, Submit Evaluation, Issue Certs)
    API->>DB: Commit database transaction
    API->>Dispatcher: dispatch_webhook(event, event_type, payload)
    Dispatcher->>DB: Query active WebhookEndpoint for event & event_type
    loop For Each Endpoint
        Dispatcher->>Dispatcher: Compute HMAC-SHA256(payload, endpoint.secret)
        Dispatcher->>HookServer: POST target_url<br/>Header: X-DogFood-Signature: sha256=...<br/>Header: X-DogFood-Event: event_type
        HookServer-->>Dispatcher: HTTP Response (e.g. 200 OK)
        Dispatcher->>DB: Record WebhookDelivery log (status, status_code, timestamp)
    end
    API-->>User: HTTP Response
```

---

## 6. Directory Structure & Technology Stack

```
DogFood/
├── backend/
│   ├── config/             # Django settings, WSGI, ASGI, and root routing
│   ├── users/              # Custom User model, API keys, authentication endpoints
│   ├── events/             # Core event logic, submissions, teams, judging, webhooks
│   │   ├── models.py       # 19 relational & cryptographic models
│   │   ├── views.py        # REST viewsets & API endpoints
│   │   ├── community.py    # T3 community voting, comments & audit log verification
│   │   ├── certificates.py # T4 vector SVG generator & certificate issuance
│   │   ├── signing.py      # Deterministic canonical serialization & HMAC engine
│   │   ├── portability.py  # Bulk JSON archive & CSV ingestion engine
│   │   └── tests.py        # 98 automated unit and integration tests
│   └── manage.py
├── frontend/
│   ├── app/                # Next.js 16 App Router (Turbopack)
│   │   ├── events/         # Event exploration, management, and project submission
│   │   ├── embed/          # T4 headless embeddable gallery widget (/embed/events/[id]/gallery)
│   │   ├── certificates/   # T4 public certificate verification (/certificates/[code])
│   │   └── verify/         # T4 public judge credential verification (/verify/judge/[record_id])
│   ├── components/         # Reusable UI components, modals, and admin panels
│   └── lib/api.ts          # Typed REST API client & error handling
├── docker-compose.yml      # Orchestration for multi-container deployment
├── Dockerfile.backend      # Python 3.12+ Django image
└── Dockerfile.frontend     # Next.js standalone container image
```

---

## 7. Security Invariants & Guarantees

1. **Anti-Collusion Blindness:** Standings, raw scores, and peer evaluations remain strictly invisible to judges and participants until the organizer explicitly triggers `results_published`.
2. **Timing Attack Resilience:** All signature checks utilize `hmac.compare_digest()` to prevent side-channel timing attacks.
3. **Database Portability:** Zero raw SQL vendor locks; runs identically on PostgreSQL (production) and SQLite (local dev).
4. **Idempotent Operations:** Critical operations such as certificate generation and bulk team CSV importation are wrapped in atomic database transactions (`transaction.atomic()`).
