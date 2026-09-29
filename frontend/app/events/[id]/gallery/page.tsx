"use client"

import React, { useState, useEffect, use } from "react"
import Link from "next/link"
import { useAuth } from "@/context/auth-context"
import { Header } from "@/components/header"
import { Squares } from "@/components/reactbits/squares"
import { api, ApiError, Event as EventType, ProjectSubmission, LeaderboardEntry, JudgeRecordData } from "@/lib/api"
import { EvaluateSubmissionModal } from "@/components/evaluate-submission-modal"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  ArrowLeft,
  Search,
  Loader2,
  Award,
  Code,
  Video,
  Presentation,
  Layers,
  Shield,
  ShieldCheck,
  FileText,
  FileCode2,
  Calendar,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Trophy,
  Star,
  Users,
  Download,
  Copy,
  Check,
} from "lucide-react"

export default function GalleryPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params)
  const eventId = resolvedParams.id
  const { user } = useAuth()

  const [event, setEvent] = useState<EventType | null>(null)
  const [submissions, setSubmissions] = useState<ProjectSubmission[]>([])
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([])
  const [leaderboardHidden, setLeaderboardHidden] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<"projects" | "leaderboard">("projects")

  const [loading, setLoading] = useState(true)
  const [loadingLeaderboard, setLoadingLeaderboard] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [trackFilter, setTrackFilter] = useState("")
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [evaluatingSubmission, setEvaluatingSubmission] = useState<ProjectSubmission | null>(null)

  // T4 Stretch: Embed Modal & Judge Record Modal
  const [showEmbedModal, setShowEmbedModal] = useState(false)
  const [copiedEmbed, setCopiedEmbed] = useState(false)
  const [showJudgeModal, setShowJudgeModal] = useState(false)
  const [judgeRecord, setJudgeRecord] = useState<JudgeRecordData | null>(null)
  const [loadingJudgeRecord, setLoadingJudgeRecord] = useState(false)
  const [judgeRecordError, setJudgeRecordError] = useState<string | null>(null)
  const [copiedJudgeUrl, setCopiedJudgeUrl] = useState(false)

  const handleOpenJudgeRecord = async () => {
    setShowJudgeModal(true)
    setLoadingJudgeRecord(true)
    setJudgeRecordError(null)
    try {
      const data = await api.getMyJudgeRecord(eventId)
      setJudgeRecord(data)
    } catch (err: any) {
      setJudgeRecordError(err.message || "Failed to load judge participation record")
    } finally {
      setLoadingJudgeRecord(false)
    }
  }

  const embedSnippet =
    typeof window !== "undefined"
      ? `<iframe src="${window.location.origin}/embed/events/${eventId}/gallery" width="100%" height="700" frameborder="0" style="border:1px solid #222; border-radius:12px; overflow:hidden;" allow="clipboard-write"></iframe>`
      : `<iframe src="/embed/events/${eventId}/gallery" width="100%" height="700" frameborder="0"></iframe>`

  const copyEmbedCode = () => {
    if (typeof window !== "undefined") {
      navigator.clipboard.writeText(embedSnippet)
      setCopiedEmbed(true)
      setTimeout(() => setCopiedEmbed(false), 2000)
    }
  }

  const copyJudgeRecordUrl = () => {
    if (typeof window !== "undefined" && judgeRecord) {
      const url = `${window.location.origin}/verify/judge/${judgeRecord.record_id}`
      navigator.clipboard.writeText(url)
      setCopiedJudgeUrl(true)
      setTimeout(() => setCopiedJudgeUrl(false), 2000)
    }
  }

  const loadData = async () => {
    try {
      const [ev, subs] = await Promise.all([
        api.getEvent(eventId),
        api.listGallery(eventId, { q: searchQuery, track: trackFilter }),
      ])
      setEvent(ev)
      setSubmissions(subs)
    } catch (e) {
      console.error("Failed to load gallery submissions", e)
    } finally {
      setLoading(false)
    }
  }

  const loadLeaderboardData = async () => {
    setLoadingLeaderboard(true)
    try {
      const data = await api.getLeaderboard(eventId)
      setLeaderboard(data)
      setLeaderboardHidden(null)
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setLeaderboard([])
        setLeaderboardHidden(e.message)
      } else {
        console.error("Failed to load leaderboard", e)
      }
    } finally {
      setLoadingLeaderboard(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [eventId, searchQuery, trackFilter])

  useEffect(() => {
    if (activeTab === "leaderboard") {
      loadLeaderboardData()
    }
  }, [activeTab, eventId])

  const now = new Date()
  const isEnded = event ? new Date(event.end_date) <= now : false
  // Scoped to THIS event: its organizer, its appointed judges, or a platform admin
  const isManager = Boolean(user && (user.role === "admin" || event?.created_by === user.id))
  const isEventJudge = Boolean(user && (user.role === "admin" || event?.event_judges?.some((j) => j.id === user.id)))
  const isJudgeOrOrganizer = isManager || isEventJudge

  const getMediaUrl = (url: string | null) => {
    if (!url) return null
    if (url.startsWith("http")) return url
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    return `${baseUrl}${url.startsWith("/") ? url : `/${url}`}`
  }

  return (
    <div className="relative min-h-screen flex flex-col bg-background font-mono select-none overflow-hidden pb-16">
      <Header />
      <div className="relative flex-1 p-4 sm:p-8 max-w-6xl mx-auto w-full space-y-6">
        <Squares
          direction="diagonal"
          speed={0.2}
          squareSize={48}
          borderColor="rgba(255, 255, 255, 0.03)"
          hoverFillColor="rgba(255, 255, 255, 0.06)"
          className="z-0 pointer-events-none"
        />

        <div className="relative z-10 space-y-6">
          {/* Top Bar Navigation */}
          <div className="flex items-center justify-between">
            <Link
              href={`/events/${eventId}`}
              className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors group"
            >
              <ArrowLeft className="size-3.5 group-hover:-translate-x-0.5 transition-transform" />
              Back to {event?.title || "Event Specification"}
            </Link>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowEmbedModal(true)}
                className="h-7 text-xs font-mono border-border/40 gap-1.5 hover:text-purple-300"
              >
                <Code className="size-3 text-purple-400" />
                Embed Gallery
              </Button>

              {isEventJudge && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleOpenJudgeRecord}
                  className="h-7 text-xs font-mono border-amber-500/40 text-amber-300 bg-amber-500/10 gap-1.5 hover:bg-amber-500/20"
                >
                  <ShieldCheck className="size-3 text-amber-400" />
                  My Signed Credential
                </Button>
              )}

              {isJudgeOrOrganizer && (
                <Badge
                  variant="outline"
                  className="text-[11px] font-mono text-amber-400 border-amber-500/30 bg-amber-500/10 py-1 px-2.5 flex items-center gap-1.5"
                >
                  <Shield className="size-3 text-amber-400" />
                  Judging Mode
                </Badge>
              )}
            </div>
          </div>

          {/* Heading & Context Information */}
          <div className="space-y-1 border-b border-border/30 pb-4">
            <h1 className="text-2xl sm:text-3xl font-light tracking-tight text-foreground flex items-center gap-2.5">
              <span>{isJudgeOrOrganizer ? "Submissions & Evaluation Portal" : "Public Project Gallery"}</span>
            </h1>
            <p className="text-xs text-muted-foreground">
              {event?.title ? `Competition submissions for ${event.title}. ` : ""}
              {isEnded
                ? "This contest has concluded. All submitted projects remain publicly archived for peer review."
                : isJudgeOrOrganizer
                ? "Evaluate projects using the organizer-defined rubrics. Your weighted marks contribute to the official event standings."
                : "Explore published projects built during this hackathon."}
            </p>
          </div>

          {/* Tab Selector: Projects vs Leaderboard */}
          <div className="flex items-center justify-between border-b border-border/20 pb-3 gap-4">
            <div className="flex items-center gap-2">
              <Button
                variant={activeTab === "projects" ? "default" : "outline"}
                size="sm"
                onClick={() => setActiveTab("projects")}
                className="h-8 text-xs font-mono"
              >
                <FileCode2 className="size-3.5 mr-1.5" />
                Submissions ({submissions.length})
              </Button>

              <Button
                variant={activeTab === "leaderboard" ? "default" : "outline"}
                size="sm"
                onClick={() => setActiveTab("leaderboard")}
                className="h-8 text-xs font-mono"
              >
                <Trophy className="size-3.5 mr-1.5 text-amber-400" />
                Standings & Leaderboard
              </Button>
            </div>

            {/* Filter inputs for projects tab */}
            {activeTab === "projects" && (
              <div className="flex items-center gap-2">
                <div className="relative min-w-[200px] hidden sm:block">
                  <Search className="absolute left-2.5 top-2 size-3.5 text-muted-foreground pointer-events-none" />
                  <Input
                    placeholder="Search projects or tech..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-8 bg-muted/20 border-border/40 font-mono text-xs h-7"
                  />
                </div>

                {event?.tracks && event.tracks.length > 0 && (
                  <select
                    className="rounded-md border border-border/40 bg-muted/20 px-2.5 py-1 text-xs font-mono focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                    value={trackFilter}
                    onChange={(e) => setTrackFilter(e.target.value)}
                  >
                    <option value="">All Tracks</option>
                    {event.tracks.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.title}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}
          </div>

          {/* TAB 1: SUBMISSIONS LIST */}
          {activeTab === "projects" && (
            <div>
              {loading ? (
                <div className="p-12 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                  <Loader2 className="size-4 animate-spin text-foreground" />
                  Loading submissions...
                </div>
              ) : submissions.length === 0 ? (
                <div className="p-12 border border-border/30 rounded-xl bg-background/80 backdrop-blur-md text-center space-y-2">
                  <FileCode2 className="size-8 text-muted-foreground mx-auto" />
                  <div className="text-sm font-semibold text-foreground">No Projects Found</div>
                  <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                    {searchQuery || trackFilter
                      ? "No submissions matched your filter criteria."
                      : "No projects have been submitted for this hackathon yet."}
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {submissions.map((sub) => {
                    const isExpanded = expandedId === sub.id
                    const presentationFileUrl = getMediaUrl(sub.presentation_file)

                    return (
                      <div
                        key={sub.id}
                        className="p-5 rounded-xl border border-border/40 bg-background/80 backdrop-blur-md shadow-lg space-y-4 hover:border-border/70 transition-colors flex flex-col justify-between"
                      >
                        <div className="space-y-3">
                          {/* Card Header: Title, Team, and Evaluate Action */}
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <h3 className="font-semibold text-base text-foreground">
                                {sub.title}
                              </h3>
                              <div className="text-[11px] text-muted-foreground font-mono">
                                Team: <strong className="text-foreground">{sub.team_name}</strong> • By @{sub.submitted_by_username}
                              </div>
                            </div>

                            <div className="flex flex-col items-end gap-1.5 shrink-0">
                              <div className="flex items-center gap-1.5">
                                {sub.is_draft && (
                                  <Badge
                                    variant="outline"
                                    className="text-[9px] uppercase tracking-wider text-amber-400 border-amber-500/30 bg-amber-500/10 py-0"
                                  >
                                    Draft
                                  </Badge>
                                )}
                                {sub.track && (
                                  <Badge
                                    variant="outline"
                                    className="text-[9px] uppercase tracking-wider text-purple-400 border-purple-500/30 bg-purple-500/10 py-0"
                                  >
                                    Track {sub.track}
                                  </Badge>
                                )}
                              </div>

                              {/* Judge Evaluate Button */}
                              {isEventJudge && (
                                <Button
                                  size="sm"
                                  onClick={() => setEvaluatingSubmission(sub)}
                                  className="h-6 text-[11px] font-mono bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/30 px-2"
                                >
                                  <Award className="size-3 mr-1" />
                                  Score Project
                                </Button>
                              )}
                            </div>
                          </div>

                          {/* Tagline */}
                          {sub.tagline && (
                            <p className="text-xs text-muted-foreground italic font-sans">
                              &quot;{sub.tagline}&quot;
                            </p>
                          )}

                          {/* Tech Stack Chips */}
                          {sub.tech_stack && (
                            <div className="flex flex-wrap gap-1.5 pt-1">
                              {sub.tech_stack.split(",").map((tech, idx) => (
                                <span
                                  key={idx}
                                  className="text-[10px] bg-muted/40 text-muted-foreground px-2 py-0.5 rounded border border-border/30"
                                >
                                  {tech.trim()}
                                </span>
                              ))}
                            </div>
                          )}

                          {/* Expandable Architecture & Problem Statement */}
                          {isExpanded && (
                            <div className="space-y-3 pt-3 border-t border-border/20 text-xs font-sans">
                              {sub.problem_statement && (
                                <div className="space-y-1">
                                  <span className="font-semibold text-foreground text-[11px] uppercase tracking-wider font-mono">
                                    Problem Statement:
                                  </span>
                                  <p className="text-muted-foreground whitespace-pre-wrap leading-relaxed">
                                    {sub.problem_statement}
                                  </p>
                                </div>
                              )}

                              {sub.solution_description && (
                                <div className="space-y-1">
                                  <span className="font-semibold text-foreground text-[11px] uppercase tracking-wider font-mono">
                                    Solution & Architecture:
                                  </span>
                                  <p className="text-muted-foreground whitespace-pre-wrap leading-relaxed">
                                    {sub.solution_description}
                                  </p>
                                </div>
                              )}
                            </div>
                          )}
                        </div>

                        {/* Bottom Deliverables & Expand Action */}
                        <div className="pt-3 border-t border-border/20 flex items-center justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-3">
                            {sub.github_url && (
                              <a
                                href={sub.github_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-xs text-foreground hover:text-primary flex items-center gap-1 transition-colors"
                              >
                                <Code className="size-3.5" /> Code Repo
                              </a>
                            )}

                            {sub.demo_url && (
                              <a
                                href={sub.demo_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center gap-1 transition-colors"
                              >
                                <Video className="size-3.5" /> Live Demo
                              </a>
                            )}

                            {sub.presentation_url && (
                              <a
                                href={sub.presentation_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-xs text-amber-400 hover:text-amber-300 flex items-center gap-1 transition-colors"
                              >
                                <Presentation className="size-3.5" /> Deck
                              </a>
                            )}

                            {presentationFileUrl && (
                              <a
                                href={presentationFileUrl}
                                target="_blank"
                                rel="noreferrer"
                                className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors"
                              >
                                <FileText className="size-3.5" /> Slides File
                              </a>
                            )}
                          </div>

                          {/* Expand / Collapse Details Button */}
                          {(sub.problem_statement || sub.solution_description) && (
                            <button
                              type="button"
                              onClick={() => setExpandedId(isExpanded ? null : sub.id)}
                              className="text-[11px] text-muted-foreground hover:text-foreground flex items-center gap-1 cursor-pointer font-mono"
                            >
                              {isExpanded ? (
                                <>
                                  Less <ChevronUp className="size-3" />
                                </>
                              ) : (
                                <>
                                  Inspect <ChevronDown className="size-3" />
                                </>
                              )}
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: LEADERBOARD & RESULTS */}
          {activeTab === "leaderboard" && (
            <div className="space-y-4">
              <div className="rounded-xl border border-border/40 bg-background/80 p-5 backdrop-blur-md space-y-4">
                <div className="flex items-center justify-between border-b border-border/20 pb-3">
                  <div>
                    <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
                      <Trophy className="size-4 text-amber-400" />
                      Official Judging Leaderboard & Standings
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      Teams ranked by their weighted aggregate score across all judge evaluations.
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {isManager && (<>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => window.open(api.getLeaderboardCsvUrl(eventId), '_blank')}
                      className="h-7 text-xs font-mono border-border/40 hover:text-emerald-400"
                    >
                      <Download className="size-3 mr-1 text-emerald-400" />
                      Leaderboard CSV
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => window.open(api.getRubricsCsvUrl(eventId), '_blank')}
                      className="h-7 text-xs font-mono border-border/40 hover:text-amber-400"
                    >
                      <Download className="size-3 mr-1 text-amber-400" />
                      Rubrics CSV
                    </Button>
                    </>)}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={loadLeaderboardData}
                      className="h-7 text-xs font-mono"
                    >
                      Refresh Standings
                    </Button>
                  </div>
                </div>

                <div className="p-2.5 rounded-lg border border-primary/20 bg-primary/5 flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-[11px] font-mono text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="font-mono text-[9px] text-primary border-primary/30 bg-primary/10 shrink-0">
                      EMPIRICAL BAYES NORMALIZATION
                    </Badge>
                    <span>
                      Scores normalized via Z-Score shrinkage to eliminate judge severity and dispersion bias.
                    </span>
                  </div>
                  <span className="text-[10px] text-primary font-bold shrink-0">Confidence: &plusmn;SE</span>
                </div>

                {loadingLeaderboard ? (
                  <div className="p-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                    <Loader2 className="size-4 animate-spin text-foreground" />
                    Calculating weighted standings...
                  </div>
                ) : leaderboardHidden ? (
                  <div className="p-8 text-center space-y-1">
                    <div className="text-sm font-semibold text-foreground">Results are not published yet</div>
                    <div className="text-xs text-muted-foreground">
                      Standings stay hidden from participants and judges until the organizer publishes them, so no one is anchored by
                      early scores.
                    </div>
                  </div>
                ) : leaderboard.length === 0 ? (
                  <div className="p-8 text-center text-xs text-muted-foreground">
                    No submissions available to rank.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs font-mono">
                      <thead>
                        <tr className="border-b border-border/40 text-[11px] text-muted-foreground uppercase">
                          <th className="py-2.5 px-3 font-normal w-12 text-center">Rank</th>
                          <th className="py-2.5 px-3 font-normal">Team & Project</th>
                          <th className="py-2.5 px-3 font-normal text-center">Reviews</th>
                          <th className="py-2.5 px-3 font-normal text-right">Normalized Score</th>
                          {isEventJudge && (
                            <th className="py-2.5 px-3 font-normal text-right">Action</th>
                          )}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/20">
                        {leaderboard.map((entry, idx) => {
                          const hasScore = entry.average_score !== null
                          const isTop3 = idx < 3 && hasScore

                          return (
                            <tr key={entry.submission_id} className="hover:bg-muted/20">
                              <td className="py-3 px-3 text-center">
                                {isTop3 ? (
                                  <span
                                    className={`inline-flex items-center justify-center size-6 rounded-full font-bold text-xs ${
                                      idx === 0
                                        ? "bg-amber-400 text-black shadow-[0_0_10px_rgba(251,191,36,0.5)]"
                                        : idx === 1
                                        ? "bg-slate-300 text-black"
                                        : "bg-amber-700 text-white"
                                    }`}
                                  >
                                    #{idx + 1}
                                  </span>
                                ) : (
                                  <span className="text-muted-foreground">#{idx + 1}</span>
                                )}
                              </td>

                              <td className="py-3 px-3">
                                <div className="font-semibold text-foreground text-sm">
                                  {entry.submission_title}
                                </div>
                                <div className="text-[11px] text-muted-foreground">
                                  Team: <strong className="text-foreground">{entry.team_name}</strong>
                                  {entry.tagline && ` • "${entry.tagline}"`}
                                </div>
                              </td>

                              <td className="py-3 px-3 text-center">
                                <Badge variant="outline" className="text-[10px] font-mono py-0">
                                  {entry.evaluations_count}{" "}
                                  {entry.evaluations_count === 1 ? "review" : "reviews"}
                                </Badge>
                              </td>

                              <td className="py-3 px-3 text-right">
                                {hasScore ? (
                                  <div>
                                    <div className="flex items-center justify-end gap-1">
                                      <span className="text-sm font-bold text-amber-300">
                                        {entry.average_score?.toFixed(2)}
                                      </span>
                                      <span className="text-[10px] text-muted-foreground"> / 10</span>
                                    </div>
                                    {entry.standard_error !== undefined && entry.standard_error !== null && entry.standard_error > 0 && (
                                      <div className="text-[10px] text-muted-foreground font-mono">
                                        &plusmn;{entry.standard_error.toFixed(2)} SE
                                      </div>
                                    )}
                                    {entry.raw_score !== undefined && entry.raw_score !== null && (
                                      <div className="text-[9px] text-muted-foreground/60">
                                        Raw: {entry.raw_score.toFixed(2)}
                                      </div>
                                    )}
                                  </div>
                                ) : (
                                  <span className="text-xs text-muted-foreground/60 italic">
                                    Pending Evaluation
                                  </span>
                                )}
                              </td>

                              {isEventJudge && (
                                <td className="py-3 px-3 text-right">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => {
                                      const matchedSub = submissions.find(
                                        (s) => s.id === entry.submission_id
                                      )
                                      if (matchedSub) {
                                        setEvaluatingSubmission(matchedSub)
                                      }
                                    }}
                                    className="h-6 text-[11px] font-mono"
                                  >
                                    <Award className="size-3 mr-1 text-amber-400" />
                                    Evaluate
                                  </Button>
                                </td>
                              )}
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Evaluate Submission Modal */}
      {evaluatingSubmission && (
        <EvaluateSubmissionModal
          eventId={Number(eventId)}
          submission={evaluatingSubmission}
          isOpen={Boolean(evaluatingSubmission)}
          onClose={() => setEvaluatingSubmission(null)}
          onEvaluated={() => {
            loadData()
            if (activeTab === "leaderboard") {
              loadLeaderboardData()
            }
          }}
        />
      )}

      {/* Embed Gallery Modal */}
      {showEmbedModal && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setShowEmbedModal(false)}
        >
          <div
            className="bg-[#0e131f] border border-border/40 rounded-xl max-w-2xl w-full p-6 text-slate-200 shadow-2xl relative space-y-4 font-mono"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="font-bold text-base text-white flex items-center gap-2">
                <Code className="size-4 text-purple-400" /> Embed Gallery Widget
              </h3>
              <button
                onClick={() => setShowEmbedModal(false)}
                className="text-slate-400 hover:text-white font-bold"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Embed this interactive, responsive gallery on external websites, portfolio pages, or blogs. Includes real-time project search, track filtering, and details modal.
            </p>

            <div className="relative">
              <pre className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto whitespace-pre-wrap">
                {embedSnippet}
              </pre>
              <Button
                onClick={copyEmbedCode}
                size="sm"
                className="absolute top-2 right-2 h-7 text-xs border border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800 gap-1"
              >
                {copiedEmbed ? <Check className="size-3 text-emerald-400" /> : <Copy className="size-3" />}
                {copiedEmbed ? "Copied" : "Copy Code"}
              </Button>
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-slate-800 text-xs">
              <span className="text-slate-500">Supports automatic iframe height auto-resizing</span>
              <Link
                href={`/embed/events/${eventId}/gallery`}
                target="_blank"
                className="text-purple-400 hover:underline flex items-center gap-1 font-mono"
              >
                Preview Live Widget <ExternalLink className="size-3" />
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Judge Participation Record Modal */}
      {showJudgeModal && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setShowJudgeModal(false)}
        >
          <div
            className="bg-[#0e131f] border border-amber-500/40 rounded-xl max-w-xl w-full p-6 text-slate-200 shadow-2xl relative space-y-4 font-mono"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="font-bold text-base text-white flex items-center gap-2">
                <ShieldCheck className="size-4 text-amber-400" /> Official Judge Credential
              </h3>
              <button
                onClick={() => setShowJudgeModal(false)}
                className="text-slate-400 hover:text-white font-bold"
              >
                ✕
              </button>
            </div>

            {loadingJudgeRecord ? (
              <div className="py-12 flex flex-col items-center justify-center gap-2 text-slate-400">
                <Loader2 className="size-5 animate-spin text-amber-400" />
                <p className="text-xs">Fetching cryptographic judge credential...</p>
              </div>
            ) : judgeRecordError || !judgeRecord ? (
              <div className="p-4 rounded-lg bg-red-950/20 border border-red-500/30 text-xs text-red-300">
                {judgeRecordError ||
                  "No signed judge record available yet. Complete evaluations first or wait for the organizer to issue certificates."}
              </div>
            ) : (
              <div className="space-y-4 text-xs">
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Judge Username:</span>
                    <span className="font-bold text-white">@{judgeRecord.judge_username}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Event:</span>
                    <span className="font-semibold text-emerald-400">{judgeRecord.event_title}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Evaluations Completed:</span>
                    <span className="font-bold text-white">{judgeRecord.record.evaluations_count}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Average Score Given:</span>
                    <span className="font-bold text-amber-300">
                      {judgeRecord.record.average_score_given != null ? judgeRecord.record.average_score_given.toFixed(2) : "—"}
                    </span>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5 break-all text-[11px]">
                  <span className="text-slate-500 block text-[10px] uppercase">
                    Cryptographic Signature (Ed25519)
                  </span>
                  <span className="text-emerald-400">{judgeRecord.signature}</span>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-slate-800">
                  <Button
                    onClick={copyJudgeRecordUrl}
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs border-slate-700 bg-slate-900 text-slate-200 gap-1.5"
                  >
                    {copiedJudgeUrl ? <Check className="size-3 text-emerald-400" /> : <Copy className="size-3" />}
                    {copiedJudgeUrl ? "Link Copied" : "Copy Public Verification URL"}
                  </Button>

                  <Link
                    href={`/verify/judge/${judgeRecord.record_id}`}
                    target="_blank"
                    className="text-amber-400 hover:underline flex items-center gap-1 text-xs"
                  >
                    View Public Record <ExternalLink className="size-3" />
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
