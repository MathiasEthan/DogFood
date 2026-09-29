"use client"

import React, { useState, useEffect, use } from "react"
import { api, Event as EventType, ProjectSubmission } from "@/lib/api"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Search,
  Loader2,
  ExternalLink,
  Code,
  Video,
  Presentation,
  Shield,
  Layers,
  Award,
  Sparkles,
} from "lucide-react"

export default function EmbedGalleryPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params)
  const eventId = resolvedParams.id

  const [event, setEvent] = useState<EventType | null>(null)
  const [submissions, setSubmissions] = useState<ProjectSubmission[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")
  const [trackFilter, setTrackFilter] = useState("")
  const [selectedSubmission, setSelectedSubmission] = useState<ProjectSubmission | null>(null)

  useEffect(() => {
    let isMounted = true
    async function fetchData() {
      try {
        const [ev, subs] = await Promise.all([
          api.getEvent(eventId),
          api.listGallery(eventId, { q: searchQuery, track: trackFilter }),
        ])
        if (isMounted) {
          setEvent(ev)
          setSubmissions(subs)
        }
      } catch (err) {
        console.error("Embed gallery fetch error", err)
      } finally {
        if (isMounted) setLoading(false)
      }
    }
    fetchData()
    return () => {
      isMounted = false
    }
  }, [eventId, searchQuery, trackFilter])

  // PostMessage height resize protocol for seamless iframe integration
  useEffect(() => {
    const notifyHeight = () => {
      if (typeof window !== "undefined" && window.parent) {
        window.parent.postMessage(
          {
            type: "dogfood:embed:resize",
            height: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight),
          },
          "*"
        )
      }
    }
    notifyHeight()
    const timer = setTimeout(notifyHeight, 300)
    window.addEventListener("resize", notifyHeight)
    return () => {
      clearTimeout(timer)
      window.removeEventListener("resize", notifyHeight)
    }
  }, [submissions, loading, selectedSubmission])

  const tracks = event?.tracks || []

  return (
    <div className="min-h-screen bg-[#07090e] text-slate-100 p-4 sm:p-6 font-mono selection:bg-emerald-500/30 selection:text-emerald-300">
      {/* Widget Header */}
      <div className="max-w-7xl mx-auto mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-emerald-500/20 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              {event?.title || "Project Gallery"}
              <span className="text-xs font-normal text-emerald-400/80 border border-emerald-500/30 px-2 py-0.5 rounded bg-emerald-950/40">
                LIVE WIDGET
              </span>
            </h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {submissions.length} project{submissions.length === 1 ? "" : "s"} submitted
            {event?.prize_pool ? ` • Prize Pool: ${event.prize_pool}` : ""}
          </p>
        </div>

        {/* Search & Filter Bar */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[220px]">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input
              type="text"
              placeholder="Search projects, stack..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 h-8 text-xs bg-slate-900/80 border-slate-700/80 text-white placeholder:text-slate-500 focus-visible:ring-emerald-500"
            />
          </div>

          {tracks.length > 0 && (
            <select
              value={trackFilter}
              onChange={(e) => setTrackFilter(e.target.value)}
              aria-label="Filter by track"
              className="h-8 text-xs bg-slate-900/80 border border-slate-700/80 text-slate-200 rounded px-2.5 focus:outline-none focus:border-emerald-500"
            >
              <option value="">All Tracks</option>
              {tracks.map((t) => (
                <option key={t.id} value={t.id.toString()}>
                  {t.title}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Grid of Projects */}
      <div className="max-w-7xl mx-auto">
        {loading ? (
          <div className="py-20 flex flex-col items-center justify-center text-slate-400 gap-3">
            <Loader2 className="w-6 h-6 animate-spin text-emerald-400" />
            <p className="text-xs">Loading projects...</p>
          </div>
        ) : submissions.length === 0 ? (
          <div className="py-16 text-center border border-dashed border-slate-800 rounded-lg p-8">
            <Code className="w-8 h-8 text-slate-600 mx-auto mb-2" />
            <p className="text-sm text-slate-400 font-medium">No projects found</p>
            <p className="text-xs text-slate-600 mt-1">Try adjusting your search or track filters.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {submissions.map((sub) => {
              const techList = (sub.tech_stack || "")
                .split(",")
                .map((t) => t.trim())
                .filter(Boolean)

              return (
                <div
                  key={sub.id}
                  onClick={() => setSelectedSubmission(sub)}
                  className="group cursor-pointer rounded-lg border border-slate-800 bg-[#0d111a]/90 hover:border-emerald-500/50 hover:bg-[#111724] transition-all duration-200 p-4 flex flex-col justify-between shadow-lg relative overflow-hidden"
                >
                  <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-emerald-500/0 to-transparent group-hover:via-emerald-400 transition-all duration-300" />
                  
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <h3 className="font-semibold text-white text-base group-hover:text-emerald-400 transition-colors line-clamp-1">
                        {sub.title}
                      </h3>
                      {sub.track_title && (
                        <Badge variant="outline" className="text-[10px] border-emerald-500/30 text-emerald-300 shrink-0">
                          {sub.track_title}
                        </Badge>
                      )}
                    </div>

                    <p className="text-xs text-slate-400 font-mono mb-2">by {sub.team_name}</p>

                    <p className="text-xs text-slate-300 line-clamp-2 mb-3 leading-relaxed">
                      {sub.tagline || sub.solution_description || sub.problem_statement || "No description provided."}
                    </p>
                  </div>

                  <div>
                    {techList.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-3">
                        {techList.slice(0, 3).map((tech, i) => (
                          <span
                            key={i}
                            className="text-[10px] bg-slate-800/80 text-slate-300 border border-slate-700/50 px-1.5 py-0.5 rounded"
                          >
                            {tech}
                          </span>
                        ))}
                        {techList.length > 3 && (
                          <span className="text-[10px] text-slate-500 self-center">
                            +{techList.length - 3}
                          </span>
                        )}
                      </div>
                    )}

                    <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800/60">
                      <div className="flex items-center gap-2">
                        {sub.github_url && <Code className="w-3.5 h-3.5 text-slate-400 hover:text-white" />}
                        {sub.demo_url && <Video className="w-3.5 h-3.5 text-slate-400 hover:text-white" />}
                        {sub.presentation_url && <Presentation className="w-3.5 h-3.5 text-slate-400 hover:text-white" />}
                      </div>
                      <span className="text-[11px] text-emerald-400 group-hover:translate-x-0.5 transition-transform flex items-center gap-1">
                        View Details →
                      </span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Project Detail Modal */}
      {selectedSubmission && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setSelectedSubmission(null)}
        >
          <div
            className="bg-[#0e131f] border border-emerald-500/40 rounded-xl max-w-2xl w-full p-6 text-slate-200 max-h-[90vh] overflow-y-auto shadow-2xl relative"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 mb-4 border-b border-slate-800 pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold text-white">{selectedSubmission.title}</h2>
                  {selectedSubmission.track_title && (
                    <Badge variant="outline" className="border-emerald-500/40 text-emerald-300 text-xs">
                      {selectedSubmission.track_title}
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-slate-400 mt-0.5">Team: {selectedSubmission.team_name}</p>
              </div>
              <button
                onClick={() => setSelectedSubmission(null)}
                className="text-slate-400 hover:text-white text-lg font-bold p-1 leading-none"
              >
                ✕
              </button>
            </div>

            {selectedSubmission.tagline && (
              <p className="text-sm text-emerald-300/90 italic mb-4 font-sans">
                "{selectedSubmission.tagline}"
              </p>
            )}

            <div className="space-y-4 text-xs leading-relaxed">
              {selectedSubmission.problem_statement && (
                <div>
                  <h4 className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-1">
                    Problem Statement
                  </h4>
                  <p className="text-slate-300 bg-slate-900/60 p-3 rounded border border-slate-800/80">
                    {selectedSubmission.problem_statement}
                  </p>
                </div>
              )}

              {selectedSubmission.solution_description && (
                <div>
                  <h4 className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-1">
                    Solution Description
                  </h4>
                  <p className="text-slate-300 bg-slate-900/60 p-3 rounded border border-slate-800/80">
                    {selectedSubmission.solution_description}
                  </p>
                </div>
              )}

              {selectedSubmission.tech_stack && (
                <div>
                  <h4 className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-1.5">
                    Technologies Used
                  </h4>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedSubmission.tech_stack.split(",").map((tech, i) => (
                      <span
                        key={i}
                        className="bg-emerald-950/50 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded text-xs"
                      >
                        {tech.trim()}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Resource Links */}
              <div className="pt-2 border-t border-slate-800 flex flex-wrap gap-2">
                {selectedSubmission.github_url && (
                  <a
                    href={selectedSubmission.github_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-white border border-slate-700 transition-colors"
                  >
                    <Code className="w-3.5 h-3.5" /> Source Code <ExternalLink className="w-3 h-3 text-slate-400" />
                  </a>
                )}
                {selectedSubmission.demo_url && (
                  <a
                    href={selectedSubmission.demo_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-emerald-900/40 hover:bg-emerald-800/40 text-xs text-emerald-300 border border-emerald-700/50 transition-colors"
                  >
                    <Video className="w-3.5 h-3.5" /> Live Demo <ExternalLink className="w-3 h-3 text-emerald-400" />
                  </a>
                )}
                {selectedSubmission.presentation_url && (
                  <a
                    href={selectedSubmission.presentation_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-white border border-slate-700 transition-colors"
                  >
                    <Presentation className="w-3.5 h-3.5" /> Slides <ExternalLink className="w-3 h-3 text-slate-400" />
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Widget Footer */}
      <div className="max-w-7xl mx-auto mt-8 pt-4 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
        <div className="flex items-center gap-1.5">
          <Sparkles className="w-3 h-3 text-emerald-400" />
          <span>Interactive Embed Gallery</span>
        </div>
        <a
          href="/"
          target="_blank"
          rel="noreferrer"
          className="text-slate-400 hover:text-emerald-400 transition-colors flex items-center gap-1"
        >
          Powered by DogFood Platform <ExternalLink className="w-2.5 h-2.5" />
        </a>
      </div>
    </div>
  )
}
