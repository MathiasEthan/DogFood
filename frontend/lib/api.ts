const getApiBaseUrl = () => {
  if (typeof window === "undefined") {
    // Server-side inside Docker network
    return process.env.INTERNAL_API_URL || "http://backend:8000"
  }
  // Client-side in browser
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
}

export interface User {
  id: number
  username: string
  email: string
  role: "participant" | "judge" | "organizer" | "admin"
  first_name?: string
  last_name?: string
  bio?: string
  organization?: string
  created_at: string
}

export interface AuthResponse {
  message: string
  user: User
}

export interface TeamMember {
  id: number
  user_id: number
  username: string
  email: string
  is_leader: boolean
  joined_at: string
}

export interface Team {
  id: number
  name: string
  code: string
  event: number
  leader: number
  leader_username: string
  created_at: string
  members: TeamMember[]
  member_count: number
  max_size: number
  submission?: ProjectSubmission | null
}


export interface Track {
  id: number
  title: string
  description: string
}

export interface Prize {
  id: number
  title: string
  amount: string
  description: string
}

export interface ProjectSubmission {
  id: number
  team: number
  team_name: string
  title: string
  tagline: string
  problem_statement: string
  solution_description: string
  github_url: string
  demo_url: string
  presentation_url: string
  presentation_file: string | null
  tech_stack: string
  submitted_by: number
  submitted_by_username: string
  created_at: string
  updated_at: string
  is_draft: boolean
  track: number | null
  track_title?: string | null
  community_vote_count?: number | null
  has_voted?: boolean
  comment_count?: number
}

export interface EventRubric {
  id?: number
  title: string
  description?: string
  weight: number
  max_score?: number
}

export interface EvaluationScoreItem {
  id?: number
  rubric: number
  rubric_title?: string
  rubric_weight?: number
  score: number
}

export interface ProjectEvaluation {
  id: number
  submission: number
  submission_title: string
  team_name: string
  judge: number
  judge_username: string
  feedback: string
  total_score: number
  scores: EvaluationScoreItem[]
  created_at: string
  updated_at: string
}

export interface AnonymizedEvaluation {
  judge_label: string
  total_score: number
  feedback: string
  scores: EvaluationScoreItem[]
}

export interface LeaderboardEntry {
  rank?: number
  track_title?: string | null
  outliers_flagged?: number
  submission_id: number
  submission_title: string
  team_name: string
  tagline: string
  track: number | null
  average_score: number | null
  normalized_score?: number | null
  raw_score?: number | null
  standard_error?: number | null
  evaluations_count: number
  evaluations: Array<ProjectEvaluation | AnonymizedEvaluation>
}

export interface JudgingProgressSummary {
  total_submissions: number
  total_judges: number
  target_reviews_per_project?: number
  total_assignments: number
  completed_assignments: number
  overall_progress_percent: number
  saturation_percent?: number
  under_reviewed_count: number
  flagged_evaluations?: number
  results_published?: boolean
}

export interface JudgeProgressItem {
  judge_id: number
  username: string
  assigned: number
  completed: number
  progress_percent: number
  avg_review_seconds?: number | null
  raw_mean?: number | null
  shrunk_mean?: number | null
  shrunk_std?: number | null
  score_variance?: number | null
  flatline_warning?: boolean
}

export interface ProjectProgressItem {
  submission_id: number
  title: string
  team_name: string
  assigned_judges: number
  reviews_completed: number
  target_reviews: number
  saturation: "SATISFIED" | "IN_PROGRESS" | "DEFICIT"
  raw_score: number | null
  normalized_score: number | null
  standard_error: number | null
  outliers_flagged: number
}

export interface JudgingProgressResponse {
  summary: JudgingProgressSummary
  judges: JudgeProgressItem[]
  projects?: ProjectProgressItem[]
  under_reviewed_submissions: Array<{
    submission_id: number
    title: string
    team_name: string
    reviews_completed: number
    target_reviews: number
  }>
}

export interface Event {
  id: number
  title: string
  description: string
  banner: string | null
  start_date: string
  end_date: string
  mode: "virtual" | "in_person" | "hybrid"
  location: string
  prize_pool: string
  max_team_size: number
  created_by: number
  created_by_username: string
  created_at: string
  teams_count: number
  my_team?: Team | null
  teams?: Team[]
  tracks?: Track[]
  prizes?: Prize[]
  phases?: { id: number; title: string; start_date: string; end_date: string }[]
  rubrics?: EventRubric[]
  require_github_url?: boolean
  require_demo_url?: boolean
  require_presentation?: boolean
  submission_guidelines?: string
  event_judges?: { id: number; username: string; email?: string }[]
  community_voting_start?: string | null
  community_voting_end?: string | null
  show_community_voting_results?: boolean
  votes_per_user?: number
  voting_eligibility?: "any" | "registered"
  allow_self_vote?: boolean
  comments_enabled?: boolean
  judges_per_project?: number
  results_published?: boolean
}

export interface VotingStatus {
  event_id: number
  is_active: boolean
  has_ended: boolean
  voting_start: string | null
  voting_end: string | null
  votes_per_user: number
  voting_eligibility: "any" | "registered"
  allow_self_vote: boolean
  comments_enabled: boolean
  results_visible: boolean
  eligible: boolean
  ineligible_reason: string | null
  votes_used: number
  votes_remaining: number | null
  voted_submission_ids: number[]
  own_submission_id: number | null
}

export interface VoteResponse {
  detail: string
  has_voted: boolean
  votes_used: number
  votes_remaining: number | null
}

export interface CommunityResultRow {
  rank: number
  submission_id: number
  submission_title: string
  team_name: string
  track: string | null
  votes: number
}

export interface CommunityResults {
  event_id: number
  voting_closed: boolean
  total_votes: number
  results: CommunityResultRow[]
}

export interface CommunityComment {
  id: number
  submission: number
  author: number
  author_username: string
  text: string
  created_at: string
  updated_at: string
  is_edited: boolean
  can_edit: boolean
  can_remove: boolean
}

export interface CommunityAuditEntry {
  id: number
  timestamp: string
  action: string
  submission_id: number | null
  submission_title: string | null
  user_id: number | null
  username: string | null
  flagged: boolean
  metadata: Record<string, any>
  ip_address: string | null
  entry_hash: string
  prev_hash: string
}

export interface CommunityVoteRecord {
  id: number
  submission_id: number
  submission_title: string
  voter_id: number
  voter_username: string
  ip_address: string | null
  flags: string[]
  is_void: boolean
  void_reason: string
  created_at: string
}

// T4 Stretch - Certificates, Verification, Portability, Webhooks
export interface Certificate {
  id: number
  event: number
  event_title: string
  recipient_name: string
  recipient_email: string
  role: "winner" | "participant" | "judge"
  title: string
  award_title: string
  certificate_code: string
  signature: string
  signature_algorithm?: string
  public_key_hex?: string
  signed_payload?: Record<string, any>
  issued_at: string
  is_valid: boolean
  status?: "valid" | "revoked" | "invalid"
  revoked_at?: string | null
  revocation_reason?: string
  download_url?: string
  verification_url?: string
}

export interface JudgeRecordData {
  record_id: string
  judge_username: string
  event_title: string
  is_valid: boolean
  signature: string
  signature_algorithm: string
  public_key_hex?: string
  canonical_digest: string
  record: {
    judge_id: number
    judge_username: string
    event_id: number
    event_title: string
    evaluations_count: number
    average_score_given: number | null
    scored_rubrics_count: number
    first_evaluation_at: string | null
    last_evaluation_at: string | null
    signed_at?: string
    key_id?: string
  }
}

export interface WebhookEndpoint {
  id: number
  target_url: string
  is_active: boolean
  subscribed_events: string[]
  created_at: string
  updated_at?: string
  secret?: string
}

export interface WebhookDelivery {
  id: number
  event_type: string
  status: "SUCCESS" | "FAILED" | "PENDING"
  response_status: number | null
  attempt_count: number
  created_at: string
  payload?: any
  response_body?: string
}


export class ApiError extends Error {
  status: number
  data: any
  constructor(message: string, status: number, data: any) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.data = data
  }
}

// Paths that must never trigger an automatic token refresh + retry
const NO_REFRESH_PATHS = ["/api/auth/login/", "/api/auth/register/", "/api/auth/refresh/", "/api/auth/logout/"]
let refreshInFlight: Promise<boolean> | null = null

async function tryRefreshSession(baseUrl: string): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${baseUrl}/api/auth/refresh/`, {
      method: "POST",
      credentials: "include",
    })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null
      })
  }
  return refreshInFlight
}

export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const baseUrl = getApiBaseUrl()
  const url = `${baseUrl}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`

  const isFormData = options.body instanceof FormData

  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(options.headers as Record<string, string>),
  }

  const doFetch = () =>
    fetch(url, {
      ...options,
      headers,
      credentials: "include", // Essential for HttpOnly cookie transfer
    })

  let response = await doFetch()

  // Access tokens expire after ~60 min: silently rotate via the refresh cookie once, then retry
  if (
    response.status === 401 &&
    typeof window !== "undefined" &&
    !NO_REFRESH_PATHS.some((p) => endpoint.startsWith(p))
  ) {
    const refreshed = await tryRefreshSession(baseUrl)
    if (refreshed) {
      response = await doFetch()
    }
  }

  let data: any
  try {
    data = await response.json()
  } catch (err) {
    data = null
  }

  if (!response.ok) {
    const errorMessage =
      data?.detail ||
      data?.non_field_errors?.[0] ||
      (typeof data === "object" && data !== null
        ? Object.entries(data)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`)
            .join("; ")
        : `Request failed with status ${response.status}`)
    throw new ApiError(errorMessage, response.status, data)
  }

  return data as T
}

export const api = {
  // Authentication
  login: (credentials: { username: string; password: string }) =>
    apiRequest<AuthResponse>("/api/auth/login/", {
      method: "POST",
      body: JSON.stringify(credentials),
    }),

  register: (payload: {
    username: string
    email: string
    password: string
    confirm_password: string
    role: "participant" | "organizer"
  }) =>
    apiRequest<AuthResponse>("/api/auth/register/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  logout: () =>
    apiRequest<{ message: string }>("/api/auth/logout/", {
      method: "POST",
    }),

  getMe: () => apiRequest<User>("/api/auth/me/"),

  refreshToken: () =>
    apiRequest<{ message: string }>("/api/auth/refresh/", {
      method: "POST",
    }),

  // Admin & Organizer Management
  listUsers: () => apiRequest<User[]>("/api/auth/users/"),

  listAppointableJudges: (query?: string) =>
    apiRequest<User[]>(
      query
        ? `/api/auth/appointable-judges/?q=${encodeURIComponent(query)}`
        : "/api/auth/appointable-judges/"
    ),

  appointJudge: (userId: number) =>
    apiRequest<{ message: string; user: User }>(
      `/api/auth/users/${userId}/appoint-judge/`,
      {
        method: "POST",
      }
    ),

  // Events & Teams
  listEvents: (params?: { filter?: string }) => {
    let url = "/api/events/"
    if (params?.filter) {
      url += `?filter=${encodeURIComponent(params.filter)}`
    }
    return apiRequest<Event[]>(url)
  },

  listMyOrganizedEvents: () => apiRequest<Event[]>("/api/events/?filter=organized"),

  listMyJudgedEvents: () => apiRequest<Event[]>("/api/events/?filter=judged"),

  getEvent: (id: number | string) => apiRequest<Event>(`/api/events/${id}/`),

  createEvent: (formData: FormData) =>
    apiRequest<Event>("/api/events/", {
      method: "POST",
      body: formData,
    }),

  updateEvent: (eventId: number, data: Partial<any>) =>
    apiRequest<Event>(`/api/events/admin/events/${eventId}/`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  createTeam: (eventId: number | string, name: string) =>
    apiRequest<{ message: string; team: Team }>(
      `/api/events/${eventId}/teams/create/`,
      {
        method: "POST",
        body: JSON.stringify({ name }),
      }
    ),

  joinTeam: (eventId: number | string, code: string) =>
    apiRequest<{ message: string; team: Team }>(
      `/api/events/${eventId}/teams/join/`,
      {
        method: "POST",
        body: JSON.stringify({ code }),
      }
    ),

  leaveTeam: (eventId: number | string) =>
    apiRequest<{ message: string }>(`/api/events/${eventId}/teams/leave/`, {
      method: "POST",
    }),

  // Project Submissions
  getMySubmission: (eventId: number | string) =>
    apiRequest<ProjectSubmission>(`/api/events/${eventId}/my-submission/`),

  submitProject: (eventId: number | string, formData: FormData) =>
    apiRequest<{ message: string; submission: ProjectSubmission }>(
      `/api/events/${eventId}/submit/`,
      {
        method: "POST",
        body: formData,
      }
    ),

  listGallery: (eventId: number | string, params?: { q?: string; track?: string }) => {
    let url = `/api/events/${eventId}/gallery/`
    if (params) {
      const qs = new URLSearchParams()
      if (params.q) qs.append("q", params.q)
      if (params.track) qs.append("track", params.track)
      url += `?${qs.toString()}`
    }
    return apiRequest<ProjectSubmission[]>(url)
  },

  // Admin / Organizer Management Endpoints
  deleteEvent: (eventId: number) =>
    apiRequest<{ message: string }>(`/api/events/admin/events/${eventId}/`, {
      method: "DELETE",
    }),
  updateEventAdmin: (eventId: number, data: Partial<Event>) =>
    apiRequest<Event>(`/api/events/admin/events/${eventId}/`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  addEventJudge: (
    eventId: number,
    payload: number | { user_id?: number; username?: string; email?: string }
  ) =>
    apiRequest<{ message: string; judge?: any }>(
      `/api/events/admin/events/${eventId}/judges/`,
      {
        method: "POST",
        body: JSON.stringify(
          typeof payload === "number" ? { user_id: payload } : payload
        ),
      }
    ),
  removeEventJudge: (
    eventId: number,
    payload: number | { user_id?: number; username?: string; email?: string }
  ) =>
    apiRequest<{ message: string }>(
      `/api/events/admin/events/${eventId}/judges/`,
      {
        method: "DELETE",
        body: JSON.stringify(
          typeof payload === "number" ? { user_id: payload } : payload
        ),
      }
    ),
  listAllTeams: (eventId?: number) =>
    apiRequest<Team[]>(
      eventId ? `/api/events/admin/teams/?event=${eventId}` : "/api/events/admin/teams/"
    ),
  getTeamAdmin: (teamId: number) => apiRequest<Team>(`/api/events/admin/teams/${teamId}/`),
  removeTeamMember: (teamId: number, userId: number) =>
    apiRequest<{ message: string }>(`/api/events/admin/teams/${teamId}/members/${userId}/`, {
      method: "DELETE",
    }),
  deleteTeam: (teamId: number) =>
    apiRequest<{ message: string }>(`/api/events/admin/teams/${teamId}/`, {
      method: "DELETE",
    }),
  updateTeamAdmin: (teamId: number, data: Partial<Team>) =>
    apiRequest<Team>(`/api/events/admin/teams/${teamId}/`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  listAllSubmissions: (eventId?: number) => apiRequest<ProjectSubmission[]>(eventId ? `/api/events/admin/submissions/?event=${eventId}` : "/api/events/admin/submissions/"),
  deleteSubmission: (subId: number) =>
    apiRequest<{ message: string }>(`/api/events/admin/submissions/${subId}/`, {
      method: "DELETE",
    }),
  updateSubmissionAdmin: (subId: number, data: Partial<ProjectSubmission>) =>
    apiRequest<ProjectSubmission>(`/api/events/admin/submissions/${subId}/`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  listEventSubmissions: (eventId: number | string) =>
    apiRequest<ProjectSubmission[]>(`/api/events/${eventId}/submissions/`),

  // Rubrics & Judging Evaluation Endpoints
  getEventRubrics: (eventId: number | string) =>
    apiRequest<EventRubric[]>(`/api/events/${eventId}/rubrics/`),

  createRubric: (eventId: number | string, data: Partial<EventRubric>) =>
    apiRequest<EventRubric>(`/api/events/${eventId}/rubrics/`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  deleteRubric: (eventId: number | string, rubricId: number) =>
    apiRequest<{ message: string }>(`/api/events/${eventId}/rubrics/${rubricId}/`, {
      method: "DELETE",
    }),

  submitEvaluation: (
    eventId: number | string,
    submissionId: number | string,
    payload: { scores: { rubric_id: number; score: number }[]; feedback?: string }
  ) =>
    apiRequest<{ message: string; evaluation: ProjectEvaluation }>(
      `/api/events/${eventId}/submissions/${submissionId}/evaluate/`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    ),

  getMyEvaluation: (eventId: number | string, submissionId: number | string) =>
    apiRequest<{ evaluated: boolean; evaluation: ProjectEvaluation | null }>(
      `/api/events/${eventId}/submissions/${submissionId}/evaluate/`
    ),

  getLeaderboard: (eventId: number | string) =>
    apiRequest<LeaderboardEntry[]>(`/api/events/${eventId}/leaderboard/`),

  assignJudges: (eventId: number | string, k: number = 3) =>
    apiRequest<{
      success: boolean
      total_submissions: number
      total_judges: number
      target_k: number
      total_assignments_created: number
      workload_distribution: Record<string, number>
      fully_saturated?: boolean
      deficits?: { submission_id: number; title: string; assigned: number; target: number }[]
      warning?: string | null
    }>(`/api/events/${eventId}/admin/assign-judges/`, {
      method: "POST",
      body: JSON.stringify({ k_per_project: k }),
    }),

  getJudgingProgress: (eventId: number | string) =>
    apiRequest<JudgingProgressResponse>(`/api/events/${eventId}/admin/judging-progress/`),

  getLeaderboardCsvUrl: (eventId: number | string) =>
    `${getApiBaseUrl()}/api/events/${eventId}/admin/export/leaderboard-csv/`,

  getRubricsCsvUrl: (eventId: number | string) =>
    `${getApiBaseUrl()}/api/events/${eventId}/admin/export/rubrics-csv/`,
    
  getFeedbackCsvUrl: (eventId: number | string) =>
    `${getApiBaseUrl()}/api/events/${eventId}/admin/export/feedback-csv/`,

  getSubmissionsCsvUrl: (eventId: number | string) =>
    `${getApiBaseUrl()}/api/events/${eventId}/admin/export/submissions-csv/`,

  getAssignmentsCsvUrl: (eventId: number | string) =>
    `${getApiBaseUrl()}/api/events/${eventId}/admin/export/assignments-csv/`,

  getEvaluationAuditCsvUrl: (eventId: number | string) =>
    `${getApiBaseUrl()}/api/events/${eventId}/admin/export/evaluation-audit-csv/`,

  publishResults: (eventId: number | string, published: boolean) =>
    apiRequest<{ results_published: boolean }>(`/api/events/${eventId}/admin/publish-results/`, {
      method: "POST",
      body: JSON.stringify({ published }),
    }),

  // T3 - Community voting
  getVotingStatus: (eventId: number | string) =>
    apiRequest<VotingStatus>(`/api/events/${eventId}/voting/`),

  castVote: (eventId: number | string, submissionId: number | string) =>
    apiRequest<VoteResponse>(`/api/events/${eventId}/submissions/${submissionId}/vote/`, {
      method: "POST",
    }),

  withdrawVote: (eventId: number | string, submissionId: number | string) =>
    apiRequest<VoteResponse>(`/api/events/${eventId}/submissions/${submissionId}/vote/`, {
      method: "DELETE",
    }),

  getCommunityResults: (eventId: number | string) =>
    apiRequest<CommunityResults>(`/api/events/${eventId}/community-results/`),

  listComments: (eventId: number | string, submissionId: number | string) =>
    apiRequest<CommunityComment[]>(`/api/events/${eventId}/submissions/${submissionId}/comments/`),

  postComment: (eventId: number | string, submissionId: number | string, text: string) =>
    apiRequest<CommunityComment>(`/api/events/${eventId}/submissions/${submissionId}/comments/`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  editComment: (eventId: number | string, commentId: number, text: string) =>
    apiRequest<CommunityComment>(`/api/events/${eventId}/comments/${commentId}/`, {
      method: "PATCH",
      body: JSON.stringify({ text }),
    }),

  deleteComment: (eventId: number | string, commentId: number) =>
    apiRequest<{ detail: string }>(`/api/events/${eventId}/comments/${commentId}/`, {
      method: "DELETE",
    }),

  getCommunityAudit: (eventId: number | string, params?: { flagged?: boolean }) =>
    apiRequest<CommunityAuditEntry[]>(
      `/api/events/${eventId}/admin/community-audit/${params?.flagged ? "?flagged=1" : ""}`
    ),

  verifyCommunityAudit: (eventId: number | string) =>
    apiRequest<{ valid: boolean; entries_checked: number; head_hash?: string; first_invalid_entry_id?: number }>(
      `/api/events/${eventId}/admin/community-audit/verify/`
    ),

  listCommunityVotes: (eventId: number | string, params?: { flagged?: boolean }) =>
    apiRequest<CommunityVoteRecord[]>(
      `/api/events/${eventId}/admin/community-votes/${params?.flagged ? "?flagged=1" : ""}`
    ),

  voidCommunityVote: (eventId: number | string, voteId: number, reason: string) =>
    apiRequest<{ detail: string }>(`/api/events/${eventId}/admin/community-votes/${voteId}/void/`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  getCommunityVotesCsvUrl: (eventId: number | string) =>
    `${getApiBaseUrl()}/api/events/${eventId}/admin/export/community-votes-csv/`,

  getCommunityAuditCsvUrl: (eventId: number | string) =>
    `${getApiBaseUrl()}/api/events/${eventId}/admin/export/community-audit-csv/`,

  // T4 Stretch
  generateCertificates: (eventId: number | string) =>
    apiRequest<{ message: string; certificates_count: number; records_signed: number; revoked_count: number }>(
      `/api/events/${eventId}/admin/certificates/generate/`,
      { method: "POST" }
    ),

  listEventCertificates: (eventId: number | string) =>
    apiRequest<Certificate[]>(`/api/events/${eventId}/certificates/`),

  getMyCertificates: () =>
    apiRequest<Certificate[]>(`/api/my-certificates/`),

  getPublicCertificate: (code: string) =>
    apiRequest<Certificate>(`/api/certificates/${code}/`),

  getCertificateDownloadUrl: (code: string) =>
    `${getApiBaseUrl()}/api/certificates/${code}/download/`,

  getMyJudgeRecord: (eventId: number | string) =>
    apiRequest<JudgeRecordData>(`/api/events/${eventId}/my-judge-record/`),

  getPublicJudgeRecord: (recordId: string) =>
    apiRequest<JudgeRecordData>(`/api/judges/records/${recordId}/verify/`),

  getExportBulkArchiveUrl: (eventId: number | string) =>
    `${getApiBaseUrl()}/api/events/${eventId}/admin/export/bulk-archive/?download=1`,

  exportBulkArchive: (eventId: number | string) =>
    apiRequest<any>(`/api/events/${eventId}/admin/export/bulk-archive/`),

  importBulkArchive: (archiveData: any) =>
    apiRequest<{ message: string; event_id: number }>(`/api/events/admin/import/bulk-archive/`, {
      method: "POST",
      body: JSON.stringify(archiveData),
    }),

  importTeamsCsv: (eventId: number | string, csvContent: string) =>
    apiRequest<{
      message: string
      teams_created: number
      members_added: number
      users_created?: number
      skipped?: { line: number; username?: string; reason: string }[]
    }>(
      `/api/events/${eventId}/admin/import/teams-csv/`,
      {
        method: "POST",
        body: JSON.stringify({ csv_content: csvContent }),
      }
    ),

  listWebhooks: (eventId: number | string) =>
    apiRequest<WebhookEndpoint[]>(`/api/events/${eventId}/webhooks/`),

  createWebhook: (
    eventId: number | string,
    data: { target_url: string; subscribed_events: string[]; secret?: string }
  ) =>
    apiRequest<WebhookEndpoint>(`/api/events/${eventId}/webhooks/`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateWebhook: (
    eventId: number | string,
    webhookId: number,
    data: { target_url?: string; is_active?: boolean; subscribed_events?: string[] }
  ) =>
    apiRequest<WebhookEndpoint>(`/api/events/${eventId}/webhooks/${webhookId}/`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteWebhook: (eventId: number | string, webhookId: number) =>
    apiRequest<void>(`/api/events/${eventId}/webhooks/${webhookId}/`, {
      method: "DELETE",
    }),

  testWebhook: (eventId: number | string, webhookId: number) =>
    apiRequest<{ delivery_id: number; status: "SUCCESS" | "FAILED" | "PENDING"; status_code: number | null; response_body: string }>(`/api/events/${eventId}/webhooks/${webhookId}/test/`, {
      method: "POST",
    }),

  listWebhookDeliveries: (eventId: number | string, webhookId: number) =>
    apiRequest<WebhookDelivery[]>(`/api/events/${eventId}/webhooks/${webhookId}/deliveries/`),

  getWebhookEvents: () =>
    apiRequest<{ event_types: { value: string; label: string }[] }>(`/api/events/webhook-events/`),

  getSigningKey: () =>
    apiRequest<{ algorithm: string; key_id: string; public_key_hex: string; public_key_pem: string }>(`/api/signing-key/`),

  getSigningKeyUrl: () => `${getApiBaseUrl()}/api/signing-key/`,

  lookupTeamInvite: (eventId: number | string, code: string) =>
    apiRequest<{
      event_id: number
      event_title: string
      team_name: string
      code: string
      leader_username: string
      member_count: number
      max_size: number
      is_full: boolean
      already_in_a_team: boolean
    }>(`/api/events/${eventId}/teams/lookup/?code=${encodeURIComponent(code)}`),
}

export function buildInviteLink(eventId: number | string, code: string) {
  const origin = typeof window !== "undefined" ? window.location.origin : ""
  return `${origin}/events/${eventId}?join=${encodeURIComponent(code)}`
}

