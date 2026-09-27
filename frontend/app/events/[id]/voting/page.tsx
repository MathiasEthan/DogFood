"use client"

import React, { useCallback, useEffect, useRef, useState, use } from "react"
import Link from "next/link"
import { useAuth } from "@/context/auth-context"
import { Header } from "@/components/header"
import { Squares } from "@/components/reactbits/squares"
import {
  api,
  ApiError,
  CommunityComment,
  CommunityResults,
  Event as EventType,
  ProjectSubmission,
  VotingStatus,
} from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  AlertCircle,
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  Code,
  Loader2,
  Lock,
  MessageSquare,
  Presentation,
  Search,
  Shuffle,
  ThumbsUp,
  Trophy,
  Video,
} from "lucide-react"

const getMediaUrl = (url: string | null) => {
  if (!url) return null
  if (url.startsWith("http")) return url
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
  return `${baseUrl}${url.startsWith("/") ? url : `/${url}`}`
}

function CommentThread({
  eventId,
  submissionId,
  canPost,
  onCountChange,
}: {
  eventId: string
  submissionId: number
  canPost: boolean
  onCountChange: (n: number) => void
}) {
  const [comments, setComments] = useState<CommunityComment[]>([])
  const [loading, setLoading] = useState(true)
  const [text, setText] = useState("")
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editText, setEditText] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Keep the latest callback in a ref so a new parent closure doesn't trigger refetches
  const onCountChangeRef = useRef(onCountChange)
  useEffect(() => {
    onCountChangeRef.current = onCountChange
  }, [onCountChange])

  const load = useCallback(async () => {
    try {
      const data = await api.listComments(eventId, submissionId)
      setComments(data)
      onCountChangeRef.current(data.length)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [eventId, submissionId])

  useEffect(() => {
    load()
  }, [load])

  const submit = async () => {
    if (!text.trim()) return
    setBusy(true)
    setError(null)
    try {
      await api.postComment(eventId, submissionId, text)
      setText("")
      load()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const saveEdit = async (id: number) => {
    try {
      await api.editComment(eventId, id, editText)
      setEditingId(null)
      load()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const remove = async (id: number) => {
    if (!confirm("Remove this comment?")) return
    try {
      await api.deleteComment(eventId, id)
      load()
    } catch (e: any) {
      setError(e.message)
    }
  }

  return (
    <div className="space-y-2 pt-2 border-t border-border/20">
      {loading ? (
        <div className="text-[11px] text-muted-foreground flex items-center gap-1">
          <Loader2 className="size-3 animate-spin" /> loading comments...
        </div>
      ) : comments.length === 0 ? (
        <div className="text-[11px] text-muted-foreground">No comments yet.</div>
      ) : (
        <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
          {comments.map((c) => (
            <div key={c.id} className="text-xs rounded-md bg-muted/20 border border-border/30 p-2 space-y-1">
              <div className="flex items-center justify-between text-[10px] text-muted-foreground font-mono">
                <span>
                  @{c.author_username} · {new Date(c.created_at).toLocaleString()}
                  {c.is_edited && " · edited"}
                </span>
                <span className="flex gap-2">
                  {c.can_edit && editingId !== c.id && (
                    <button
                      className="hover:text-foreground"
                      onClick={() => {
                        setEditingId(c.id)
                        setEditText(c.text)
                      }}
                    >
                      edit
                    </button>
                  )}
                  {c.can_remove && (
                    <button className="hover:text-destructive" onClick={() => remove(c.id)}>
                      remove
                    </button>
                  )}
                </span>
              </div>
              {editingId === c.id ? (
                <div className="flex gap-2">
                  <Input value={editText} onChange={(e) => setEditText(e.target.value)} className="h-7 text-xs" maxLength={2000} />
                  <Button size="sm" className="h-7 text-[11px]" onClick={() => saveEdit(c.id)}>
                    save
                  </Button>
                  <Button size="sm" variant="ghost" className="h-7 text-[11px]" onClick={() => setEditingId(null)}>
                    cancel
                  </Button>
                </div>
              ) : (
                <p className="whitespace-pre-wrap font-sans text-foreground/90">{c.text}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {error && <div className="text-[11px] text-destructive">{error}</div>}

      {canPost ? (
        <div className="flex gap-2">
          <Input
            placeholder="Add a comment..."
            value={text}
            maxLength={2000}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                submit()
              }
            }}
            className="h-7 text-xs"
          />
          <Button size="sm" onClick={submit} disabled={busy || !text.trim()} className="h-7 text-[11px] font-mono">
            {busy ? <Loader2 className="size-3 animate-spin" /> : "post"}
          </Button>
        </div>
      ) : null}
    </div>
  )
}

export default function CommunityVotingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: eventId } = use(params)
  const { user } = useAuth()

  const [event, setEvent] = useState<EventType | null>(null)
  const [submissions, setSubmissions] = useState<ProjectSubmission[]>([])
  const [status, setStatus] = useState<VotingStatus | null>(null)
  const [results, setResults] = useState<CommunityResults | null>(null)
  const [resultsHidden, setResultsHidden] = useState<string | null>(null)
  const [tab, setTab] = useState<"projects" | "results">("projects")

  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [commentsOpen, setCommentsOpen] = useState<Record<number, boolean>>({})
  const [commentCounts, setCommentCounts] = useState<Record<number, number>>({})
  const [counts, setCounts] = useState<Record<number, number | null>>({})
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await api.getVotingStatus(eventId))
    } catch (e) {
      console.error(e)
    }
  }, [eventId])

  const loadData = useCallback(async () => {
    try {
      const [ev, subs] = await Promise.all([api.getEvent(eventId), api.listGallery(eventId, { q: searchQuery })])
      setEvent(ev)
      setSubmissions(subs)
      const c: Record<number, number | null> = {}
      const cc: Record<number, number> = {}
      subs.forEach((s) => {
        c[s.id] = s.community_vote_count ?? null
        cc[s.id] = s.comment_count ?? 0
      })
      setCounts(c)
      setCommentCounts(cc)
    } catch (e: any) {
      setError(e.message || "Failed to load projects")
    } finally {
      setLoading(false)
    }
  }, [eventId, searchQuery])

  const loadResults = useCallback(async () => {
    try {
      setResults(await api.getCommunityResults(eventId))
      setResultsHidden(null)
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setResults(null)
        setResultsHidden(e.message)
      }
    }
  }, [eventId])

  useEffect(() => {
    loadData()
  }, [loadData])

  useEffect(() => {
    loadStatus()
  }, [loadStatus, user])

  useEffect(() => {
    if (tab === "results") loadResults()
  }, [tab, loadResults])

  const voted = new Set(status?.voted_submission_ids ?? [])

  const toggleVote = async (sub: ProjectSubmission) => {
    setError(null)
    setBusyId(sub.id)
    try {
      const hasVoted = voted.has(sub.id)
      if (hasVoted) {
        await api.withdrawVote(eventId, sub.id)
      } else {
        await api.castVote(eventId, sub.id)
      }
      setCounts((prev) => {
        const current = prev[sub.id]
        if (current === null || current === undefined) return prev
        return { ...prev, [sub.id]: Math.max(0, current + (hasVoted ? -1 : 1)) }
      })
      await loadStatus()
    } catch (e: any) {
      setError(e instanceof ApiError && e.status === 429 ? "You're voting too fast — please wait a moment." : e.message)
      loadStatus()
    } finally {
      setBusyId(null)
    }
  }

  const isActive = Boolean(status?.is_active)
  const outOfVotes = status?.votes_remaining === 0

  const windowText = (() => {
    if (!status?.voting_start || !status?.voting_end) return "Community voting has not been scheduled for this event."
    const start = new Date(status.voting_start).toLocaleString()
    const end = new Date(status.voting_end).toLocaleString()
    if (status.is_active) return `Voting is open until ${end}.`
    if (status.has_ended) return `Voting closed on ${end}.`
    return `Voting opens ${start} and closes ${end}.`
  })()

  return (
    <div className="relative min-h-screen flex flex-col bg-background font-mono overflow-hidden">
      <Header />

      <div className="relative flex-1 p-4 sm:p-8 max-w-5xl mx-auto w-full space-y-8 z-10">
        <Squares
          direction="diagonal"
          speed={0.2}
          squareSize={48}
          borderColor="rgba(255, 255, 255, 0.03)"
          hoverFillColor="rgba(255, 255, 255, 0.06)"
          className="z-0 pointer-events-none fixed inset-0 h-full w-full"
        />

        <div className="relative z-10 space-y-6">
          <Link href={`/events/${eventId}`}>
            <Button variant="ghost" size="sm" className="h-7 text-[11px] font-mono hover:bg-muted/40 text-muted-foreground -ml-2 mb-2">
              <ArrowLeft className="size-3 mr-1" />
              Back to Event
            </Button>
          </Link>

          <div className="space-y-3 border-b border-border/20 pb-6">
            <h1 className="text-2xl font-light tracking-tight text-foreground flex items-center gap-2">
              <ThumbsUp className="size-5 text-emerald-400" />
              <span>Community Voting</span>
            </h1>
            <p className="text-xs text-muted-foreground">
              {event?.title ? `${event.title} · ` : ""}
              {windowText}
            </p>

            {status && (
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <Badge variant="outline" className={isActive ? "text-emerald-400 border-emerald-500/30" : "text-muted-foreground"}>
                  {isActive ? "OPEN" : status.has_ended ? "CLOSED" : "NOT OPEN"}
                </Badge>
                {user && status.eligible && (
                  <Badge variant="outline" className="text-foreground">
                    {status.votes_remaining === null
                      ? `${status.votes_used} votes cast · unlimited`
                      : `${status.votes_remaining} of ${status.votes_per_user} votes left`}
                  </Badge>
                )}
                {!status.results_visible && (
                  <Badge variant="outline" className="text-muted-foreground flex items-center gap-1">
                    <Lock className="size-3" /> counts hidden until voting closes
                  </Badge>
                )}
                <Badge variant="outline" className="text-muted-foreground flex items-center gap-1">
                  <Shuffle className="size-3" /> order randomized per viewer
                </Badge>
              </div>
            )}

            {!user ? (
              <p className="text-[11px] text-muted-foreground">
                <Link href="/login" className="text-primary hover:underline">
                  Sign in
                </Link>{" "}
                to vote and comment.
              </p>
            ) : status && !status.eligible && status.ineligible_reason ? (
              <p className="text-[11px] text-amber-400 flex items-center gap-1">
                <AlertCircle className="size-3" /> {status.ineligible_reason}
              </p>
            ) : null}
          </div>

          {error && (
            <div className="flex items-center gap-2 text-xs text-destructive bg-destructive/10 border border-destructive/20 p-2 rounded">
              <AlertCircle className="size-3.5" />
              <span>{error}</span>
            </div>
          )}

          <div className="flex items-center justify-between border-b border-border/20 pb-3 gap-4">
            <div className="flex gap-2">
              <Button
                variant={tab === "projects" ? "default" : "outline"}
                size="sm"
                onClick={() => setTab("projects")}
                className="h-7 text-xs font-mono"
              >
                Projects ({submissions.length})
              </Button>
              <Button
                variant={tab === "results" ? "default" : "outline"}
                size="sm"
                onClick={() => setTab("results")}
                className="h-7 text-xs font-mono"
              >
                <Trophy className="size-3 mr-1 text-amber-400" />
                Results
              </Button>
            </div>
            {tab === "projects" && (
              <div className="relative min-w-[200px]">
                <Search className="absolute left-2.5 top-2 size-3.5 text-muted-foreground pointer-events-none" />
                <Input
                  placeholder="Search projects or tech..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 bg-muted/20 border-border/40 font-mono text-xs h-7"
                />
              </div>
            )}
          </div>

          {tab === "results" ? (
            <div className="rounded-xl border border-border/40 bg-background/80 p-5 backdrop-blur-md">
              {resultsHidden ? (
                <div className="text-center space-y-1 py-6">
                  <Lock className="size-5 mx-auto text-muted-foreground" />
                  <div className="text-sm font-semibold text-foreground">Results are hidden</div>
                  <div className="text-xs text-muted-foreground">
                    Vote counts are revealed when voting closes
                    {status?.voting_end ? ` (${new Date(status.voting_end).toLocaleString()})` : ""}, so early leaders don&apos;t
                    snowball.
                  </div>
                </div>
              ) : !results ? (
                <div className="text-xs text-muted-foreground flex items-center gap-2">
                  <Loader2 className="size-3 animate-spin" /> loading results...
                </div>
              ) : (
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="border-b border-border/40 text-[11px] text-muted-foreground uppercase">
                      <th className="py-2 px-2 font-normal w-12">Rank</th>
                      <th className="py-2 px-2 font-normal">Project</th>
                      <th className="py-2 px-2 font-normal text-right">Votes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/20">
                    {results.results.map((r) => (
                      <tr key={r.submission_id}>
                        <td className="py-2 px-2">#{r.rank}</td>
                        <td className="py-2 px-2">
                          <div className="text-foreground font-semibold">{r.submission_title}</div>
                          <div className="text-[11px] text-muted-foreground">
                            {r.team_name}
                            {r.track ? ` · ${r.track}` : ""}
                          </div>
                        </td>
                        <td className="py-2 px-2 text-right text-emerald-400 font-bold">{r.votes}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ) : loading ? (
            <div className="p-12 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
              <Loader2 className="size-4 animate-spin text-foreground" />
              Loading submissions...
            </div>
          ) : submissions.length === 0 ? (
            <div className="p-12 border border-border/30 rounded-xl bg-background/80 backdrop-blur-md text-center space-y-2">
              <div className="text-sm font-semibold text-foreground">No Projects Found</div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {submissions.map((sub) => {
                const isExpanded = expandedId === sub.id
                const presentationFileUrl = getMediaUrl(sub.presentation_file)
                const hasVoted = voted.has(sub.id)
                const isOwn = status?.own_submission_id === sub.id
                const blockedOwn = isOwn && !status?.allow_self_vote
                const disabled =
                  !user ||
                  !isActive ||
                  !status?.eligible ||
                  blockedOwn ||
                  busyId === sub.id ||
                  (!hasVoted && outOfVotes)
                const title = !user
                  ? "Sign in to vote"
                  : !isActive
                  ? "Voting is not open"
                  : blockedOwn
                  ? "You can't vote for your own team"
                  : !hasVoted && outOfVotes
                  ? "No votes left — withdraw one first"
                  : undefined
                const count = counts[sub.id]

                return (
                  <div
                    key={sub.id}
                    className={`p-5 rounded-xl border ${
                      hasVoted ? "border-emerald-500/50" : "border-border/40"
                    } bg-background/80 backdrop-blur-md shadow-lg space-y-4 hover:border-emerald-500/30 transition-colors flex flex-col justify-between`}
                  >
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h3 className="font-semibold text-base text-foreground">{sub.title || "Untitled Project"}</h3>
                          {/* Team names hidden during voting to reduce popularity bias */}
                          <div className="text-[11px] text-muted-foreground font-mono">
                            {isOwn ? "Your team" : "Anonymous Team"}
                          </div>
                        </div>

                        <div className="flex flex-col items-end gap-1.5 shrink-0">
                          {sub.track_title && (
                            <Badge
                              variant="outline"
                              className="text-[9px] uppercase tracking-wider text-purple-400 border-purple-500/30 bg-purple-500/10 py-0"
                            >
                              {sub.track_title}
                            </Badge>
                          )}
                          <Button
                            size="sm"
                            disabled={disabled}
                            title={title}
                            onClick={() => toggleVote(sub)}
                            className={`h-7 text-[11px] font-mono px-3 ${
                              hasVoted
                                ? "bg-emerald-500 text-black hover:bg-emerald-600"
                                : "bg-muted/40 hover:bg-emerald-500/20 text-foreground"
                            }`}
                          >
                            {busyId === sub.id ? (
                              <Loader2 className="size-3 animate-spin" />
                            ) : (
                              <ThumbsUp className={`size-3 mr-1 ${hasVoted ? "" : "text-muted-foreground"}`} />
                            )}
                            {hasVoted ? "Voted" : "Vote"}
                            {count !== null && count !== undefined && <span className="ml-1 opacity-80">({count})</span>}
                          </Button>
                        </div>
                      </div>

                      {sub.tagline && <p className="text-xs text-muted-foreground italic font-sans">&quot;{sub.tagline}&quot;</p>}

                      {sub.tech_stack && (
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {sub.tech_stack.split(",").map((tech, idx) => (
                            <span
                              key={idx}
                              className="text-[10px] font-mono text-muted-foreground bg-muted/30 border border-border/40 px-1.5 py-0.5 rounded-sm whitespace-nowrap"
                            >
                              {tech.trim()}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="space-y-3 pt-2">
                      <div className="grid grid-cols-2 gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setExpandedId(isExpanded ? null : sub.id)}
                          className="h-7 text-[11px] font-mono bg-muted/20 hover:bg-muted/40 justify-between text-muted-foreground"
                        >
                          {isExpanded ? "Hide details" : "Details & links"}
                          {isExpanded ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setCommentsOpen((p) => ({ ...p, [sub.id]: !p[sub.id] }))}
                          className="h-7 text-[11px] font-mono bg-muted/20 hover:bg-muted/40 justify-between text-muted-foreground"
                        >
                          <span className="flex items-center gap-1">
                            <MessageSquare className="size-3" /> Comments ({commentCounts[sub.id] ?? 0})
                          </span>
                          {commentsOpen[sub.id] ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                        </Button>
                      </div>

                      {isExpanded && (
                        <div className="pt-2 pb-1 space-y-4 text-[11px] border-t border-border/20 text-muted-foreground">
                          {sub.problem_statement && (
                            <div className="space-y-1">
                              <h4 className="text-foreground font-semibold uppercase tracking-wider text-[10px]">Problem Statement</h4>
                              <div className="whitespace-pre-wrap font-sans text-xs">{sub.problem_statement}</div>
                            </div>
                          )}
                          {sub.solution_description && (
                            <div className="space-y-1">
                              <h4 className="text-foreground font-semibold uppercase tracking-wider text-[10px]">
                                Solution & Architecture
                              </h4>
                              <div className="whitespace-pre-wrap font-sans text-xs">{sub.solution_description}</div>
                            </div>
                          )}
                          <div className="flex flex-wrap gap-2 pt-2 border-t border-border/20">
                            {sub.github_url && (
                              <a href={sub.github_url} target="_blank" rel="noreferrer">
                                <Button variant="outline" size="sm" className="h-6 text-[10px] px-2">
                                  <Code className="size-3 mr-1" /> Repo
                                </Button>
                              </a>
                            )}
                            {sub.demo_url && (
                              <a href={sub.demo_url} target="_blank" rel="noreferrer">
                                <Button variant="outline" size="sm" className="h-6 text-[10px] px-2">
                                  <Video className="size-3 mr-1" /> Demo
                                </Button>
                              </a>
                            )}
                            {(sub.presentation_url || presentationFileUrl) && (
                              <a href={sub.presentation_url || presentationFileUrl || "#"} target="_blank" rel="noreferrer">
                                <Button variant="outline" size="sm" className="h-6 text-[10px] px-2">
                                  <Presentation className="size-3 mr-1" /> Slides
                                </Button>
                              </a>
                            )}
                          </div>
                        </div>
                      )}

                      {commentsOpen[sub.id] && (
                        <CommentThread
                          eventId={eventId}
                          submissionId={sub.id}
                          canPost={Boolean(user && (status?.comments_enabled ?? true))}
                          onCountChange={(n) => setCommentCounts((p) => (p[sub.id] === n ? p : { ...p, [sub.id]: n }))}
                        />
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
