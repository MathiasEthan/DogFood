"use client"

import React, { useState, useEffect, use } from "react"
import Link from "next/link"
import { useAuth } from "@/context/auth-context"
import { Header } from "@/components/header"
import { Squares } from "@/components/reactbits/squares"
import { api, buildInviteLink, Event as EventType, Team, ProjectSubmission } from "@/lib/api"
import { AdminEventDashboard } from "@/components/admin-event-dashboard"
import { JudgeAppointmentCombobox } from "@/components/judge-appointment-combobox"
import { EditEventModal } from "@/components/edit-event-modal"
import { CommunityVotingPanel } from "@/components/community-voting-panel"
import { JudgingProgressPanel } from "@/components/judging-progress-panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  ArrowLeft,
  Calendar,
  Globe,
  Award,
  Users,
  Copy,
  Check,
  Loader2,
  AlertCircle,
  PlusCircle,
  UserPlus,
  LogOut,
  Shield,
  Crown,
  FileCode2,
  ExternalLink,
  Presentation,
  Video,
  Layers,
  ArrowRight,
  Edit2,
  Trophy,
  Target,
  FileText,
  MapPin,
  Scale,
  BarChart3,
} from "lucide-react"

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
      <path d="M9 18c-4.51 2-5-2-7-2" />
    </svg>
  )
}

export default function EventDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const resolvedParams = use(params)
  const eventId = resolvedParams.id

  const { user } = useAuth()

  const [event, setEvent] = useState<EventType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Team Form States
  const [teamName, setTeamName] = useState("")
  const [teamCodeInput, setTeamCodeInput] = useState("")
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [copiedLink, setCopiedLink] = useState(false)
  // Invite links: /events/<id>?join=<TEAM-CODE>
  const [invite, setInvite] = useState<{
    code: string
    team_name?: string
    leader_username?: string
    member_count?: number
    max_size?: number
    is_full?: boolean
    error?: string
  } | null>(null)

  const [activeTab, setActiveTab] = useState<"create" | "join">("create")

  // Submissions roster for Organizers/Judges
  const [allSubmissions, setAllSubmissions] = useState<ProjectSubmission[]>([])
  const [isEditingModalOpen, setIsEditingModalOpen] = useState(false)


  const updateField = async (field: string, newValue: string) => {
    try {
      await api.updateEventAdmin(Number(eventId), { [field]: newValue })
      fetchEvent()
    } catch (err: any) {
      alert(err.message)
    }
  }

  const handleEditField = async (field: string, currentValue: string) => {
    const newValue = prompt(`Enter new ${field}:`, currentValue)
    if (newValue && newValue !== currentValue) {
      updateField(field, newValue)
    }
  }

  const fetchEvent = async () => {
    try {
      const data = await api.getEvent(eventId)
      setEvent(data)

      // Only this event's organizer, its judges, and admins can load the roster
      const isReviewer =
        user &&
        (user.role === "admin" ||
          data.created_by === user.id ||
          Boolean(data.event_judges?.some((j) => j.id === user.id)))

      if (isReviewer) {
        try {
          const subs = await api.listEventSubmissions(eventId)
          setAllSubmissions(subs)
        } catch {
          // ignore if unauthorized
        }
      }
    } catch (err: any) {
      setError(err.message || "Failed to load event details.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEvent()
  }, [eventId, user])

  const isCreatorOrAdmin = Boolean(user && (user.role === "admin" || user.id === event?.created_by))
  const isJudge = Boolean(user && event?.event_judges?.some((j) => j.id === user.id))
  const isReviewer = Boolean(
    user &&
      (["organizer", "judge", "admin"].includes(user.role) ||
        user.id === event?.created_by ||
        isJudge)
  )
  const totalRubricWeight = (event?.rubrics || []).reduce(
    (acc, r) => acc + (Number(r.weight) || 0),
    0
  )

  const handleCreateTeam = async (e: React.FormEvent) => {
    e.preventDefault()
    setActionError(null)
    setActionSuccess(null)
    if (!teamName.trim()) {
      setActionError("Team name cannot be empty.")
      return
    }

    setActionLoading(true)
    try {
      const res = await api.createTeam(eventId, teamName.trim())
      setActionSuccess(res.message)
      setTeamName("")
      await fetchEvent()
    } catch (err: any) {
      setActionError(err.message || "Could not create team.")
    } finally {
      setActionLoading(false)
    }
  }

  useEffect(() => {
    if (typeof window === "undefined") return
    const code = new URLSearchParams(window.location.search).get("join")
    if (!code) return
    const normalized = code.trim().toUpperCase()
    setActiveTab("join")
    setTeamCodeInput(normalized)
    api
      .lookupTeamInvite(eventId, normalized)
      .then((info) => setInvite({ ...info, code: normalized }))
      .catch((err) => setInvite({ code: normalized, error: err.message || "This invite link is invalid." }))
  }, [eventId])

  const copyInviteLink = (code: string) => {
    navigator.clipboard.writeText(buildInviteLink(eventId, code))
    setCopiedLink(true)
    setTimeout(() => setCopiedLink(false), 2000)
  }

  const clearInviteParam = () => {
    if (typeof window !== "undefined" && window.location.search.includes("join=")) {
      window.history.replaceState(null, "", window.location.pathname)
    }
    setInvite(null)
  }

  const handleJoinTeam = async (e: React.FormEvent) => {
    e.preventDefault()
    setActionError(null)
    setActionSuccess(null)
    if (!teamCodeInput.trim()) {
      setActionError("Please enter a team code.")
      return
    }

    setActionLoading(true)
    try {
      const res = await api.joinTeam(eventId, teamCodeInput.trim())
      setActionSuccess(res.message)
      setTeamCodeInput("")
      clearInviteParam()
      await fetchEvent()
    } catch (err: any) {
      setActionError(err.message || "Could not join team.")
    } finally {
      setActionLoading(false)
    }
  }

  const handleLeaveTeam = async () => {
    if (!confirm("Are you sure you want to leave this team?")) return
    setActionError(null)
    setActionSuccess(null)

    setActionLoading(true)
    try {
      const res = await api.leaveTeam(eventId)
      setActionSuccess(res.message)
      await fetchEvent()
    } catch (err: any) {
      setActionError(err.message || "Could not leave team.")
    } finally {
      setActionLoading(false)
    }
  }

  const copyTeamCode = (code: string) => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const getMediaUrl = (url: string | null) => {
    if (!url) return null
    if (url.startsWith("http")) return url
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    return `${baseUrl}${url.startsWith("/") ? url : `/${url}`}`
  }

  const getEventStatus = () => {
    if (!event) return { label: "Unknown", color: "text-muted-foreground", bg: "bg-muted/10", border: "border-border/30", dot: "bg-muted-foreground" }
    const now = new Date()
    const start = new Date(event.start_date)
    const end = new Date(event.end_date)
    if (now < start) {
      return { label: "Upcoming", color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20", dot: "bg-amber-400" }
    } else if (now > end) {
      return { label: "Concluded", color: "text-muted-foreground", bg: "bg-muted/20", border: "border-border/30", dot: "bg-muted-foreground" }
    } else {
      return { label: "Live & Ongoing", color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20", dot: "bg-emerald-400 animate-pulse" }
    }
  }

  if (loading) {
    return (
      <div className="relative min-h-screen flex flex-col bg-background font-mono select-none">
        <Header />
        <div className="flex-1 flex items-center justify-center">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin text-foreground" />
            Loading hackathon specifications...
          </div>
        </div>
      </div>
    )
  }

  if (error || !event) {
    return (
      <div className="relative min-h-screen flex flex-col bg-background font-mono select-none">
        <Header />
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="max-w-md w-full p-6 rounded-xl border border-destructive/30 bg-destructive/5 space-y-4 text-center">
            <AlertCircle className="size-8 text-destructive mx-auto" />
            <h2 className="text-sm font-semibold text-foreground">Hackathon Not Found</h2>
            <p className="text-sm text-muted-foreground">{error || "Unable to locate event record."}</p>
            <Link href="/">
              <Button size="sm" variant="outline" className="text-sm font-mono">
                <ArrowLeft className="size-3 mr-1.5" /> Return to Events
              </Button>
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const bannerUrl = getMediaUrl(event.banner)
  const eventStatus = getEventStatus()

  const now = new Date()
  const eventStart = new Date(event.start_date)
  const eventEnd = new Date(event.end_date)
  const totalDuration = eventEnd.getTime() - eventStart.getTime()
  const elapsed = now.getTime() - eventStart.getTime()
  const progressPercent = totalDuration > 0
    ? Math.min(100, Math.max(0, Math.round((elapsed / totalDuration) * 100)))
    : 0

  const milestones = (event.phases && event.phases.length > 0)
    ? event.phases.map((p, idx) => {
        const pStart = new Date(p.start_date)
        const pEnd = new Date(p.end_date)
        const isPast = now > pEnd
        const isCurrent = now >= pStart && now <= pEnd
        const isUpcoming = now < pStart
        return {
          id: p.id || idx,
          title: p.title,
          startDate: pStart,
          endDate: pEnd,
          isPast,
          isCurrent,
          isUpcoming,
        }
      })
    : []

  return (
    <div className="relative min-h-screen flex flex-col bg-background font-mono select-none overflow-hidden pb-16">
      <Header />

      <div className="relative flex-1 p-4 sm:p-8 max-w-5xl mx-auto w-full space-y-8">
        <Squares
          direction="diagonal"
          speed={0.2}
          squareSize={48}
          borderColor="rgba(255, 255, 255, 0.03)"
          hoverFillColor="rgba(255, 255, 255, 0.06)"
          className="z-0 pointer-events-none"
        />

        <div className="relative z-10 space-y-8">
          {/* Back Navigation */}
          <div>
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors group"
            >
              <ArrowLeft className="size-3.5 group-hover:-translate-x-0.5 transition-transform" />
              Back to Hackathons
            </Link>
            <Link href={`/events/${eventId}/gallery`} className="inline-flex items-center gap-1.5 text-sm text-primary hover:text-primary/80 transition-colors ml-4">
              View Public Gallery <ArrowRight className="size-3.5" />
            </Link>
          </div>

          {/* Event Header & Banner */}
          <div className="rounded-xl border border-border/40 bg-background/80 overflow-hidden backdrop-blur-md shadow-2xl">
            {bannerUrl ? (
              <div className="relative w-full h-48 sm:h-72 bg-muted/20 border-b border-border/30 overflow-hidden">
                <img
                  src={bannerUrl}
                  alt={event.title}
                  className="w-full h-full object-cover object-center"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-background/90 via-background/20 to-transparent" />
              </div>
            ) : null}

            <div className="p-6 sm:p-8 space-y-6">
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  {/* Event Live Status Badge */}
                  <Badge variant="outline" className={`font-mono text-[10px] uppercase tracking-wider py-0.5 px-2.5 ${eventStatus.color} ${eventStatus.bg} ${eventStatus.border}`}>
                    <span className={`size-1.5 rounded-full mr-1.5 ${eventStatus.dot}`} />
                    {eventStatus.label}
                  </Badge>

                  {/* Event Mode Badge */}
                  <Badge variant="outline" className="font-mono text-[10px] uppercase tracking-wider py-0.5 px-2.5 text-foreground bg-muted/20 border-border/40 flex items-center gap-1">
                    {event.mode === "virtual" ? <Globe className="size-3" /> : <MapPin className="size-3" />}
                    {event.mode.replace("_", " ")}
                    {user?.role === "admin" && (
                      <button
                        onClick={() => {
                          const newMode = prompt("Enter new mode (virtual, in_person, hybrid):", event.mode)
                          if (newMode && ["virtual", "in_person", "hybrid"].includes(newMode) && newMode !== event.mode) {
                            updateField("mode", newMode)
                          } else if (newMode && !["virtual", "in_person", "hybrid"].includes(newMode)) {
                            alert("Invalid mode. Must be virtual, in_person, or hybrid.")
                          }
                        }}
                        className="ml-1 text-muted-foreground hover:text-foreground"
                      >
                        <Edit2 className="size-3" />
                      </button>
                    )}
                  </Badge>

                  {/* Max Team Size Badge */}
                  <Badge variant="outline" className="font-mono text-[10px] text-muted-foreground py-0.5 px-2 bg-muted/20 border-border/30 flex items-center gap-1">
                    <Users className="size-3" /> Max Team Size: {event.max_team_size}
                    {user?.role === "admin" && (
                      <button
                        onClick={() => {
                          const newSize = prompt("Enter new max team size:", event.max_team_size.toString())
                          if (newSize && !isNaN(Number(newSize)) && newSize !== event.max_team_size.toString()) {
                            updateField("max_team_size", newSize)
                          }
                        }}
                        className="ml-1 text-muted-foreground hover:text-foreground"
                      >
                        <Edit2 className="size-3" />
                      </button>
                    )}
                  </Badge>

                  {/* Teams Registered Badge */}
                  <Badge variant="outline" className="font-mono text-[10px] text-muted-foreground py-0.5 px-2 bg-muted/20 border-border/30">
                    {event.teams_count || 0} {event.teams_count === 1 ? "Team" : "Teams"} Registered
                  </Badge>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h1 className="text-2xl sm:text-3xl font-light tracking-tight text-foreground flex items-center gap-2">
                    {event.title}
                  </h1>
                  {user && (user.role === "admin" || user.id === event.created_by) && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setIsEditingModalOpen(true)}
                      className="h-7 text-xs font-mono hover:border-primary hover:text-primary"
                    >
                      <Edit2 className="size-3 mr-1" /> Edit Contest
                    </Button>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground font-mono">
                  <span>
                    Organized by <span className="text-foreground font-medium">@{event.created_by_username}</span>
                  </span>
                  {event.created_at && (
                    <span>• Created {new Date(event.created_at).toLocaleDateString()}</span>
                  )}
                </div>
              </div>

              {/* Event Metadata Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2">
                <div className="p-3.5 rounded-lg border border-border/30 bg-muted/10 space-y-1">
                  <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                    <Calendar className="size-3" /> Timeline
                  </div>
                  <div className="text-sm text-foreground font-medium flex items-center justify-between">
                    <span className="truncate">
                      {new Date(event.start_date).toLocaleDateString()} – {new Date(event.end_date).toLocaleDateString()}
                    </span>
                    {user?.role === "admin" && (
                      <button
                        onClick={() => {
                          const newStart = prompt("Enter new start date (YYYY-MM-DD or YYYY-MM-DDTHH:MM):", event.start_date)
                          if (newStart && newStart !== event.start_date) updateField("start_date", newStart)
                          const newEnd = prompt("Enter new end date (YYYY-MM-DD or YYYY-MM-DDTHH:MM):", event.end_date)
                          if (newEnd && newEnd !== event.end_date) updateField("end_date", newEnd)
                        }}
                        className="text-muted-foreground hover:text-primary ml-1"
                      >
                        <Edit2 className="size-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                <div className="p-3.5 rounded-lg border border-border/30 bg-muted/10 space-y-1">
                  <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                    <Globe className="size-3" /> Venue / Location
                  </div>
                  <div className="text-sm text-foreground font-medium truncate flex items-center justify-between">
                    <span className="truncate">{event.location || (event.mode === "virtual" ? "Virtual / Online" : "TBD")}</span>
                    {user?.role === "admin" && (
                      <button
                        onClick={() => handleEditField("location", event.location)}
                        className="text-muted-foreground hover:text-primary ml-1"
                      >
                        <Edit2 className="size-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                <div className="p-3.5 rounded-lg border border-border/30 bg-muted/10 space-y-1">
                  <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                    <Award className="size-3" /> Total Prize Pool
                  </div>
                  <div className="text-sm text-emerald-400 font-semibold truncate flex items-center justify-between">
                    <span className="truncate">{event.prize_pool || "Non-monetary / Certificates"}</span>
                    {user?.role === "admin" && (
                      <button
                        onClick={() => handleEditField("prize_pool", event.prize_pool)}
                        className="text-muted-foreground hover:text-primary ml-1"
                      >
                        <Edit2 className="size-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                <div className="p-3.5 rounded-lg border border-border/30 bg-muted/10 space-y-1">
                  <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                    <Users className="size-3" /> Team Structure
                  </div>
                  <div className="text-sm text-foreground font-medium truncate">
                    <span>Up to {event.max_team_size} members / team</span>
                  </div>
                </div>
              </div>

              {/* Description */}
              <div className="space-y-2 border-t border-border/30 pt-6">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground flex items-center gap-2">
                  Event Brief & Objectives
                  {user?.role === "admin" && (
                    <button
                      onClick={() => handleEditField("description", event.description)}
                      className="text-muted-foreground hover:text-primary"
                    >
                      <Edit2 className="size-3.5" />
                    </button>
                  )}
                </h3>
                <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap font-sans">
                  {event.description}
                </p>
              </div>

              {/* Competition Tracks */}
              {event.tracks && event.tracks.length > 0 && (
                <div className="space-y-3 border-t border-border/30 pt-6">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground flex items-center gap-2">
                      <Target className="size-4 text-primary" />
                      Competition Tracks ({event.tracks.length})
                    </h3>
                    <span className="text-[11px] text-muted-foreground font-mono">
                      Challenge Categories
                    </span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {event.tracks.map((track, idx) => (
                      <div
                        key={track.id || idx}
                        className="p-4 rounded-lg border border-border/30 bg-muted/10 hover:border-border/60 transition-colors space-y-2"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <h4 className="text-xs sm:text-sm font-semibold text-foreground flex items-center gap-2">
                            <span className="text-[10px] font-mono text-muted-foreground bg-muted/30 px-1.5 py-0.5 rounded border border-border/30">
                              Track {idx + 1}
                            </span>
                            {track.title}
                          </h4>
                        </div>
                        {track.description && (
                          <p className="text-xs text-muted-foreground leading-relaxed font-sans">
                            {track.description}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Prizes & Awards Breakdown */}
              {event.prizes && event.prizes.length > 0 && (
                <div className="space-y-3 border-t border-border/30 pt-6">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground flex items-center gap-2">
                      <Trophy className="size-4 text-emerald-400" />
                      Prizes & Recognition ({event.prizes.length})
                    </h3>
                    {event.prize_pool && (
                      <Badge variant="outline" className="font-mono text-[10px] text-emerald-400 border-emerald-500/30 bg-emerald-500/10">
                        Total Pool: {event.prize_pool}
                      </Badge>
                    )}
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {event.prizes.map((prize, idx) => (
                      <div
                        key={prize.id || idx}
                        className="p-4 rounded-lg border border-border/30 bg-muted/10 hover:border-emerald-500/30 transition-colors space-y-2 relative overflow-hidden"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider block">
                              Award Tier #{idx + 1}
                            </span>
                            <h4 className="text-xs sm:text-sm font-semibold text-foreground mt-0.5">
                              {prize.title}
                            </h4>
                          </div>
                          <div className="size-7 rounded-md bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
                            <Award className="size-4" />
                          </div>
                        </div>
                        <div className="text-base sm:text-lg font-bold font-mono text-emerald-400">
                          {prize.amount}
                        </div>
                        {prize.description && (
                          <p className="text-xs text-muted-foreground leading-relaxed font-sans pt-1 border-t border-border/20">
                            {prize.description}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Event Timeline & Phases Graph */}
              {milestones.length > 0 && (
                <div className="space-y-4 border-t border-border/30 pt-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Layers className="size-4 text-primary" />
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground">
                        Event Timeline & Phases Graph
                      </h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="font-mono text-[10px] text-muted-foreground border-border/40 bg-muted/20">
                      {progressPercent}% Complete
                    </Badge>
                    {event.phases && event.phases.length > 0 && (
                      <span className="text-[11px] text-muted-foreground font-mono hidden sm:inline">
                        {event.phases.length} Phases
                      </span>
                    )}
                  </div>
                </div>

                {/* Desktop Horizontal Graph View */}
                <div className="hidden md:block space-y-4 pt-1">
                  {/* Timeline progress line */}
                  <div className="relative">
                    <div className="h-1.5 w-full rounded-full bg-muted/20 overflow-hidden border border-border/20">
                      <div
                        className="h-full bg-gradient-to-r from-emerald-500/70 to-emerald-400 rounded-full transition-all duration-500"
                        style={{ width: `${progressPercent}%` }}
                      />
                    </div>
                  </div>

                  {/* Connected Nodes Pipeline */}
                  <div className="relative pt-4 pb-2">
                    <div
                      className="grid gap-3"
                      style={{
                        gridTemplateColumns: `repeat(${milestones.length}, minmax(0, 1fr))`,
                      }}
                    >
                      {milestones.map((m, idx) => {
                        const isLast = idx === milestones.length - 1
                        return (
                          <div key={m.id} className="relative flex flex-col items-center text-center px-1 group">
                            {/* Connecting track to next node */}
                            {!isLast && (
                              <div
                                className={`absolute top-4 left-1/2 w-full h-0.5 z-0 transition-colors ${
                                  m.isPast
                                    ? "bg-emerald-500/60"
                                    : m.isCurrent
                                    ? "bg-gradient-to-r from-emerald-500/60 to-border/40"
                                    : "bg-border/40 border-t border-dashed border-border/60"
                                }`}
                              />
                            )}

                            {/* Node Marker */}
                            <div className="relative z-10 mb-3 flex items-center justify-center">
                              {m.isCurrent ? (
                                <div className="relative flex items-center justify-center">
                                  <span className="absolute -inset-1.5 rounded-full border border-emerald-400 animate-ping opacity-60" />
                                  <div className="size-8 rounded-full bg-background border-2 border-emerald-400 flex items-center justify-center text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.4)]">
                                    <span className="size-2.5 rounded-full bg-emerald-400 animate-pulse" />
                                  </div>
                                </div>
                              ) : m.isPast ? (
                                <div className="size-8 rounded-full bg-emerald-500/10 border-2 border-emerald-500/60 flex items-center justify-center text-emerald-400">
                                  <Check className="size-4 stroke-[3]" />
                                </div>
                              ) : (
                                <div className="size-8 rounded-full bg-muted/20 border-2 border-border/50 flex items-center justify-center text-[11px] font-mono text-muted-foreground">
                                  0{idx + 1}
                                </div>
                              )}
                            </div>

                            {/* Milestone Card */}
                            <div
                              className={`w-full p-3 rounded-lg border transition-all space-y-1.5 ${
                                m.isCurrent
                                  ? "border-emerald-500/40 bg-emerald-500/10 shadow-xs ring-1 ring-emerald-500/20"
                                  : m.isPast
                                  ? "border-border/30 bg-muted/5 opacity-85 hover:opacity-100"
                                  : "border-border/20 bg-muted/10"
                              }`}
                            >
                              <div className="flex items-center justify-center">
                                {m.isCurrent ? (
                                  <Badge
                                    variant="outline"
                                    className="text-[9px] uppercase tracking-wider text-emerald-400 border-emerald-500/30 bg-emerald-500/10 py-0 px-1.5"
                                  >
                                    Active Now
                                  </Badge>
                                ) : m.isPast ? (
                                  <Badge
                                    variant="outline"
                                    className="text-[9px] uppercase tracking-wider text-muted-foreground border-border/30 py-0 px-1.5"
                                  >
                                    Completed
                                  </Badge>
                                ) : (
                                  <Badge
                                    variant="outline"
                                    className="text-[9px] uppercase tracking-wider text-amber-400 border-amber-500/30 bg-amber-500/10 py-0 px-1.5"
                                  >
                                    Upcoming
                                  </Badge>
                                )}
                              </div>

                              <div className="text-xs font-semibold text-foreground truncate" title={m.title}>
                                {m.title}
                              </div>

                              <div className="text-[10px] text-muted-foreground font-mono leading-tight">
                                <div>{m.startDate.toLocaleDateString(undefined, { month: "short", day: "numeric" })}</div>
                                {m.startDate.toDateString() !== m.endDate.toDateString() && (
                                  <div className="text-[9px] text-muted-foreground/80">
                                    to {m.endDate.toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>

                {/* Mobile Vertical Connected Track View */}
                <div className="block md:hidden space-y-4 pt-1">
                  {/* Progress Line */}
                  <div className="h-1.5 w-full rounded-full bg-muted/20 overflow-hidden border border-border/20">
                    <div
                      className="h-full bg-gradient-to-r from-emerald-500/70 to-emerald-400 rounded-full"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>

                  <div className="relative pl-6 space-y-4 border-l-2 border-border/30 ml-3">
                    {milestones.map((m, idx) => (
                      <div key={m.id} className="relative group">
                        {/* Track node dot */}
                        <div
                          className={`absolute -left-[31px] top-1.5 size-4 rounded-full border-2 bg-background flex items-center justify-center ${
                            m.isCurrent
                              ? "border-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.5)]"
                              : m.isPast
                              ? "border-emerald-500/60 bg-emerald-500/20"
                              : "border-border/60"
                          }`}
                        >
                          {m.isCurrent && <span className="size-1.5 rounded-full bg-emerald-400 animate-ping" />}
                        </div>

                        {/* Card */}
                        <div
                          className={`p-3 rounded-lg border space-y-1.5 ${
                            m.isCurrent
                              ? "border-emerald-500/40 bg-emerald-500/10"
                              : m.isPast
                              ? "border-border/30 bg-muted/5 opacity-85"
                              : "border-border/20 bg-muted/10"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-semibold text-foreground">
                              {m.title}
                            </span>
                            {m.isCurrent ? (
                              <Badge
                                variant="outline"
                                className="text-[9px] uppercase tracking-wider text-emerald-400 border-emerald-500/30 bg-emerald-500/10 py-0 px-1.5"
                              >
                                Active
                              </Badge>
                            ) : m.isPast ? (
                              <Badge
                                variant="outline"
                                className="text-[9px] uppercase tracking-wider text-muted-foreground border-border/30 py-0 px-1.5"
                              >
                                Completed
                              </Badge>
                            ) : (
                              <Badge
                                variant="outline"
                                className="text-[9px] uppercase tracking-wider text-amber-400 border-amber-500/30 bg-amber-500/10 py-0 px-1.5"
                              >
                                Upcoming
                              </Badge>
                            )}
                          </div>
                          <div className="text-[11px] text-muted-foreground font-mono flex items-center gap-1.5">
                            <Calendar className="size-3" />
                            {m.startDate.toLocaleDateString()} – {m.endDate.toLocaleDateString()}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Submission Deliverables & Requirements */}
              <div className="space-y-4 border-t border-border/30 pt-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground flex items-center gap-2">
                    <FileCode2 className="size-4 text-primary" />
                    Submission Deliverables & Requirements
                  </h3>
                  <span className="text-[11px] text-muted-foreground font-mono">
                    Evaluation Criteria
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {/* GitHub Deliverable */}
                  <div className="p-3.5 rounded-lg border border-border/30 bg-muted/10 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <GithubIcon className="size-4 text-foreground shrink-0" />
                      <div>
                        <div className="text-xs font-semibold text-foreground">GitHub Repo</div>
                        <div className="text-[10px] text-muted-foreground">Source code repository</div>
                      </div>
                    </div>
                    {event.require_github_url ? (
                      <Badge variant="outline" className="text-[10px] text-emerald-400 border-emerald-500/30 bg-emerald-500/10">
                        Required
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px] text-muted-foreground border-border/40">
                        Optional
                      </Badge>
                    )}
                  </div>

                  {/* Demo Deliverable */}
                  <div className="p-3.5 rounded-lg border border-border/30 bg-muted/10 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <Video className="size-4 text-primary shrink-0" />
                      <div>
                        <div className="text-xs font-semibold text-foreground">Demo / Video</div>
                        <div className="text-[10px] text-muted-foreground">Live app or video link</div>
                      </div>
                    </div>
                    {event.require_demo_url ? (
                      <Badge variant="outline" className="text-[10px] text-emerald-400 border-emerald-500/30 bg-emerald-500/10">
                        Required
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px] text-muted-foreground border-border/40">
                        Optional
                      </Badge>
                    )}
                  </div>

                  {/* Presentation Deliverable */}
                  <div className="p-3.5 rounded-lg border border-border/30 bg-muted/10 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <Presentation className="size-4 text-amber-400 shrink-0" />
                      <div>
                        <div className="text-xs font-semibold text-foreground">Slide Deck</div>
                        <div className="text-[10px] text-muted-foreground">Slides URL or PDF</div>
                      </div>
                    </div>
                    {event.require_presentation ? (
                      <Badge variant="outline" className="text-[10px] text-emerald-400 border-emerald-500/30 bg-emerald-500/10">
                        Required
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px] text-muted-foreground border-border/40">
                        Optional
                      </Badge>
                    )}
                  </div>
                </div>

                {/* Submission Guidelines & Rules */}
                {event.submission_guidelines && (
                  <div className="p-4 rounded-lg border border-border/30 bg-muted/10 space-y-2">
                    <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                      <FileText className="size-3.5" />
                      Organizer Guidelines & Evaluation Rubric
                      {user?.role === "admin" && (
                        <button
                          onClick={() => handleEditField("submission_guidelines", event.submission_guidelines || "")}
                          className="text-muted-foreground hover:text-primary ml-1"
                        >
                          <Edit2 className="size-3" />
                        </button>
                      )}
                    </div>
                    <p className="text-xs text-foreground/90 whitespace-pre-wrap leading-relaxed font-sans">
                      {event.submission_guidelines}
                    </p>
                  </div>
                )}
              </div>

              {/* Judges / Evaluation Panel */}
              {(isCreatorOrAdmin || isJudge || (event.event_judges && event.event_judges.length > 0) || (event.rubrics && event.rubrics.length > 0)) && (
                <div className="space-y-6 border-t border-border/30 pt-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground flex items-center gap-2">
                        <Scale className="size-4 text-primary" />
                        Judging & Evaluation System
                      </h3>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        Scoring criteria, appointed judges, and evaluation standings
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      {isCreatorOrAdmin && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setIsEditingModalOpen(true)}
                          className="h-7 text-xs border-border/40 hover:border-primary/50 text-foreground"
                        >
                          <Edit2 className="size-3 mr-1.5" />
                          Edit Rubrics
                        </Button>
                      )}
                      <Link
                        href={`/events/${eventId}/gallery`}
                        className="inline-flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 transition-colors font-mono py-1 px-2.5 rounded-md border border-primary/20 bg-primary/5 hover:bg-primary/10"
                      >
                        <BarChart3 className="size-3" />
                        Leaderboard & Projects
                        <ArrowRight className="size-3" />
                      </Link>
                    </div>
                  </div>

                  {/* Appointed Judges */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="text-[11px] font-mono font-medium text-muted-foreground uppercase flex items-center gap-1.5">
                        <Shield className="size-3 text-primary" />
                        Appointed Judges ({event.event_judges?.length || 0})
                      </div>
                      <span className="text-[10px] text-muted-foreground font-mono">
                        {isCreatorOrAdmin ? "Organizer Controls" : "Evaluation Board"}
                      </span>
                    </div>

                    {isCreatorOrAdmin ? (
                      <div className="p-4 rounded-lg border border-border/40 bg-muted/10 space-y-3">
                        <p className="text-[11px] text-muted-foreground">
                          Search and appoint judges for this contest from registered platform users:
                        </p>
                        <JudgeAppointmentCombobox
                          eventId={event.id}
                          currentJudges={event.event_judges || []}
                          onJudgeAdded={() => fetchEvent()}
                          onJudgeRemoved={() => fetchEvent()}
                        />
                      </div>
                    ) : event.event_judges && event.event_judges.length > 0 ? (
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                        {event.event_judges.map((judge) => (
                          <div
                            key={judge.id}
                            className="p-3 rounded-lg border border-border/30 bg-muted/10 flex items-center gap-3"
                          >
                            <Avatar className="size-8 border border-border/40">
                              <AvatarFallback className="text-[11px] font-mono font-semibold uppercase bg-muted/50">
                                {judge.username.slice(0, 2)}
                              </AvatarFallback>
                            </Avatar>
                            <div className="min-w-0 flex-1">
                              <div className="text-xs font-semibold text-foreground truncate">
                                @{judge.username}
                              </div>
                              <div className="text-[10px] text-muted-foreground font-mono flex items-center gap-1">
                                <Shield className="size-2.5 text-primary" /> Judge
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-3 rounded-lg border border-border/20 bg-muted/5 text-xs text-muted-foreground font-mono">
                        No external judges appointed yet. Evaluations are handled by event organizers.
                      </div>
                    )}
                  </div>

                  {/* Rubrics & Scoring Criteria */}
                  <div className="space-y-3 pt-2">
                    <div className="flex items-center justify-between">
                      <div className="text-[11px] font-mono font-medium text-muted-foreground uppercase flex items-center gap-1.5">
                        <Target className="size-3 text-primary" />
                        Scoring Rubrics & Weightage ({event.rubrics?.length || 0})
                      </div>
                      {event.rubrics && event.rubrics.length > 0 && (
                        <div className="flex items-center gap-2">
                          <Badge
                            variant="outline"
                            className={`font-mono text-[10px] ${
                              Math.round(totalRubricWeight) === 100
                                ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
                                : "text-amber-400 border-amber-500/30 bg-amber-500/10"
                            }`}
                          >
                            Total Weight: {totalRubricWeight}%
                          </Badge>
                          <Badge variant="outline" className="font-mono text-[10px] text-primary border-primary/30 bg-primary/10">
                            Max mark set per rubric
                          </Badge>
                        </div>
                      )}
                    </div>

                    {event.rubrics && event.rubrics.length > 0 ? (
                      <div className="space-y-3">
                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                          {event.rubrics.map((rubric, idx) => (
                            <div
                              key={rubric.id || idx}
                              className="p-3.5 rounded-lg border border-border/30 bg-muted/10 hover:border-border/60 transition-colors space-y-2 flex flex-col justify-between"
                            >
                              <div className="space-y-1.5">
                                <div className="flex items-start justify-between gap-2">
                                  <h4 className="text-xs font-semibold text-foreground leading-snug">
                                    {rubric.title}
                                  </h4>
                                  <Badge
                                    variant="outline"
                                    className="font-mono text-[10px] text-primary border-primary/30 bg-primary/10 shrink-0"
                                  >
                                    {rubric.weight}%
                                  </Badge>
                                </div>
                                {rubric.description && (
                                  <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-3">
                                    {rubric.description}
                                  </p>
                                )}
                              </div>
                              <div className="pt-2 border-t border-border/20 flex items-center justify-between text-[10px] font-mono text-muted-foreground">
                                <span>Max mark: {rubric.max_score ?? 10}</span>
                                <span className="text-foreground/70">
                                  Weight: {rubric.weight}%
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>

                        {/* Weighted formula explanation */}
                        <div className="p-3 rounded-lg border border-primary/20 bg-primary/5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-[10px] text-primary font-bold px-1.5 py-0.5 rounded bg-primary/10 border border-primary/20">
                              FORMULA
                            </span>
                            <span className="text-foreground/80 font-mono text-[11px]">
                              Total = &Sigma; (Mark / Max &times; 10 &times; Weight share) &bull; Range: 1.0 – 10.0 &bull; then normalized across judges
                            </span>
                          </div>
                          {(isReviewer || isJudge) && (
                            <Link
                              href={`/events/${eventId}/gallery`}
                              className="inline-flex items-center gap-1 text-[11px] font-mono text-primary hover:underline font-semibold"
                            >
                              Evaluate Projects Now &rarr;
                            </Link>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="p-4 rounded-lg border border-border/30 bg-muted/5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                        <div className="text-xs text-muted-foreground">
                          {isCreatorOrAdmin
                            ? "No custom rubrics configured yet. Add weighted rubrics (1-10 scale) so judges can evaluate submissions objectively."
                            : "Standard 1-10 overall scoring applied by the judging panel."}
                        </div>
                        {isCreatorOrAdmin && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setIsEditingModalOpen(true)}
                            className="text-xs font-mono h-7 border-border/40 hover:border-primary/50"
                          >
                            <PlusCircle className="size-3 mr-1.5" />
                            Configure Rubrics
                          </Button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Feedback Banners */}
          {actionError && (
            <div className="p-3.5 rounded-lg border border-destructive/40 bg-destructive/10 text-sm text-destructive flex items-center gap-2">
              <AlertCircle className="size-4 shrink-0" />
              <span>{actionError}</span>
            </div>
          )}
          {actionSuccess && (
            <div className="p-3.5 rounded-lg border border-emerald-500/40 bg-emerald-500/10 text-sm text-emerald-400 flex items-center gap-2">
              <Check className="size-4 shrink-0" />
              <span>{actionSuccess}</span>
            </div>
          )}

          {/* 1. PARTICIPATION & TEAM PORTAL */}
          <div className="rounded-xl border border-border/40 bg-background/80 p-6 sm:p-8 backdrop-blur-md shadow-2xl space-y-6">
            <div className="flex items-center justify-between border-b border-border/30 pb-4">
              <div>
                <h2 className="text-sm font-semibold text-foreground tracking-wide uppercase">
                  Participation & Team Formation
                </h2>
                <p className="text-sm text-muted-foreground">
                  Form a team with friends using a shareable team code
                </p>
              </div>

              {event.my_team && (
                <span className="text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded font-mono">
                  Registered
                </span>
              )}
            </div>

            {event.my_team ? (
              /* SCENARIO A: PARTICIPANT IS IN A TEAM */
              <div className="space-y-6">
                <div className="p-5 rounded-lg border border-border/40 bg-muted/10 space-y-5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                      <span className="text-[10px] text-muted-foreground uppercase tracking-widest">
                        Your Registered Team
                      </span>
                      <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
                        {event.my_team.name}
                        {event.my_team.leader === user?.id && (
                          <span className="text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded font-mono flex items-center gap-1 font-normal">
                            <Crown className="size-3" /> Team Leader
                          </span>
                        )}
                      </h3>
                    </div>

                    {/* Shareable Team Code */}
                    <div className="flex items-center gap-2">
                      <div className="text-sm font-mono bg-background/80 border border-border/60 px-3 py-1.5 rounded-md text-foreground flex items-center gap-2">
                        <span className="text-muted-foreground text-[10px] uppercase">Team Code:</span>
                        <span className="font-bold tracking-wider text-emerald-400">{event.my_team.code}</span>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => copyTeamCode(event.my_team!.code)}
                        className="h-8 text-sm font-mono gap-1.5"
                      >
                        {copied ? <Check className="size-3 text-emerald-400" /> : <Copy className="size-3" />}
                        {copied ? "Copied" : "Copy Code"}
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => copyInviteLink(event.my_team!.code)}
                        className="h-8 text-sm font-mono gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white"
                      >
                        {copiedLink ? <Check className="size-3" /> : <UserPlus className="size-3" />}
                        {copiedLink ? "Link copied" : "Copy Invite Link"}
                      </Button>
                    </div>
                  </div>

                  {/* Team Members Roster */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <span>Roster ({event.my_team.members.length} / {event.max_team_size} members)</span>
                      <span>
                        {event.max_team_size - event.my_team.members.length} slot(s) remaining
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {event.my_team.members.map((m) => (
                        <div
                          key={m.id}
                          className="flex items-center justify-between p-2.5 rounded-md border border-border/40 bg-muted/20 text-sm"
                        >
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-foreground">@{m.username}</span>
                            {m.is_leader && (
                              <span className="inline-flex items-center gap-0.5 text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.2 rounded">
                                <Crown className="size-2.5" /> Leader
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] text-muted-foreground">
                            joined {new Date(m.joined_at).toLocaleDateString()}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* PROJECT SUBMISSION ACTION CALLOUT */}
                  <div className="p-4 rounded-lg border border-border/50 bg-background/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <FileCode2 className="size-4 text-emerald-400" />
                        <span className="text-sm font-semibold text-foreground uppercase tracking-wide">
                          Project Submission Portal
                        </span>
                        {event.my_team.submission ? (
                          <span className="text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded font-mono">
                            Delivered
                          </span>
                        ) : (
                          <span className="text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded font-mono">
                            Pending Submission
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-muted-foreground">
                        {event.my_team.submission
                          ? `Project: "${event.my_team.submission.title}" — view deliverables or update before deadline`
                          : "Prepare and submit your team's project, repository links, slides, and demo"}
                      </p>
                    </div>

                    <Link href={`/events/${eventId}/${event.my_team.code}`}>
                      <Button size="sm" className="text-sm font-mono bg-foreground text-background hover:bg-foreground/90 gap-1.5 w-full sm:w-auto">
                        <span>{event.my_team.submission ? "Manage Submission" : "Submit Project"}</span>
                        <ArrowRight className="size-3.5" />
                      </Button>
                    </Link>
                  </div>

                  <div className="pt-2 flex justify-end">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleLeaveTeam}
                      disabled={actionLoading}
                      className="text-sm text-destructive hover:bg-destructive/10 hover:border-destructive/30"
                    >
                      <LogOut className="size-3.5 mr-1" />
                      Leave Team
                    </Button>
                  </div>
                </div>
              </div>
            ) : user && (user.id === event.created_by || isJudge) ? (
              <div className="p-4 rounded-lg border border-border/40 bg-muted/10 text-sm text-muted-foreground">
                You are {user.id === event.created_by ? "the organizer" : "a judge"} of this event, so you can&apos;t join or
                create a team in it (conflict of interest).
              </div>
            ) : user ? (
              /* SCENARIO B: LOGGED IN PARTICIPANT WITHOUT A TEAM */
              <div className="space-y-4">
                {invite && (
                  <div
                    className={`p-4 rounded-lg border text-sm ${
                      invite.error || invite.is_full
                        ? "border-destructive/30 bg-destructive/5"
                        : "border-emerald-500/40 bg-emerald-500/10"
                    }`}
                  >
                    {invite.error ? (
                      <span className="text-destructive">{invite.error}</span>
                    ) : (
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div>
                          <div className="font-semibold text-foreground">
                            You&apos;ve been invited to join <span className="text-emerald-400">{invite.team_name}</span>
                          </div>
                          <div className="text-[11px] text-muted-foreground font-mono">
                            Led by @{invite.leader_username} · {invite.member_count}/{invite.max_size} members
                            {invite.is_full ? " · team is full" : ""}
                          </div>
                        </div>
                        {!invite.is_full && (
                          <Button
                            size="sm"
                            disabled={actionLoading}
                            onClick={(e) => handleJoinTeam(e as unknown as React.FormEvent)}
                            className="h-8 text-sm font-mono bg-emerald-600 hover:bg-emerald-500 text-white"
                          >
                            {actionLoading ? <Loader2 className="size-3.5 animate-spin mr-1.5" /> : <UserPlus className="size-3.5 mr-1.5" />}
                            Accept &amp; Join
                          </Button>
                        )}
                      </div>
                    )}
                  </div>
                )}
                <div className="grid grid-cols-2 gap-2 border-b border-border/40 pb-3">
                  <button
                    type="button"
                    onClick={() => setActiveTab("create")}
                    className={`flex items-center justify-center gap-2 py-2 text-sm font-mono transition-colors rounded-md ${
                      activeTab === "create"
                        ? "bg-foreground text-background font-semibold"
                        : "text-muted-foreground hover:bg-muted/20"
                    }`}
                  >
                    <PlusCircle className="size-3.5" />
                    <span>Create a Team</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveTab("join")}
                    className={`flex items-center justify-center gap-2 py-2 text-sm font-mono transition-colors rounded-md ${
                      activeTab === "join"
                        ? "bg-foreground text-background font-semibold"
                        : "text-muted-foreground hover:bg-muted/20"
                    }`}
                  >
                    <UserPlus className="size-3.5" />
                    <span>Join with Team Code</span>
                  </button>
                </div>

                {activeTab === "create" ? (
                  <form onSubmit={handleCreateTeam} className="space-y-3.5 max-w-md pt-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="teamName" className="text-[11px] text-muted-foreground uppercase tracking-wider">
                        Team Name
                      </Label>
                      <Input
                        id="teamName"
                        type="text"
                        required
                        value={teamName}
                        onChange={(e) => setTeamName(e.target.value)}
                        placeholder="e.g. CyberPunks, CodeCrafters"
                        className="h-9 text-sm font-mono bg-muted/20 border-border/40"
                      />
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      Creating a team makes you the team leader and generates a shareable team code.
                    </p>
                    <Button
                      type="submit"
                      disabled={actionLoading}
                      className="h-8 text-sm font-mono bg-foreground text-background hover:bg-foreground/90 font-medium"
                    >
                      {actionLoading ? <Loader2 className="size-3.5 animate-spin mr-1.5" /> : null}
                      Create Team & Generate Code
                    </Button>
                  </form>
                ) : (
                  <form onSubmit={handleJoinTeam} className="space-y-3.5 max-w-md pt-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="teamCode" className="text-[11px] text-muted-foreground uppercase tracking-wider">
                        Enter Team Code
                      </Label>
                      <Input
                        id="teamCode"
                        type="text"
                        required
                        value={teamCodeInput}
                        onChange={(e) => setTeamCodeInput(e.target.value.toUpperCase())}
                        placeholder="e.g. HACK-9A2B"
                        className="h-9 text-sm font-mono uppercase bg-muted/20 border-border/40 tracking-wider"
                      />
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      Ask your team leader for their team code and paste it above to join.
                    </p>
                    <Button
                      type="submit"
                      disabled={actionLoading}
                      className="h-8 text-sm font-mono bg-foreground text-background hover:bg-foreground/90 font-medium"
                    >
                      {actionLoading ? <Loader2 className="size-3.5 animate-spin mr-1.5" /> : null}
                      Join Team
                    </Button>
                  </form>
                )}
              </div>
            ) : (
              /* SCENARIO C: UNAUTHENTICATED */
              <div className="p-6 rounded-lg border border-border/40 bg-muted/10 text-center space-y-3">
                <p className="text-sm text-muted-foreground">
                  {invite && !invite.error
                    ? `You've been invited to join ${invite.team_name}. Sign in or register to accept.`
                    : "Sign in or create an account to form or join a team for this hackathon."}
                </p>
                <div className="flex items-center justify-center gap-3">
                  <Link href={invite ? `/login?next=${encodeURIComponent(`/events/${eventId}?join=${invite.code}`)}` : "/login"}>
                    <Button size="sm" variant="outline" className="text-sm font-mono">
                      Sign In
                    </Button>
                  </Link>
                  <Link href={invite ? `/register?next=${encodeURIComponent(`/events/${eventId}?join=${invite.code}`)}` : "/register"}>
                    <Button size="sm" className="text-sm font-mono bg-foreground text-background">
                      Register
                    </Button>
                  </Link>
                </div>
              </div>
            )}
          </div>

          {/* 2. ORGANIZER / JUDGE SUBMISSIONS EVALUATION ROSTER */}
          {allSubmissions.length > 0 && (
            <div className="rounded-xl border border-border/40 bg-background/80 p-6 sm:p-8 backdrop-blur-md shadow-2xl space-y-4">
              <div className="flex items-center gap-2 border-b border-border/30 pb-3">
                <Award className="size-4 text-primary" />
                <h3 className="text-sm font-semibold uppercase tracking-wider text-foreground">
                  Submitted Projects Roster ({allSubmissions.length} projects)
                </h3>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {allSubmissions.map((sub) => (
                  <div
                    key={sub.id}
                    className="p-4 rounded-lg border border-border/40 bg-muted/10 space-y-3 text-sm"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-foreground">{sub.title}</span>
                      <span className="text-[10px] text-muted-foreground font-mono bg-muted/30 px-2 py-0.5 rounded">
                        Team: {sub.team_name}
                      </span>
                    </div>
                    <p className="text-[11px] text-muted-foreground italic line-clamp-2">
                      &quot;{sub.tagline}&quot;
                    </p>
                    <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-border/20">
                      {sub.github_url && (
                        <a
                          href={sub.github_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-[11px] text-foreground hover:underline"
                        >
                          <GithubIcon className="size-3" /> repo
                        </a>
                      )}
                      {sub.demo_url && (
                        <a
                          href={sub.demo_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
                        >
                          <Video className="size-3" /> demo
                        </a>
                      )}
                      {sub.presentation_url && (
                        <a
                          href={sub.presentation_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-[11px] text-amber-400 hover:underline"
                        >
                          <Presentation className="size-3" /> deck
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* COMMUNITY VOTING (T3) */}
          {event && event.community_voting_start && event.community_voting_end && !isCreatorOrAdmin && (
            <Link
              href={`/events/${eventId}/voting`}
              className="block rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4 hover:bg-emerald-500/10 transition-colors"
            >
              <div className="text-sm font-semibold text-emerald-400">Community Voting</div>
              <div className="text-[11px] text-muted-foreground font-mono">
                {new Date(event.community_voting_start).toLocaleString()} → {new Date(event.community_voting_end).toLocaleString()}
                {" · "}Browse projects, vote and comment →
              </div>
            </Link>
          )}
          {event && isCreatorOrAdmin && <JudgingProgressPanel event={event} onUpdated={fetchEvent} />}
          {event && isCreatorOrAdmin && <CommunityVotingPanel event={event} onUpdated={fetchEvent} />}

          {/* 3. ADMIN MANAGEMENT */}
          {event && isCreatorOrAdmin && (
            <AdminEventDashboard
              eventId={Number(eventId)}
              eventObj={event}
              refreshEvent={fetchEvent}
              isPlatformAdmin={user?.role === "admin"}
            />
          )}

          {/* Edit Event Modal for Organizers & Admins */}
          {event && isEditingModalOpen && (
            <EditEventModal
              event={event}
              isOpen={isEditingModalOpen}
              onClose={() => setIsEditingModalOpen(false)}
              onUpdated={(updated) => {
                setActionSuccess(`Event "${updated.title}" updated successfully.`)
                fetchEvent()
              }}
            />
          )}
        </div>
      </div>
    </div>
  )
}
