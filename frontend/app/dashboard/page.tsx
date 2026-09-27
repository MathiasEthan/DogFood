"use client"

import React, { useEffect, useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useAuth } from "@/context/auth-context"
import { Header } from "@/components/header"
import { Squares } from "@/components/reactbits/squares"
import { api, User, Event, Team, ProjectSubmission } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { JudgeAppointmentCombobox } from "@/components/judge-appointment-combobox"
import { EditEventModal } from "@/components/edit-event-modal"
import {
  Loader2,
  CheckCircle2,
  AlertCircle,
  Plus,
  Trophy,
  Users,
  Calendar,
  ExternalLink,
  Edit2,
  FolderGit2,
  Shield,
  Trash2,
  Layers,
  ArrowRight,
  Download,
  Scale,
} from "lucide-react"

export default function DashboardPage() {
  const { user, isLoading } = useAuth()
  const router = useRouter()

  // State
  const [organizedEvents, setOrganizedEvents] = useState<Event[]>([])
  const [judgedEvents, setJudgedEvents] = useState<Event[]>([])
  const [allEvents, setAllEvents] = useState<Event[]>([])
  const [usersList, setUsersList] = useState<User[]>([])
  const [teamsList, setTeamsList] = useState<Team[]>([])
  const [submissionsList, setSubmissionsList] = useState<ProjectSubmission[]>([])

  const [loadingData, setLoadingData] = useState(true)
  const [activeAdminTab, setActiveAdminTab] = useState<"contests" | "users" | "teams" | "submissions">("contests")
  const [adminFilterEventId, setAdminFilterEventId] = useState<number | null>(null)

  // Modals & Feedback
  const [editingEvent, setEditingEvent] = useState<Event | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  // Redirect unauthenticated users
  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login")
    }
  }, [user, isLoading, router])

  // Data fetching
  const loadDashboardData = useCallback(async () => {
    if (!user) return
    setLoadingData(true)
    setActionError(null)

    try {
      if (user.role === "organizer") {
        const myEvs = await api.listMyOrganizedEvents()
        setOrganizedEvents(myEvs)
      } else if (user.role === "judge") {
        const jEvs = await api.listMyJudgedEvents()
        setJudgedEvents(jEvs)
      } else if (user.role === "admin") {
        const [allEvs, myEvs, users] = await Promise.all([
          api.listEvents(),
          api.listMyOrganizedEvents(),
          api.listUsers(),
        ])
        setAllEvents(allEvs)
        setOrganizedEvents(myEvs)
        setUsersList(users)

        const [tms, subs] = await Promise.all([
          api.listAllTeams(adminFilterEventId || undefined),
          api.listAllSubmissions(adminFilterEventId || undefined),
        ])
        setTeamsList(tms)
        setSubmissionsList(subs)
      }
    } catch (err: any) {
      setActionError(err.message || "Failed to load dashboard data.")
    } finally {
      setLoadingData(false)
    }
  }, [user, adminFilterEventId])

  useEffect(() => {
    loadDashboardData()
  }, [loadDashboardData])

  // Admin filter updates
  useEffect(() => {
    if (user?.role === "admin") {
      const updateAdminSubLists = async () => {
        try {
          const [tms, subs] = await Promise.all([
            api.listAllTeams(adminFilterEventId || undefined),
            api.listAllSubmissions(adminFilterEventId || undefined),
          ])
          setTeamsList(tms)
          setSubmissionsList(subs)
        } catch (err: any) {
          setActionError(err.message)
        }
      }
      updateAdminSubLists()
    }
  }, [adminFilterEventId, user?.role])

  // Handlers
  const handleDeleteEvent = async (id: number) => {
    if (!confirm("Are you sure you want to permanently delete this event?")) return
    try {
      await api.deleteEvent(id)
      setActionSuccess("Event deleted successfully.")
      loadDashboardData()
    } catch (err: any) {
      setActionError(err.message || "Failed to delete event.")
    }
  }

  const handleDeleteTeam = async (id: number) => {
    if (!confirm("Are you sure you want to delete this team?")) return
    try {
      await api.deleteTeam(id)
      setActionSuccess("Team removed.")
      loadDashboardData()
    } catch (err: any) {
      setActionError(err.message)
    }
  }

  const handleDeleteSubmission = async (id: number) => {
    if (!confirm("Are you sure you want to delete this submission?")) return
    try {
      await api.deleteSubmission(id)
      setActionSuccess("Submission removed.")
      loadDashboardData()
    } catch (err: any) {
      setActionError(err.message)
    }
  }

  const handleAppointPlatformJudge = async (userId: number, username: string) => {
    try {
      await api.appointJudge(userId)
      setActionSuccess(`@${username} designated as platform Judge.`)
      loadDashboardData()
    } catch (err: any) {
      setActionError(err.message || "Failed to appoint judge.")
    }
  }

  const handleAutoAssignJudges = async (eventId: number) => {
    try {
      const ev = [...organizedEvents, ...allEvents].find((e) => e.id === eventId)
      const res = await api.assignJudges(eventId, ev?.judges_per_project ?? 3)
      setActionSuccess(
        `Allocated ${res.total_assignments_created} evaluations across ${res.total_judges} judges (K=${res.target_k}) with zero COI violations.`
      )
      if (res.warning) {
        setActionError(res.warning)
      }
      loadDashboardData()
    } catch (err: any) {
      setActionError(err.message || "Failed to auto-assign judges.")
    }
  }

  if (isLoading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background font-mono text-xs text-muted-foreground">
        <Loader2 className="size-4 animate-spin mr-2" />
        authenticating session...
      </div>
    )
  }

  const now = new Date()

  return (
    <div className="relative min-h-screen flex flex-col bg-background font-mono overflow-hidden">
      <Header />

      <div className="relative flex-1 p-4 sm:p-8 max-w-6xl mx-auto w-full space-y-6">
        <Squares
          direction="diagonal"
          speed={0.2}
          squareSize={48}
          borderColor="rgba(255, 255, 255, 0.03)"
          hoverFillColor="rgba(255, 255, 255, 0.06)"
          className="z-0"
        />

        <div className="relative z-10 space-y-6">
          {/* Active Session Overview Banner */}
          <div className="rounded-xl border border-border/40 bg-background/80 p-5 backdrop-blur-md">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
                  Logged in as
                </p>
                <h1 className="text-lg font-semibold text-foreground flex items-center gap-2">
                  @{user.username}
                  <span className="text-[11px] font-mono font-normal text-muted-foreground">
                    ({user.email})
                  </span>
                </h1>
              </div>

              <div className="flex items-center gap-3">
                <span className="text-[11px] text-muted-foreground">Role:</span>
                <Badge
                  variant="outline"
                  className={`text-xs font-semibold px-2.5 py-0.5 rounded capitalize ${
                    user.role === "admin"
                      ? "text-rose-400 border-rose-500/30 bg-rose-500/10"
                      : user.role === "judge"
                      ? "text-amber-400 border-amber-500/30 bg-amber-500/10"
                      : user.role === "organizer"
                      ? "text-purple-400 border-purple-500/30 bg-purple-500/10"
                      : "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
                  }`}
                >
                  {user.role}
                </Badge>

                {user.role === "organizer" && (
                  <Link href="/events/create">
                    <Button size="sm" className="h-8 text-xs font-mono bg-foreground text-background hover:bg-foreground/90">
                      <Plus className="size-3.5 mr-1" />
                      Create Contest
                    </Button>
                  </Link>
                )}
              </div>
            </div>
          </div>

          {/* Feedback Messages */}
          {actionSuccess && (
            <div className="flex items-center justify-between gap-2 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 p-3 rounded-lg">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="size-4 shrink-0" />
                <span>{actionSuccess}</span>
              </div>
              <button
                onClick={() => setActionSuccess(null)}
                className="text-emerald-400/70 hover:text-emerald-400"
              >
                ✕
              </button>
            </div>
          )}

          {actionError && (
            <div className="flex items-center justify-between gap-2 text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 p-3 rounded-lg">
              <div className="flex items-center gap-2">
                <AlertCircle className="size-4 shrink-0" />
                <span>{actionError}</span>
              </div>
              <button
                onClick={() => setActionError(null)}
                className="text-rose-400/70 hover:text-rose-400"
              >
                ✕
              </button>
            </div>
          )}

          {/* ============================================================== */}
          {/* 1. ORGANIZER VIEW                                              */}
          {/* ============================================================== */}
          {user.role === "organizer" && (
            <div className="space-y-6">
              {/* Metric Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-4 rounded-xl border border-border/40 bg-background/80 backdrop-blur-md space-y-1">
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Trophy className="size-3.5 text-purple-400" /> Contests Created
                  </div>
                  <div className="text-xl font-bold text-foreground">
                    {organizedEvents.length}
                  </div>
                </div>

                <div className="p-4 rounded-xl border border-border/40 bg-background/80 backdrop-blur-md space-y-1">
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Calendar className="size-3.5 text-emerald-400" /> Active Now
                  </div>
                  <div className="text-xl font-bold text-foreground">
                    {
                      organizedEvents.filter(
                        (e) => new Date(e.end_date) >= now && new Date(e.start_date) <= now
                      ).length
                    }
                  </div>
                </div>

                <div className="p-4 rounded-xl border border-border/40 bg-background/80 backdrop-blur-md space-y-1">
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Users className="size-3.5 text-primary" /> Total Teams Registered
                  </div>
                  <div className="text-xl font-bold text-foreground">
                    {organizedEvents.reduce((acc, curr) => acc + (curr.teams_count || 0), 0)}
                  </div>
                </div>
              </div>

              {/* Contests List */}
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-border/20 pb-3">
                  <div>
                    <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
                      My Contests ({organizedEvents.length})
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      Manage your hackathons, appoint judges via search, and edit contest details.
                    </p>
                  </div>
                  <Link href="/events/create">
                    <Button size="sm" variant="outline" className="h-7 text-xs font-mono">
                      <Plus className="size-3 mr-1" /> New Contest
                    </Button>
                  </Link>
                </div>

                {loadingData ? (
                  <div className="p-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                    <Loader2 className="size-4 animate-spin" />
                    Loading your contests...
                  </div>
                ) : organizedEvents.length === 0 ? (
                  <div className="p-8 text-center rounded-xl border border-border/40 bg-background/80 backdrop-blur-md space-y-3">
                    <Trophy className="size-8 text-muted-foreground mx-auto" />
                    <div className="text-sm font-semibold text-foreground">No Contests Created Yet</div>
                    <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                      You haven't launched any hackathons. Create your first contest to set up tracks, phases, and appoint judges.
                    </p>
                    <Link href="/events/create">
                      <Button size="sm" className="h-8 text-xs font-mono bg-foreground text-background">
                        Launch First Contest
                      </Button>
                    </Link>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {organizedEvents.map((ev) => {
                      const isLive = new Date(ev.start_date) <= now && new Date(ev.end_date) >= now
                      const isUpcoming = new Date(ev.start_date) > now
                      const isEnded = new Date(ev.end_date) < now

                      return (
                        <div
                          key={ev.id}
                          className="rounded-xl border border-border/40 bg-background/80 p-5 backdrop-blur-md space-y-4 hover:border-border/70 transition-colors"
                        >
                          {/* Contest Header */}
                          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 border-b border-border/20 pb-4">
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <h3 className="text-base font-semibold text-foreground">
                                  {ev.title}
                                </h3>
                                {isLive && (
                                  <Badge variant="outline" className="text-[10px] text-emerald-400 border-emerald-500/30 bg-emerald-500/10">
                                    Live Now
                                  </Badge>
                                )}
                                {isUpcoming && (
                                  <Badge variant="outline" className="text-[10px] text-amber-400 border-amber-500/30 bg-amber-500/10">
                                    Upcoming
                                  </Badge>
                                )}
                                {isEnded && (
                                  <Badge variant="outline" className="text-[10px] text-muted-foreground border-border/40">
                                    Ended
                                  </Badge>
                                )}
                              </div>
                              <p className="text-xs text-muted-foreground line-clamp-2 max-w-2xl font-sans">
                                {ev.description}
                              </p>
                              <div className="flex flex-wrap items-center gap-3 pt-1 text-[11px] text-muted-foreground">
                                <span>Mode: <strong className="text-foreground capitalize">{ev.mode}</strong></span>
                                <span>•</span>
                                <span>Prize: <strong className="text-foreground">{ev.prize_pool || "N/A"}</strong></span>
                                <span>•</span>
                                <span>Teams: <strong className="text-foreground">{ev.teams_count || 0}</strong></span>
                                <span>•</span>
                                <span>Dates: <strong className="text-foreground">{new Date(ev.start_date).toLocaleDateString()} - {new Date(ev.end_date).toLocaleDateString()}</strong></span>
                              </div>
                            </div>

                            {/* Contest Quick Actions */}
                            <div className="flex items-center gap-2 shrink-0">
                              <Link href={`/events/${ev.id}`}>
                                <Button size="sm" variant="outline" className="h-7 text-xs font-mono">
                                  <ExternalLink className="size-3 mr-1" /> View Event
                                </Button>
                              </Link>
                              <Link href={`/events/${ev.id}/gallery`}>
                                <Button size="sm" variant="outline" className="h-7 text-xs font-mono">
                                  <FolderGit2 className="size-3 mr-1" /> Gallery
                                </Button>
                              </Link>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => window.open(api.getLeaderboardCsvUrl(ev.id), '_blank')}
                                className="h-7 text-xs font-mono hover:text-emerald-400 border-border/40"
                                title="Download Leaderboard Standings CSV"
                              >
                                <Download className="size-3 mr-1 text-emerald-400" /> CSV
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setEditingEvent(ev)}
                                className="h-7 text-xs font-mono hover:border-primary hover:text-primary"
                              >
                                <Edit2 className="size-3 mr-1" /> Edit
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleDeleteEvent(ev.id)}
                                className="h-7 text-xs font-mono text-destructive hover:bg-destructive/10"
                              >
                                <Trash2 className="size-3" />
                              </Button>
                            </div>
                          </div>

                          {/* Filterable Judge Appointment & Allocation Section */}
                          <div className="rounded-lg border border-border/30 bg-muted/10 p-3.5 space-y-3">
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/20 pb-2">
                              <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                                <Shield className="size-3.5 text-primary" />
                                Judging Board & Allocation
                              </div>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleAutoAssignJudges(ev.id)}
                                className="h-6 text-[11px] font-mono border-primary/30 text-primary hover:bg-primary/10"
                                title="Run load-balanced bipartite matching algorithm to allocate submissions to judges with zero COI violations"
                              >
                                <Scale className="size-3 mr-1" /> Auto-Assign Reviewers (K=3)
                              </Button>
                            </div>
                            <JudgeAppointmentCombobox
                              eventId={ev.id}
                              currentJudges={ev.event_judges || []}
                              onJudgeAdded={(newJudge) => {
                                setOrganizedEvents((prev) =>
                                  prev.map((e) =>
                                    e.id === ev.id
                                      ? {
                                          ...e,
                                          event_judges: [...(e.event_judges || []), newJudge],
                                        }
                                      : e
                                  )
                                )
                              }}
                              onJudgeRemoved={(judgeId) => {
                                setOrganizedEvents((prev) =>
                                  prev.map((e) =>
                                    e.id === ev.id
                                      ? {
                                          ...e,
                                          event_judges: (e.event_judges || []).filter(
                                            (j) => j.id !== judgeId
                                          ),
                                        }
                                      : e
                                  )
                                )
                              }}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* 2. JUDGE VIEW                                                  */}
          {/* ============================================================== */}
          {user.role === "judge" && (
            <div className="space-y-6">
              {/* Metric Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="p-4 rounded-xl border border-border/40 bg-background/80 backdrop-blur-md space-y-1">
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Shield className="size-3.5 text-amber-400" /> Contests Assigned
                  </div>
                  <div className="text-xl font-bold text-foreground">
                    {judgedEvents.length}
                  </div>
                </div>

                <div className="p-4 rounded-xl border border-border/40 bg-background/80 backdrop-blur-md space-y-1">
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <FolderGit2 className="size-3.5 text-emerald-400" /> Evaluation Roster
                  </div>
                  <div className="text-xs font-semibold text-emerald-400 pt-1">
                    Ready to Review & Score Submissions
                  </div>
                </div>
              </div>

              {/* Assigned Contests List */}
              <div className="space-y-4">
                <div className="border-b border-border/20 pb-3">
                  <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
                    <Shield className="size-4 text-amber-400" />
                    Assigned Hackathons for Evaluation ({judgedEvents.length})
                  </h2>
                  <p className="text-xs text-muted-foreground">
                    You have been appointed as an official judge for these competitions. Review projects and evaluate submissions.
                  </p>
                </div>

                {loadingData ? (
                  <div className="p-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                    <Loader2 className="size-4 animate-spin" />
                    Loading assigned contests...
                  </div>
                ) : judgedEvents.length === 0 ? (
                  <div className="p-8 text-center rounded-xl border border-border/40 bg-background/80 backdrop-blur-md space-y-3">
                    <Shield className="size-8 text-muted-foreground mx-auto" />
                    <div className="text-sm font-semibold text-foreground">No Contests Assigned Yet</div>
                    <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                      You have not been assigned to judge any hackathons yet. Once an organizer appoints you, the contest will show up here.
                    </p>
                    <Link href="/">
                      <Button size="sm" variant="outline" className="h-8 text-xs font-mono">
                        Browse Platform Hackathons
                      </Button>
                    </Link>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {judgedEvents.map((ev) => (
                      <div
                        key={ev.id}
                        className="rounded-xl border border-border/40 bg-background/80 p-5 backdrop-blur-md space-y-4"
                      >
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/20 pb-4">
                          <div className="space-y-1">
                            <h3 className="text-base font-semibold text-foreground">
                              {ev.title}
                            </h3>
                            <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
                              <span>Organized by <strong className="text-foreground">@{ev.created_by_username}</strong></span>
                              <span>•</span>
                              <span>Mode: <strong className="text-foreground capitalize">{ev.mode}</strong></span>
                              <span>•</span>
                              <span>Prize Pool: <strong className="text-foreground">{ev.prize_pool || "N/A"}</strong></span>
                              <span>•</span>
                              <span>Timeline: <strong className="text-foreground">{new Date(ev.start_date).toLocaleDateString()} - {new Date(ev.end_date).toLocaleDateString()}</strong></span>
                            </div>
                          </div>

                          <div className="flex items-center gap-2">
                            <Link href={`/events/${ev.id}`}>
                              <Button size="sm" variant="outline" className="h-8 text-xs font-mono">
                                <ExternalLink className="size-3.5 mr-1" /> Contest Page
                              </Button>
                            </Link>
                            <Link href={`/events/${ev.id}/gallery`}>
                              <Button size="sm" className="h-8 text-xs font-mono bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/30">
                                <FolderGit2 className="size-3.5 mr-1" /> Evaluate Submissions
                              </Button>
                            </Link>
                          </div>
                        </div>

                        {/* Deliverables requirements hint */}
                        <div className="text-[11px] text-muted-foreground flex items-center gap-4">
                          <span className="font-semibold text-foreground">Evaluation Scope:</span>
                          <span>GitHub Repo: {ev.require_github_url ? "Required" : "Optional"}</span>
                          <span>•</span>
                          <span>Live Demo: {ev.require_demo_url ? "Required" : "Optional"}</span>
                          <span>•</span>
                          <span>Slide Deck: {ev.require_presentation ? "Required" : "Optional"}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* 3. ADMIN VIEW                                                  */}
          {/* ============================================================== */}
          {user.role === "admin" && (
            <div className="space-y-6">
              {/* Admin Tabs */}
              <div className="flex gap-2 border-b border-border/20 pb-2 overflow-x-auto">
                {[
                  { key: "contests", label: "All Contests" },
                  { key: "users", label: "User Directory" },
                  { key: "teams", label: "Teams" },
                  { key: "submissions", label: "Submissions" },
                ].map((t) => (
                  <Button
                    key={t.key}
                    variant={activeAdminTab === t.key ? "default" : "outline"}
                    size="sm"
                    onClick={() => setActiveAdminTab(t.key as any)}
                    className="capitalize text-xs h-7 font-mono"
                  >
                    {t.label}
                  </Button>
                ))}
              </div>

              {/* Event filter dropdown for Teams and Submissions */}
              {(activeAdminTab === "teams" || activeAdminTab === "submissions") && (
                <div className="flex items-center gap-3 border-b border-border/20 pb-3">
                  <span className="text-xs text-muted-foreground font-semibold">Filter by Event:</span>
                  <select
                    className="bg-background border border-border text-xs rounded px-2.5 py-1 font-mono"
                    value={adminFilterEventId || ""}
                    onChange={(e) => setAdminFilterEventId(e.target.value ? Number(e.target.value) : null)}
                  >
                    <option value="">All Events (Global)</option>
                    {allEvents.map((ev) => (
                      <option key={ev.id} value={ev.id}>
                        {ev.title}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* TAB 1: ALL CONTESTS */}
              {activeAdminTab === "contests" && (
                <div className="space-y-4">
                  {allEvents.map((ev) => (
                    <div
                      key={ev.id}
                      className="rounded-xl border border-border/40 bg-background/80 p-5 backdrop-blur-md space-y-4"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/20 pb-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="text-base font-semibold text-foreground">{ev.title}</h3>
                            <Badge variant="outline" className="text-[10px] capitalize">
                              {ev.mode}
                            </Badge>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            Created by @{ev.created_by_username} • {ev.teams_count || 0} teams registered
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <Link href={`/events/${ev.id}`}>
                            <Button size="sm" variant="outline" className="h-7 text-xs font-mono">
                              <ExternalLink className="size-3 mr-1" /> View
                            </Button>
                          </Link>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setEditingEvent(ev)}
                            className="h-7 text-xs font-mono"
                          >
                            <Edit2 className="size-3 mr-1" /> Edit
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleDeleteEvent(ev.id)}
                            className="h-7 text-xs font-mono text-destructive hover:bg-destructive/10"
                          >
                            <Trash2 className="size-3" />
                          </Button>
                        </div>
                      </div>

                      {/* Appoint judges section */}
                      <JudgeAppointmentCombobox
                        eventId={ev.id}
                        currentJudges={ev.event_judges || []}
                        onJudgeAdded={() => loadDashboardData()}
                        onJudgeRemoved={() => loadDashboardData()}
                      />
                    </div>
                  ))}
                </div>
              )}

              {/* TAB 2: USER DIRECTORY */}
              {activeAdminTab === "users" && (
                <div className="rounded-xl border border-border/40 bg-background/80 p-4 backdrop-blur-md overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead>
                      <tr className="border-b border-border/40 text-[11px] text-muted-foreground uppercase">
                        <th className="py-2 px-3 font-normal">Username</th>
                        <th className="py-2 px-3 font-normal">Email</th>
                        <th className="py-2 px-3 font-normal">Role</th>
                        <th className="py-2 px-3 font-normal text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/20">
                      {usersList.map((u) => (
                        <tr key={u.id} className="hover:bg-muted/20">
                          <td className="py-2.5 px-3 font-medium">@{u.username}</td>
                          <td className="py-2.5 px-3 text-muted-foreground">{u.email}</td>
                          <td className="py-2.5 px-3 text-muted-foreground capitalize">
                            <Badge variant="outline" className="text-[10px] py-0">
                              {u.role}
                            </Badge>
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            {u.role !== "judge" && u.role !== "admin" ? (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleAppointPlatformJudge(u.id, u.username)}
                                className="h-6 text-[11px] font-mono hover:border-amber-500 hover:text-amber-400"
                              >
                                appoint judge
                              </Button>
                            ) : (
                              <span className="text-[11px] text-muted-foreground/60">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* TAB 3: TEAMS */}
              {activeAdminTab === "teams" && (
                <div className="rounded-xl border border-border/40 bg-background/80 p-4 backdrop-blur-md overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead>
                      <tr className="border-b border-border/40 text-[11px] text-muted-foreground uppercase">
                        <th className="py-2 px-3 font-normal">Team Name</th>
                        <th className="py-2 px-3 font-normal">Code</th>
                        <th className="py-2 px-3 font-normal">Leader</th>
                        <th className="py-2 px-3 font-normal text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/20">
                      {teamsList.map((t) => (
                        <tr key={t.id} className="hover:bg-muted/20">
                          <td className="py-2.5 px-3 font-medium">{t.name}</td>
                          <td className="py-2.5 px-3 text-muted-foreground">{t.code}</td>
                          <td className="py-2.5 px-3 text-muted-foreground">@{t.leader_username}</td>
                          <td className="py-2.5 px-3 text-right space-x-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={async () => {
                                const newName = prompt("Enter new team name:", t.name)
                                if (newName) {
                                  try {
                                    await api.updateTeamAdmin(t.id, { name: newName })
                                    setActionSuccess("Team renamed.")
                                    loadDashboardData()
                                  } catch (err: any) {
                                    setActionError(err.message)
                                  }
                                }
                              }}
                              className="h-6 text-[11px] font-mono"
                            >
                              Edit Name
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleDeleteTeam(t.id)}
                              className="h-6 text-[11px] font-mono text-destructive hover:bg-destructive/10"
                            >
                              Delete
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* TAB 4: SUBMISSIONS */}
              {activeAdminTab === "submissions" && (
                <div className="rounded-xl border border-border/40 bg-background/80 p-4 backdrop-blur-md overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead>
                      <tr className="border-b border-border/40 text-[11px] text-muted-foreground uppercase">
                        <th className="py-2 px-3 font-normal">Project Title</th>
                        <th className="py-2 px-3 font-normal">Team</th>
                        <th className="py-2 px-3 font-normal">Submitted By</th>
                        <th className="py-2 px-3 font-normal text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/20">
                      {submissionsList.map((s) => (
                        <tr key={s.id} className="hover:bg-muted/20">
                          <td className="py-2.5 px-3 font-medium">{s.title}</td>
                          <td className="py-2.5 px-3 text-muted-foreground">{s.team_name}</td>
                          <td className="py-2.5 px-3 text-muted-foreground">@{s.submitted_by_username}</td>
                          <td className="py-2.5 px-3 text-right space-x-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={async () => {
                                const newTitle = prompt("Enter new project title:", s.title)
                                if (newTitle) {
                                  try {
                                    await api.updateSubmissionAdmin(s.id, { title: newTitle })
                                    setActionSuccess("Submission updated.")
                                    loadDashboardData()
                                  } catch (err: any) {
                                    setActionError(err.message)
                                  }
                                }
                              }}
                              className="h-6 text-[11px] font-mono"
                            >
                              Edit Title
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleDeleteSubmission(s.id)}
                              className="h-6 text-[11px] font-mono text-destructive hover:bg-destructive/10"
                            >
                              Delete
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ============================================================== */}
          {/* 4. PARTICIPANT VIEW                                            */}
          {/* ============================================================== */}
          {user.role === "participant" && (
            <div className="p-8 text-center rounded-xl border border-border/40 bg-background/80 backdrop-blur-md space-y-4">
              <Trophy className="size-10 text-emerald-400 mx-auto" />
              <div className="space-y-1">
                <h2 className="text-base font-semibold text-foreground">Participant Dashboard</h2>
                <p className="text-xs text-muted-foreground max-w-md mx-auto">
                  You are registered as a participant. Browse open hackathons to form a team and submit your groundbreaking project!
                </p>
              </div>
              <div className="flex items-center justify-center gap-3 pt-2">
                <Link href="/">
                  <Button size="sm" className="h-8 text-xs font-mono bg-foreground text-background hover:bg-foreground/90">
                    Explore Hackathons
                  </Button>
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Edit Event Modal */}
      {editingEvent && (
        <EditEventModal
          event={editingEvent}
          isOpen={Boolean(editingEvent)}
          onClose={() => setEditingEvent(null)}
          onUpdated={(updated) => {
            setActionSuccess(`Event "${updated.title}" updated successfully.`)
            loadDashboardData()
          }}
        />
      )}
    </div>
  )
}
