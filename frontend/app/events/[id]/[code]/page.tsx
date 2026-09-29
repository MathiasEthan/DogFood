"use client"

import React, { useState, useEffect, use } from "react"
import Link from "next/link"
import { useAuth } from "@/context/auth-context"
import { Header } from "@/components/header"
import { Squares } from "@/components/reactbits/squares"
import { api, buildInviteLink, Event as EventType, Team, ProjectSubmission } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
  Shield,
  Crown,
  FileCode2,
  ExternalLink,
  Presentation,
  Video,
  Layers,
  Edit3,
  Clock,
  Send,
  Upload,
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

export default function TeamSubmissionPage({
  params,
}: {
  params: Promise<{ id: string; code: string }>
}) {
  const resolvedParams = use(params)
  const eventId = resolvedParams.id
  const teamCode = resolvedParams.code

  const { user } = useAuth()

  const [event, setEvent] = useState<EventType | null>(null)
  const [team, setTeam] = useState<Team | null>(null)
  const [submission, setSubmission] = useState<ProjectSubmission | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Project Submission Form States
  const [subTitle, setSubTitle] = useState("")
  const [subTagline, setSubTagline] = useState("")
  const [subProblem, setSubProblem] = useState("")
  const [subSolution, setSubSolution] = useState("")
  const [subGithub, setSubGithub] = useState("")
  const [subDemo, setSubDemo] = useState("")
  const [subPresentation, setSubPresentation] = useState("")
  const [subTechStack, setSubTechStack] = useState("")

  const [subTrack, setSubTrack] = useState<number | "">( "")
  const [isDraft, setIsDraft] = useState<boolean>(true)

  const [subFile, setSubFile] = useState<File | null>(null)
  const [isEditingSubmission, setIsEditingSubmission] = useState(false)
  const [submittingProject, setSubmittingProject] = useState(false)
  const [submissionError, setSubmissionError] = useState<string | null>(null)
  const [submissionSuccess, setSubmissionSuccess] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  // Countdown timer state
  const [timeLeft, setTimeLeft] = useState<{
    days: number
    hours: number
    minutes: number
    seconds: number
    isExpired: boolean
  }>({ days: 0, hours: 0, minutes: 0, seconds: 0, isExpired: false })

  const loadData = async () => {
    try {
      const ev = await api.getEvent(eventId)
      setEvent(ev)

      // Find the specific team matching the teamCode
      let currentTeam: Team | null = null
      if (ev.my_team && ev.my_team.code.toUpperCase() === teamCode.toUpperCase()) {
        currentTeam = ev.my_team
      } else if (ev.teams) {
        currentTeam = ev.teams.find((t) => t.code.toUpperCase() === teamCode.toUpperCase()) || null
      }

      setTeam(currentTeam)

      // If user is member/leader of this team or has submission
      if (currentTeam?.submission) {
        setSubmission(currentTeam.submission)
        populateForm(currentTeam.submission)
      } else {
        // Try fetching submission directly via API
        try {
          const sub = await api.getMySubmission(eventId)
          setSubmission(sub)
          populateForm(sub)
        } catch {
          setSubmission(null)
        }
      }
    } catch (err: any) {
      setError(err.message || "Failed to load team and submission information.")
    } finally {
      setLoading(false)
    }
  }

  const populateForm = (s: ProjectSubmission) => {
    setSubTitle(s.title)
    setSubTagline(s.tagline)
    setSubProblem(s.problem_statement)
    setSubSolution(s.solution_description)
    setSubGithub(s.github_url)
    setSubDemo(s.demo_url || "")
    setSubPresentation(s.presentation_url || "")
    setSubTechStack(s.tech_stack || "")

    setSubTrack(s.track || "")
    setIsDraft(s.is_draft)

  }

  useEffect(() => {
    loadData()
  }, [eventId, teamCode, user])

  // Countdown Timer
  useEffect(() => {
    if (!event) return

    const updateTimer = () => {
      const now = new Date().getTime()
      const end = new Date(event.end_date).getTime()
      const difference = end - now

      if (difference <= 0) {
        setTimeLeft({ days: 0, hours: 0, minutes: 0, seconds: 0, isExpired: true })
      } else {
        const days = Math.floor(difference / (1000 * 60 * 60 * 24))
        const hours = Math.floor((difference % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))
        const minutes = Math.floor((difference % (1000 * 60 * 60)) / (1000 * 60))
        const seconds = Math.floor((difference % (1000 * 60)) / 1000)
        setTimeLeft({ days, hours, minutes, seconds, isExpired: false })
      }
    }

    updateTimer()
    const interval = setInterval(updateTimer, 1000)
    return () => clearInterval(interval)
  }, [event])

  const isLeader = Boolean(user && team && team.leader === user.id)
  const isDeadlinePassed = timeLeft.isExpired

  const handleProjectSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmissionError(null)
    setSubmissionSuccess(null)

    if (isDeadlinePassed) {
      setSubmissionError("The submission deadline has passed. Submissions are permanently locked.")
      return
    }

    if (!isLeader) {
      setSubmissionError("Only the team leader is permitted to create or edit project submissions.")
      return
    }

    if (!isDraft) {
      if (
        !subTitle.trim() ||
        !subTagline.trim() ||
        !subProblem.trim() ||
        !subSolution.trim() ||
        (event?.require_github_url && !subGithub.trim()) ||
        (event?.require_demo_url && !subDemo.trim()) ||
        (event?.require_presentation && !subPresentation.trim() && !subFile && !submission?.presentation_file)
      ) {
        setSubmissionError("Please fill in all mandatory fields before making a final submission.")
        return
      }
    }

    setSubmittingProject(true)
    try {
      const formData = new FormData()
      formData.append("title", subTitle.trim())
      formData.append("tagline", subTagline.trim())
      formData.append("problem_statement", subProblem.trim())
      formData.append("solution_description", subSolution.trim())
      formData.append("github_url", subGithub.trim())
      formData.append("demo_url", subDemo.trim())
      formData.append("presentation_url", subPresentation.trim())
      formData.append("tech_stack", subTechStack.trim())

      formData.append("is_draft", isDraft ? "true" : "false")
      if (subTrack) formData.append("track", subTrack.toString())

      if (subFile) {
        formData.append("presentation_file", subFile)
      }

      const res = await api.submitProject(eventId, formData)
      setSubmissionSuccess(res.message)
      setSubmission(res.submission)
      setIsEditingSubmission(false)
      await loadData()
    } catch (err: any) {
      setSubmissionError(err.message || "Failed to submit project.")
    } finally {
      setSubmittingProject(false)
    }
  }

  const [inviteCopied, setInviteCopied] = useState(false)

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

  if (loading) {
    return (
      <div className="relative min-h-screen flex flex-col bg-background font-mono select-none">
        <Header />
        <div className="flex-1 flex items-center justify-center">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="size-4 animate-spin text-foreground" />
            Loading team submission portal...
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
            <h2 className="text-sm font-semibold text-foreground">Failed to Load Submission Portal</h2>
            <p className="text-xs text-muted-foreground">{error || "Event not found."}</p>
            <Link href={`/events/${eventId}`}>
              <Button size="sm" variant="outline" className="text-xs font-mono">
                <ArrowLeft className="size-3 mr-1.5" /> Return to Event
              </Button>
            </Link>
          </div>
        </div>
      </div>
    )
  }

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
          {/* Navigation & Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/30 pb-6">
            <div className="space-y-2">
              <Link
                href={`/events/${eventId}`}
                className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors group"
              >
                <ArrowLeft className="size-3.5 group-hover:-translate-x-0.5 transition-transform" />
                Back to {event.title}
              </Link>
              <div className="flex items-center gap-3">
                <h1 className="text-xl sm:text-2xl font-light tracking-tight text-foreground">
                  Team Submission Portal
                </h1>
                <span className="text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded font-mono uppercase tracking-wider">
                  {teamCode}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Manage your team project, architecture description, codebase repository, and deliverables.
              </p>
            </div>

            {/* Countdown / Deadline Status */}
            <div className="flex items-center">
              {isDeadlinePassed ? (
                <div className="px-3 py-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-400 text-xs flex items-center gap-2">
                  <Clock className="size-4 text-rose-400" />
                  <span>Submissions Closed (Deadline Expired)</span>
                </div>
              ) : (
                <div className="px-3 py-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-xs space-y-0.5">
                  <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                    <Clock className="size-3" /> Time Remaining Until Deadline
                  </div>
                  <div className="font-semibold text-sm tracking-wide text-foreground">
                    {timeLeft.days}d {timeLeft.hours}h {timeLeft.minutes}m {timeLeft.seconds}s
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Team Info Card */}
          {team && (
            <div className="rounded-xl border border-border/40 bg-muted/10 p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <div className="text-[10px] text-muted-foreground uppercase tracking-widest">Registered Team</div>
                  <div className="text-base font-semibold text-foreground flex items-center gap-2">
                    {team.name}
                    {isLeader && (
                      <span className="text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded flex items-center gap-1">
                        <Crown className="size-3" /> Team Leader
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <div className="text-xs text-muted-foreground font-mono bg-background/60 border border-border/40 px-2.5 py-1 rounded">
                    Code: <span className="text-foreground font-semibold">{team.code}</span>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyTeamCode(team.code)}
                    className="h-7 text-xs font-mono gap-1"
                  >
                    {copied ? <Check className="size-3 text-emerald-400" /> : <Copy className="size-3" />}
                    {copied ? "Copied" : "Copy"}
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => {
                      navigator.clipboard.writeText(buildInviteLink(eventId, team.code))
                      setInviteCopied(true)
                      setTimeout(() => setInviteCopied(false), 2000)
                    }}
                    className="h-7 text-xs font-mono gap-1 bg-emerald-600 hover:bg-emerald-500 text-white"
                  >
                    {inviteCopied ? <Check className="size-3" /> : <Users className="size-3" />}
                    {inviteCopied ? "Link copied" : "Copy invite link"}
                  </Button>
                </div>
              </div>

              {/* Members List */}
              <div className="border-t border-border/20 pt-3">
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">
                  Team Roster ({team.members.length} / {team.max_size})
                </div>
                <div className="flex flex-wrap gap-2">
                  {team.members.map((m) => (
                    <div
                      key={m.id}
                      className="text-xs px-2.5 py-1 rounded-md border border-border/30 bg-background/50 flex items-center gap-1.5"
                    >
                      {m.is_leader ? (
                        <Crown className="size-3 text-amber-400" />
                      ) : (
                        <span className="size-1.5 rounded-full bg-muted-foreground" />
                      )}
                      <span>@{m.username}</span>
                      {m.username === user?.username && <span className="text-[10px] text-muted-foreground">(You)</span>}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Submission Alerts */}
          {submissionError && (
            <div className="p-3.5 rounded-lg border border-destructive/40 bg-destructive/10 text-xs text-destructive flex items-center gap-2">
              <AlertCircle className="size-4 shrink-0" />
              <span>{submissionError}</span>
            </div>
          )}
          {submissionSuccess && (
            <div className="p-3.5 rounded-lg border border-emerald-500/40 bg-emerald-500/10 text-xs text-emerald-400 flex items-center gap-2">
              <Check className="size-4 shrink-0" />
              <span>{submissionSuccess}</span>
            </div>
          )}

          {/* MAIN SUBMISSION WORKSPACE */}
          <div className="rounded-xl border border-border/40 bg-background/80 p-6 sm:p-8 backdrop-blur-md shadow-2xl space-y-6">
            {submission && !isEditingSubmission ? (
              /* ============================================================ */
              /* READ-ONLY SUBMISSION VIEW                                   */
              /* ============================================================ */
              <div className="space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 border-b border-border/30 pb-5">
                  <div className="space-y-1.5">
                    <div className="inline-flex items-center gap-2 text-[10px] tracking-widest text-emerald-400 uppercase">
                      <span className="size-1.5 rounded-full bg-emerald-400" />
                      Submission Status: Confirmed
                    </div>
                    <h2 className="text-xl sm:text-2xl font-semibold text-foreground tracking-tight">
                      {submission.title}
                    </h2>
                    <p className="text-sm text-muted-foreground italic">
                      "{submission.tagline}"
                    </p>
                    <div className="text-[11px] text-muted-foreground flex items-center gap-3 pt-1">
                      <span>Submitted by: @{submission.submitted_by_username}</span>
                      <span>•</span>
                      <span>Updated: {new Date(submission.updated_at).toLocaleString()}</span>
                    </div>
                  </div>

                  {/* Leader Edit Button */}
                  {isLeader && !isDeadlinePassed && (
                    <Button
                      onClick={() => setIsEditingSubmission(true)}
                      size="sm"
                      className="text-xs font-mono bg-foreground text-background hover:bg-foreground/90 gap-1.5 shrink-0"
                    >
                      <Edit3 className="size-3.5" /> Edit Submission
                    </Button>
                  )}
                </div>

                {/* Project Links & Deliverables */}
                <div className="flex flex-wrap gap-3">
                  <a
                    href={submission.github_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-2 text-xs font-mono px-3.5 py-2 rounded-lg border border-border/40 bg-muted/20 hover:bg-muted/40 text-foreground transition-colors"
                  >
                    <GithubIcon className="size-3.5" />
                    <span>Source Code</span>
                    <ExternalLink className="size-3 text-muted-foreground" />
                  </a>

                  {submission.demo_url && (
                    <a
                      href={submission.demo_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 text-xs font-mono px-3.5 py-2 rounded-lg border border-border/40 bg-muted/20 hover:bg-muted/40 text-foreground transition-colors"
                    >
                      <Video className="size-3.5 text-blue-400" />
                      <span>Live Demo</span>
                      <ExternalLink className="size-3 text-muted-foreground" />
                    </a>
                  )}

                  {submission.presentation_url && (
                    <a
                      href={submission.presentation_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 text-xs font-mono px-3.5 py-2 rounded-lg border border-border/40 bg-muted/20 hover:bg-muted/40 text-foreground transition-colors"
                    >
                      <Presentation className="size-3.5 text-amber-400" />
                      <span>Slide Deck</span>
                      <ExternalLink className="size-3 text-muted-foreground" />
                    </a>
                  )}

                  {submission.presentation_file && (
                    <a
                      href={getMediaUrl(submission.presentation_file) || "#"}
                      target="_blank"
                      rel="noreferrer"
                      download
                      className="inline-flex items-center gap-2 text-xs font-mono px-3.5 py-2 rounded-lg border border-border/40 bg-muted/20 hover:bg-muted/40 text-foreground transition-colors"
                    >
                      <Upload className="size-3.5 text-purple-400" />
                      <span>Download Deck File</span>
                      <ExternalLink className="size-3 text-muted-foreground" />
                    </a>
                  )}
                </div>

                {/* Tech Stack Tags */}
                {submission.tech_stack && (
                  <div className="space-y-1.5">
                    <div className="text-[10px] text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                      <Layers className="size-3" /> Tech Stack & Technologies
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {submission.tech_stack.split(",").map((tech, idx) => (
                        <span
                          key={idx}
                          className="text-[11px] font-mono px-2 py-0.5 rounded bg-muted/30 border border-border/40 text-foreground"
                        >
                          {tech.trim()}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Problem Statement */}
                <div className="space-y-2 border-t border-border/20 pt-4">
                  <div className="text-[11px] font-semibold text-foreground uppercase tracking-wider">
                    Problem Statement
                  </div>
                  <div className="p-4 rounded-lg border border-border/30 bg-muted/10 text-xs leading-relaxed text-foreground whitespace-pre-wrap">
                    {submission.problem_statement}
                  </div>
                </div>

                {/* Solution Description */}
                <div className="space-y-2 border-t border-border/20 pt-4">
                  <div className="text-[11px] font-semibold text-foreground uppercase tracking-wider">
                    Solution & Architecture
                  </div>
                  <div className="p-4 rounded-lg border border-border/30 bg-muted/10 text-xs leading-relaxed text-foreground whitespace-pre-wrap">
                    {submission.solution_description}
                  </div>
                </div>
              </div>
            ) : (
              /* ============================================================ */
              /* SUBMISSION & EDIT FORM (LEADER ONLY)                         */
              /* ============================================================ */
              <div>
                {!isLeader ? (
                  <div className="p-8 rounded-lg border border-border/30 bg-muted/10 text-center space-y-3">
                    <Shield className="size-8 text-muted-foreground mx-auto" />
                    <h3 className="text-sm font-semibold text-foreground">Leader Submission Required</h3>
                    <p className="text-xs text-muted-foreground max-w-md mx-auto">
                      Only the team leader (@{team?.leader_username}) has permissions to submit or modify this project.
                      Please coordinate with your team leader before the deadline.
                    </p>
                  </div>
                ) : isDeadlinePassed ? (
                  <div className="p-8 rounded-lg border border-rose-500/20 bg-rose-500/5 text-center space-y-3">
                    <Clock className="size-8 text-rose-400 mx-auto" />
                    <h3 className="text-sm font-semibold text-rose-400">Submission Window Closed</h3>
                    <p className="text-xs text-muted-foreground max-w-md mx-auto">
                      The hackathon deadline has passed. No further deliverables or project edits can be submitted.
                    </p>
                  </div>
                ) : (
                  <form onSubmit={handleProjectSubmit} className="space-y-6">
                    <div className="flex items-center justify-between border-b border-border/30 pb-4">
                      <div>
                        <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
                          {submission ? "Update Project Submission" : "Submit Team Deliverables"}
                        </h2>
                        <p className="text-xs text-muted-foreground">
                          Fill in your project information, architecture summary, and repository links
                        </p>
                      </div>

                      {submission && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setIsEditingSubmission(false)}
                          className="text-xs font-mono"
                        >
                          Cancel
                        </Button>
                      )}
                    </div>
                    
                    {event?.submission_guidelines && (
                      <div className="p-4 rounded-md border border-amber-500/30 bg-amber-500/5 text-xs text-amber-600/90 whitespace-pre-wrap leading-relaxed">
                        <strong className="text-amber-600">Organizer Guidelines:</strong><br/>
                        {event.submission_guidelines}
                      </div>
                    )}

                    {/* Project Title & Tagline */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <Label htmlFor="subTitle" className="text-[11px] text-muted-foreground uppercase tracking-wider">
                          Project Title {!isDraft ? "*" : ""}
                        </Label>
                        <Input
                          id="subTitle"
                          placeholder="e.g. Nexus Protocol"
                          value={subTitle}
                          onChange={(e) => setSubTitle(e.target.value)}
                          className="h-9 text-xs font-mono bg-muted/20"
                          required={!isDraft}
                        />
                      </div>

                      <div className="space-y-1.5">
                        <Label htmlFor="subTagline" className="text-[11px] text-muted-foreground uppercase tracking-wider">
                          Tagline / One-Liner {!isDraft ? "*" : ""}
                        </Label>
                        <Input
                          id="subTagline"
                          placeholder="e.g. Decentralized identity verification for Web3"
                          value={subTagline}
                          onChange={(e) => setSubTagline(e.target.value)}
                          className="h-9 text-xs font-mono bg-muted/20"
                          required={!isDraft}
                        />
                      </div>
                    </div>

                    {/* Problem Statement */}
                    <div className="space-y-1.5">
                      <Label htmlFor="subProblem" className="text-[11px] text-muted-foreground uppercase tracking-wider">
                        Problem Statement {!isDraft ? "*" : ""}
                      </Label>
                      <textarea
                        id="subProblem"
                        rows={4}
                        placeholder="Describe the exact problem your team set out to solve..."
                        value={subProblem}
                        onChange={(e) => setSubProblem(e.target.value)}
                        className="w-full rounded-md border border-input bg-muted/20 px-3 py-2 text-xs font-mono placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                        required={!isDraft}
                      />
                    </div>

                    {/* Solution Description */}
                    <div className="space-y-1.5">
                      <Label htmlFor="subSolution" className="text-[11px] text-muted-foreground uppercase tracking-wider">
                        Solution & Architecture {!isDraft ? "*" : ""}
                      </Label>
                      <textarea
                        id="subSolution"
                        rows={5}
                        placeholder="Detail how your solution works, the system architecture, and how challenges were resolved..."
                        value={subSolution}
                        onChange={(e) => setSubSolution(e.target.value)}
                        className="w-full rounded-md border border-input bg-muted/20 px-3 py-2 text-xs font-mono placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                        required={!isDraft}
                      />
                    </div>

                    {/* Code & Demo Links */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <Label htmlFor="subGithub" className="text-[11px] text-muted-foreground uppercase tracking-wider flex items-center gap-1">
                          <GithubIcon className="size-3" /> GitHub Repository Link {(event?.require_github_url && !isDraft) ? "*" : "(Optional)"}
                        </Label>
                        <Input
                          id="subGithub"
                          type="url"
                          placeholder="https://github.com/org/repo"
                          value={subGithub}
                          onChange={(e) => setSubGithub(e.target.value)}
                          className="h-9 text-xs font-mono bg-muted/20"
                          required={event?.require_github_url && !isDraft}
                        />
                      </div>

                      <div className="space-y-1.5">
                        <Label htmlFor="subDemo" className="text-[11px] text-muted-foreground uppercase tracking-wider flex items-center gap-1">
                          <Video className="size-3" /> Live Demo URL {(event?.require_demo_url && !isDraft) ? "*" : "(Optional)"}
                        </Label>
                        <Input
                          id="subDemo"
                          type="url"
                          placeholder="https://demo.myproject.app"
                          value={subDemo}
                          onChange={(e) => setSubDemo(e.target.value)}
                          className="h-9 text-xs font-mono bg-muted/20"
                          required={event?.require_demo_url && !isDraft}
                        />
                      </div>
                    </div>

                    {/* Presentation Deck (URL or File) */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <Label htmlFor="subPresentation" className="text-[11px] text-muted-foreground uppercase tracking-wider flex items-center gap-1">
                          <Presentation className="size-3" /> Presentation Slide Deck URL {(event?.require_presentation && !isDraft) ? "*" : "(Optional)"}
                        </Label>
                        <Input
                          id="subPresentation"
                          type="url"
                          placeholder="https://canva.com/design/... or Google Slides"
                          value={subPresentation}
                          onChange={(e) => setSubPresentation(e.target.value)}
                          className="h-9 text-xs font-mono bg-muted/20"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <Label htmlFor="subFile" className="text-[11px] text-muted-foreground uppercase tracking-wider flex items-center gap-1">
                          <Upload className="size-3" /> Slide Deck File Upload (PDF, PPTX, KEY) {(event?.require_presentation && !isDraft) ? "*" : ""}
                        </Label>
                        <Input
                          id="subFile"
                          type="file"
                          accept=".pdf,.pptx,.ppt,.key"
                          onChange={(e) => setSubFile(e.target.files?.[0] || null)}
                          className="h-9 text-xs font-mono bg-muted/20 cursor-pointer"
                        />
                        {submission?.presentation_file && !subFile && (
                          <div className="text-[10px] text-muted-foreground">
                            Current file:{" "}
                            <span className="text-foreground">{submission.presentation_file.split("/").pop()}</span>
                          </div>
                        )}
                        {(event?.require_presentation && !isDraft) && (
                          <div className="text-[10px] text-amber-500/80">
                            * Either URL or File upload is required.
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Tech Stack */}
                    <div className="space-y-1.5">
                      <Label htmlFor="subTechStack" className="text-[11px] text-muted-foreground uppercase tracking-wider flex items-center gap-1">
                        <Layers className="size-3" /> Tech Stack (comma-separated)
                      </Label>
                      <Input
                        id="subTechStack"
                        placeholder="Django, Next.js, PostgreSQL, TailwindCSS, Docker"
                        value={subTechStack}
                        onChange={(e) => setSubTechStack(e.target.value)}
                        className="h-9 text-xs font-mono bg-muted/20"
                      />
                    </div>

                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <Label htmlFor="subTrack" className="text-[11px] text-muted-foreground uppercase tracking-wider">
                          Competition Track (Optional)
                        </Label>
                        <select
                          id="subTrack"
                          value={subTrack}
                          onChange={(e) => setSubTrack(e.target.value ? Number(e.target.value) : "")}
                          className="w-full h-9 rounded-md border border-input bg-muted/20 px-3 py-1 text-xs font-mono"
                        >
                          <option value="">-- No Track selected --</option>
                          {event?.tracks?.map(t => (
                            <option key={t.id} value={t.id}>{t.title}</option>
                          ))}
                        </select>
                      </div>

                      <div className="space-y-1.5 flex items-center pt-5 gap-2">
                        <input
                          id="isDraft"
                          type="checkbox"
                          checked={isDraft}
                          onChange={(e) => setIsDraft(e.target.checked)}
                          className="size-4"
                        />
                        <Label htmlFor="isDraft" className="text-[11px] text-muted-foreground uppercase tracking-wider cursor-pointer">
                          Save as Draft (Hide from Public Gallery)
                        </Label>
                      </div>
                    </div>

                    {/* Submit Actions */}
                    <div className="pt-2 flex items-center justify-end gap-3">
                      {submission && (
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => setIsEditingSubmission(false)}
                          className="text-xs font-mono"
                        >
                          Cancel
                        </Button>
                      )}
                      <Button
                        type="submit"
                        disabled={submittingProject}
                        className="h-9 text-xs font-mono bg-foreground text-background hover:bg-foreground/90 font-medium px-5"
                      >
                        {submittingProject ? (
                          <Loader2 className="size-3.5 animate-spin mr-1.5" />
                        ) : (
                          <Send className="size-3.5 mr-1.5" />
                        )}
                        {submission ? "Update Submission" : "Submit Project"}
                      </Button>
                    </div>
                  </form>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
