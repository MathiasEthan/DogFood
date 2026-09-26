"use client"

import React, { useState, useEffect, use } from "react"
import Link from "next/link"
import { useAuth } from "@/context/auth-context"
import { Header } from "@/components/header"
import { Squares } from "@/components/reactbits/squares"
import { api, Event as EventType, ProjectSubmission } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  ArrowLeft,
  Search,
  Loader2,
  Code,
  Video,
  Presentation,
  ChevronDown,
  ChevronUp,
  ThumbsUp,
  ExternalLink,
} from "lucide-react"

export default function CommunityVotingPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params)
  const eventId = resolvedParams.id
  const { user } = useAuth()
  
  const [event, setEvent] = useState<EventType | null>(null)
  const [submissions, setSubmissions] = useState<ProjectSubmission[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [votingState, setVotingState] = useState<Record<number, { count: number | null, voted: boolean }>>({})
  const [actionLoading, setActionLoading] = useState<Record<number, boolean>>({})

  const loadData = async () => {
    try {
      const [ev, subs] = await Promise.all([
        api.getEvent(eventId),
        api.listGallery(eventId, { q: searchQuery }),
      ])
      setEvent(ev)
      setSubmissions(subs)
      
      const vState: Record<number, { count: number | null, voted: boolean }> = {}
      subs.forEach(s => {
        vState[s.id] = { count: s.community_vote_count ?? null, voted: s.has_voted ?? false }
      })
      setVotingState(vState)
    } catch (e) {
      console.error("Failed to load voting data", e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [eventId, searchQuery])

  const handleVote = async (subId: number) => {
    if (!user) {
      alert("Please login to vote.")
      return
    }
    setActionLoading(prev => ({ ...prev, [subId]: true }))
    try {
      const res = await api.castVote(eventId, subId)
      setVotingState(prev => {
        const current = prev[subId]
        let newCount = current.count
        if (newCount !== null) {
           newCount = res.has_voted ? newCount + 1 : Math.max(0, newCount - 1)
        }
        return {
          ...prev,
          [subId]: { count: newCount, voted: res.has_voted }
        }
      })
    } catch (e: any) {
      alert(e.message || "Failed to cast vote")
    } finally {
      setActionLoading(prev => ({ ...prev, [subId]: false }))
    }
  }

  const getMediaUrl = (url: string | null) => {
    if (!url) return null
    if (url.startsWith("http")) return url
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    return `${baseUrl}${url.startsWith("/") ? url : `/${url}`}`
  }

  const now = new Date()
  const isVotingActive = event?.community_voting_start && event?.community_voting_end && 
                         new Date(event.community_voting_start) <= now && 
                         now <= new Date(event.community_voting_end)

  return (
    <div className="relative min-h-screen flex flex-col bg-background font-mono overflow-hidden select-none">
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

          <div className="space-y-2 border-b border-border/20 pb-6">
            <h1 className="text-2xl font-light tracking-tight text-foreground flex items-center gap-2">
              <ThumbsUp className="size-5 text-emerald-400" />
              <span>Community Voting</span>
            </h1>
            <p className="text-xs text-muted-foreground">
              {event?.title ? `Vote for your favorite projects in ${event.title}. ` : ""}
              {isVotingActive 
                ? "Browse the randomized list below and cast your votes!" 
                : "Voting is currently closed for this event."}
            </p>
          </div>

          <div className="flex items-center justify-between border-b border-border/20 pb-3 gap-4">
             <div className="text-sm font-semibold text-foreground">
                All Projects ({submissions.length})
             </div>
             <div className="relative min-w-[200px]">
                <Search className="absolute left-2.5 top-2 size-3.5 text-muted-foreground pointer-events-none" />
                <Input
                  placeholder="Search projects or tech..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 bg-muted/20 border-border/40 font-mono text-xs h-7"
                />
              </div>
          </div>

          {loading ? (
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
                const vState = votingState[sub.id] || { count: null, voted: false }

                return (
                  <div
                    key={sub.id}
                    className={`p-5 rounded-xl border ${vState.voted ? 'border-emerald-500/50' : 'border-border/40'} bg-background/80 backdrop-blur-md shadow-lg space-y-4 hover:border-emerald-500/30 transition-colors flex flex-col justify-between`}
                  >
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h3 className="font-semibold text-base text-foreground">
                            {sub.title || "Untitled Project"}
                          </h3>
                          {/* Hide Team Name to prevent bias */}
                          <div className="text-[11px] text-muted-foreground font-mono">
                            Anonymous Team
                          </div>
                        </div>

                        <div className="flex flex-col items-end gap-1.5 shrink-0">
                          {sub.track && (
                            <Badge
                              variant="outline"
                              className="text-[9px] uppercase tracking-wider text-purple-400 border-purple-500/30 bg-purple-500/10 py-0"
                            >
                              Track {sub.track}
                            </Badge>
                          )}
                          <Button
                            size="sm"
                            disabled={!isVotingActive || actionLoading[sub.id]}
                            onClick={() => handleVote(sub.id)}
                            className={`h-7 text-[11px] font-mono px-3 ${vState.voted ? 'bg-emerald-500 text-black hover:bg-emerald-600' : 'bg-muted/40 hover:bg-emerald-500/20 text-foreground'}`}
                          >
                            {actionLoading[sub.id] ? (
                              <Loader2 className="size-3 animate-spin" />
                            ) : (
                              <ThumbsUp className={`size-3 mr-1 ${vState.voted ? '' : 'text-muted-foreground'}`} />
                            )}
                            {vState.voted ? "Voted" : "Vote"}
                            {vState.count !== null && (
                              <span className="ml-1 opacity-80">({vState.count})</span>
                            )}
                          </Button>
                        </div>
                      </div>

                      {sub.tagline && (
                        <p className="text-xs text-muted-foreground italic font-sans">
                          &quot;{sub.tagline}&quot;
                        </p>
                      )}

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
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setExpandedId(isExpanded ? null : sub.id)}
                        className="w-full h-7 text-[11px] font-mono bg-muted/20 hover:bg-muted/40 justify-between text-muted-foreground"
                      >
                        {isExpanded ? "Hide Details" : "Read More & View Links"}
                        {isExpanded ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                      </Button>

                      {isExpanded && (
                        <div className="pt-2 pb-1 space-y-4 text-[11px] border-t border-border/20 text-muted-foreground animate-in slide-in-from-top-2">
                          {sub.problem_statement && (
                            <div className="space-y-1">
                              <h4 className="text-foreground font-semibold flex items-center gap-1.5 uppercase tracking-wider text-[10px]">
                                Problem Statement
                              </h4>
                              <div className="whitespace-pre-wrap font-sans text-xs">
                                {sub.problem_statement}
                              </div>
                            </div>
                          )}

                          {sub.solution_description && (
                            <div className="space-y-1">
                              <h4 className="text-foreground font-semibold flex items-center gap-1.5 uppercase tracking-wider text-[10px]">
                                Solution & Architecture
                              </h4>
                              <div className="whitespace-pre-wrap font-sans text-xs">
                                {sub.solution_description}
                              </div>
                            </div>
                          )}

                          <div className="flex flex-wrap gap-2 pt-2 border-t border-border/20">
                            {sub.github_url && (
                              <a href={sub.github_url} target="_blank" rel="noreferrer">
                                <Button variant="outline" size="sm" className="h-6 text-[10px] px-2 text-primary hover:text-primary hover:border-primary/50">
                                  <Code className="size-3 mr-1" /> Repo
                                </Button>
                              </a>
                            )}
                            {sub.demo_url && (
                              <a href={sub.demo_url} target="_blank" rel="noreferrer">
                                <Button variant="outline" size="sm" className="h-6 text-[10px] px-2 text-primary hover:text-primary hover:border-primary/50">
                                  <Video className="size-3 mr-1" /> Demo
                                </Button>
                              </a>
                            )}
                            {(sub.presentation_url || presentationFileUrl) && (
                              <a
                                href={sub.presentation_url || presentationFileUrl || "#"}
                                target="_blank"
                                rel="noreferrer"
                              >
                                <Button variant="outline" size="sm" className="h-6 text-[10px] px-2 text-primary hover:text-primary hover:border-primary/50">
                                  <Presentation className="size-3 mr-1" /> Slides
                                </Button>
                              </a>
                            )}
                          </div>
                        </div>
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
