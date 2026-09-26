"use client"

import React, { useEffect, useState, useMemo } from "react"
import Link from "next/link"
import { useAuth } from "@/context/auth-context"
import { Header } from "@/components/header"
import { Squares } from "@/components/reactbits/squares"
import { api, Event as EventType } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Calendar,
  Globe,
  Award,
  Users,
  PlusCircle,
  ArrowRight,
  Loader2,
  Sparkles,
  Search,
  X,
} from "lucide-react"

export default function Home() {
  const { user } = useAuth()
  const [events, setEvents] = useState<EventType[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")
  const [modeFilter, setModeFilter] = useState<"all" | "virtual" | "in_person" | "hybrid">("all")

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const data = await api.listEvents()
        setEvents(data)
      } catch (err) {
        console.error("Failed to load events", err)
      } finally {
        setLoading(false)
      }
    }
    fetchEvents()
  }, [])

  const filteredEvents = useMemo(() => {
    return events.filter((ev) => {
      const matchesMode = modeFilter === "all" || ev.mode === modeFilter
      const query = searchQuery.trim().toLowerCase()
      if (!query) return matchesMode

      const matchesText =
        ev.title.toLowerCase().includes(query) ||
        ev.description.toLowerCase().includes(query) ||
        ev.location.toLowerCase().includes(query) ||
        ev.prize_pool.toLowerCase().includes(query) ||
        ev.created_by_username.toLowerCase().includes(query)

      return matchesMode && matchesText
    })
  }, [events, searchQuery, modeFilter])

  const getMediaUrl = (url: string | null) => {
    if (!url) return null
    if (url.startsWith("http")) return url
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    return `${baseUrl}${url.startsWith("/") ? url : `/${url}`}`
  }

  return (
    <div className="relative min-h-screen flex flex-col bg-background font-mono select-none overflow-hidden">
      {/* Minimal Header */}
      <Header />

      {/* Main Viewport */}
      <div className="relative flex-1 p-4 sm:p-8 max-w-6xl mx-auto w-full space-y-8">
        <Squares
          direction="diagonal"
          speed={0.2}
          squareSize={48}
          borderColor="rgba(255, 255, 255, 0.03)"
          hoverFillColor="rgba(255, 255, 255, 0.06)"
          className="z-0 pointer-events-none"
        />

        <div className="relative z-10 space-y-8">
          {/* Top Title & Organizer Action */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/30 pb-6">
            <div className="space-y-1">
              <div className="inline-flex items-center gap-2 text-[10px] tracking-widest text-muted-foreground uppercase">
                <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Active Hackathons
              </div>
              <h1 className="text-xl sm:text-2xl font-light tracking-tight text-foreground">
                Explore Events & Build Teams
              </h1>
              <p className="text-xs text-muted-foreground">
                Join a hackathon, create a team, or join your friends with a team code
              </p>
            </div>

            {/* Organizer Event Creation CTA */}
            {user && (user.role === "organizer" || user.role === "admin") && (
              <Link href="/events/create">
                <Button size="sm" className="h-9 px-3.5 text-xs font-mono bg-foreground text-background hover:bg-foreground/90 gap-1.5">
                  <PlusCircle className="size-3.5" />
                  <span>Create Hackathon</span>
                </Button>
              </Link>
            )}
          </div>

          {/* Search Bar & Mode Filter Pills */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-background/80 border border-border/40 p-3 rounded-xl backdrop-blur-md">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
              <Input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search hackathons by title, description, location, or prize..."
                className="h-9 pl-9 pr-8 text-xs font-mono bg-muted/20 border-transparent focus-visible:border-border/60"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-2.5 text-muted-foreground hover:text-foreground"
                >
                  <X className="size-4" />
                </button>
              )}
            </div>

            {/* Filter Pills */}
            <div className="flex items-center gap-1 overflow-x-auto">
              {(["all", "virtual", "in_person", "hybrid"] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setModeFilter(mode)}
                  className={`h-8 px-2.5 rounded-md text-[11px] font-mono capitalize transition-colors whitespace-nowrap ${
                    modeFilter === mode
                      ? "bg-foreground text-background font-semibold"
                      : "text-muted-foreground hover:bg-muted/30"
                  }`}
                >
                  {mode.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>

          {/* Results Summary Counter */}
          {!loading && events.length > 0 && (
            <div className="flex items-center justify-between text-[11px] text-muted-foreground/80 px-1">
              <span>
                Showing {filteredEvents.length} of {events.length} hackathon{events.length === 1 ? "" : "s"}
              </span>
              {(searchQuery || modeFilter !== "all") && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchQuery("")
                    setModeFilter("all")
                  }}
                  className="text-foreground hover:underline"
                >
                  reset filters
                </button>
              )}
            </div>
          )}

          {/* Events Grid */}
          {loading ? (
            <div className="py-20 flex flex-col items-center justify-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="size-5 animate-spin text-primary" />
              <span>loading hackathons...</span>
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="rounded-xl border border-border/40 bg-background/60 p-12 text-center backdrop-blur-md space-y-4">
              <div className="p-3 w-fit mx-auto rounded-full bg-muted/20 text-muted-foreground">
                <Sparkles className="size-6" />
              </div>
              <div className="space-y-1 max-w-sm mx-auto">
                <h3 className="text-sm font-semibold text-foreground">
                  {events.length === 0 ? "No Events Active" : "No Matching Hackathons"}
                </h3>
                <p className="text-xs text-muted-foreground">
                  {events.length === 0
                    ? user && (user.role === "organizer" || user.role === "admin")
                      ? "You can publish the first event using the button above."
                      : "Organizers will publish new events soon."
                    : "No hackathons matched your search query or filter. Try a different search."}
                </p>
              </div>
              {events.length > 0 && (searchQuery || modeFilter !== "all") && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setSearchQuery("")
                    setModeFilter("all")
                  }}
                  className="text-xs font-mono"
                >
                  Clear Filters
                </Button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredEvents.map((event) => {
                const bannerSrc = getMediaUrl(event.banner)
                return (
                  <div
                    key={event.id}
                    className="group rounded-xl border border-border/40 bg-background/80 overflow-hidden backdrop-blur-md hover:border-border transition-all duration-300 flex flex-col shadow-lg"
                  >
                    {/* Banner Image or Fallback */}
                    {bannerSrc ? (
                      <div className="relative w-full aspect-[21/9] overflow-hidden border-b border-border/30 bg-muted/20">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={bannerSrc}
                          alt={event.title}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                        />
                      </div>
                    ) : (
                      <div className="w-full aspect-[21/9] bg-gradient-to-br from-primary/10 via-purple-500/10 to-emerald-500/10 border-b border-border/30 flex items-center justify-center p-4">
                        <span className="text-[10px] text-muted-foreground tracking-widest uppercase">
                          No Banner Uploaded
                        </span>
                      </div>
                    )}

                    <div className="p-5 flex-1 flex flex-col justify-between space-y-4">
                      <div className="space-y-2">
                        {/* Meta Tags */}
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full capitalize">
                            {event.mode.replace("_", " ")}
                          </span>
                          {event.prize_pool && (
                            <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
                              {event.prize_pool}
                            </span>
                          )}
                        </div>

                        {/* Event Title */}
                        <h2 className="text-base font-semibold text-foreground tracking-tight group-hover:text-primary transition-colors">
                          {event.title}
                        </h2>

                        {/* Description Preview */}
                        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                          {event.description}
                        </p>
                      </div>

                      {/* Footer Details */}
                      <div className="space-y-3 pt-2 border-t border-border/30 text-[11px] text-muted-foreground">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1">
                            <Calendar className="size-3 text-muted-foreground" />
                            <span>{new Date(event.start_date).toLocaleDateString()}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Users className="size-3 text-muted-foreground" />
                            <span>Teams: {event.teams_count}</span>
                          </div>
                        </div>

                        {(() => {
                          const now = new Date()
                          const isVotingActive = event.community_voting_start && event.community_voting_end && new Date(event.community_voting_start) <= now && now <= new Date(event.community_voting_end)
                          
                          if (isVotingActive) {
                            return (
                              <Link href={`/events/${event.id}/voting`} className="block">
                                <Button
                                  variant="default"
                                  size="sm"
                                  className="w-full text-xs font-mono justify-between bg-primary text-primary-foreground hover:bg-primary/90"
                                >
                                  <span>Community Voting Active - Vote Now</span>
                                  <ArrowRight className="size-3.5 group-hover:translate-x-0.5 transition-transform" />
                                </Button>
                              </Link>
                            )
                          }

                          return (
                            <Link href={`/events/${event.id}`} className="block">
                              <Button
                                variant="outline"
                                size="sm"
                                className="w-full text-xs font-mono justify-between group-hover:bg-muted/40"
                              >
                                <span>View Event & Teams</span>
                                <ArrowRight className="size-3.5 group-hover:translate-x-0.5 transition-transform" />
                              </Button>
                            </Link>
                          )
                        })()}
                      </div>
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
