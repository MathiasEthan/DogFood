"use client"

import React, { useEffect, useState } from "react"
import Link from "next/link"
import {
  api,
  Event as EventType,
  CommunityVoteRecord,
  CommunityAuditEntry,
} from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  AlertCircle,
  CheckCircle2,
  Download,
  Eye,
  EyeOff,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  ThumbsUp,
  Trophy,
} from "lucide-react"

function toLocalInput(iso?: string | null): string {
  if (!iso) return ""
  const d = new Date(iso)
  const offset = d.getTimezoneOffset() * 60000
  return new Date(d.getTime() - offset).toISOString().slice(0, 16)
}

function fromLocalInput(value: string): string | null {
  return value ? new Date(value).toISOString() : null
}

/**
 * Organizer-only controls for T3 community voting and T2 result publication:
 * voting window + rules, publishing judged results, abuse review, audit-chain verification and exports.
 */
export function CommunityVotingPanel({
  event,
  onUpdated,
}: {
  event: EventType
  onUpdated: () => void
}) {
  const [form, setForm] = useState({
    community_voting_start: toLocalInput(event.community_voting_start),
    community_voting_end: toLocalInput(event.community_voting_end),
    votes_per_user: String(event.votes_per_user ?? 3),
    voting_eligibility: event.voting_eligibility ?? "any",
    allow_self_vote: Boolean(event.allow_self_vote),
    show_community_voting_results: Boolean(event.show_community_voting_results),
    comments_enabled: event.comments_enabled ?? true,
  })
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  const [flaggedVotes, setFlaggedVotes] = useState<CommunityVoteRecord[]>([])
  const [audit, setAudit] = useState<CommunityAuditEntry[]>([])
  const [chain, setChain] = useState<{ valid: boolean; entries_checked: number; first_invalid_entry_id?: number } | null>(null)
  const [loadingReview, setLoadingReview] = useState(false)

  const loadReview = async () => {
    setLoadingReview(true)
    try {
      const [votes, log, verify] = await Promise.all([
        api.listCommunityVotes(event.id, { flagged: true }),
        api.getCommunityAudit(event.id),
        api.verifyCommunityAudit(event.id),
      ])
      setFlaggedVotes(votes)
      setAudit(log.slice(0, 15))
      setChain(verify)
    } catch (e: any) {
      setMessage({ ok: false, text: e.message || "Failed to load moderation data" })
    } finally {
      setLoadingReview(false)
    }
  }

  useEffect(() => {
    loadReview()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [event.id])

  const save = async () => {
    setSaving(true)
    setMessage(null)
    try {
      const votes = parseInt(form.votes_per_user, 10)
      await api.updateEventAdmin(event.id, {
        community_voting_start: fromLocalInput(form.community_voting_start),
        community_voting_end: fromLocalInput(form.community_voting_end),
        votes_per_user: Number.isNaN(votes) ? 0 : Math.max(0, votes),
        voting_eligibility: form.voting_eligibility as "any" | "registered",
        allow_self_vote: form.allow_self_vote,
        show_community_voting_results: form.show_community_voting_results,
        comments_enabled: form.comments_enabled,
      })
      setMessage({ ok: true, text: "Voting settings saved (change recorded in the audit trail)." })
      onUpdated()
      loadReview()
    } catch (e: any) {
      setMessage({ ok: false, text: e.message || "Failed to save settings" })
    } finally {
      setSaving(false)
    }
  }

  const togglePublish = async () => {
    const next = !event.results_published
    const prompt = next
      ? "Publish the judging leaderboard? Judges will no longer be able to change scores."
      : "Hide the judging leaderboard again? Judges will be able to edit scores."
    if (!confirm(prompt)) return
    try {
      await api.publishResults(event.id, next)
      setMessage({ ok: true, text: next ? "Judging results published." : "Judging results hidden." })
      onUpdated()
    } catch (e: any) {
      setMessage({ ok: false, text: e.message })
    }
  }

  const voidVote = async (vote: CommunityVoteRecord) => {
    const reason = window.prompt(`Reason for voiding @${vote.voter_username}'s vote on "${vote.submission_title}":`)
    if (!reason) return
    try {
      await api.voidCommunityVote(event.id, vote.id, reason)
      loadReview()
    } catch (e: any) {
      setMessage({ ok: false, text: e.message })
    }
  }

  const download = (url: string) => window.open(url, "_blank")

  return (
    <div className="rounded-xl border border-border/40 bg-background/80 p-5 backdrop-blur-md space-y-5 shadow-2xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/30 pb-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground flex items-center gap-2">
            <ThumbsUp className="size-4 text-emerald-400" />
            Community Voting & Results
          </h2>
          <p className="text-[11px] text-muted-foreground">
            Organizer controls. Every change here is written to a tamper-evident audit trail.
          </p>
        </div>
        <Link
          href={`/events/${event.id}/voting`}
          className="text-xs font-mono text-primary hover:text-primary/80 border border-primary/20 bg-primary/5 rounded-md px-2.5 py-1"
        >
          Open voting page →
        </Link>
      </div>

      {message && (
        <div
          className={`flex items-center gap-2 text-xs p-2 rounded border ${
            message.ok
              ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
              : "text-destructive bg-destructive/10 border-destructive/20"
          }`}
        >
          {message.ok ? <CheckCircle2 className="size-3.5" /> : <AlertCircle className="size-3.5" />}
          <span>{message.text}</span>
        </div>
      )}

      {/* Judging results publication */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg border border-border/40 bg-muted/10">
        <div className="text-xs">
          <div className="font-semibold text-foreground flex items-center gap-1.5">
            <Trophy className="size-3.5 text-amber-400" /> Judging leaderboard
          </div>
          <div className="text-[11px] text-muted-foreground">
            {event.results_published
              ? "Published — visible to everyone with anonymized judge feedback. Scoring is locked."
              : "Hidden from participants and judges (prevents anchoring). Only you can see standings."}
          </div>
        </div>
        <Button size="sm" variant={event.results_published ? "outline" : "default"} onClick={togglePublish} className="h-7 text-xs font-mono">
          {event.results_published ? <EyeOff className="size-3 mr-1" /> : <Eye className="size-3 mr-1" />}
          {event.results_published ? "Unpublish" : "Publish results"}
        </Button>
      </div>

      {/* Voting settings */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
        <div className="space-y-1">
          <Label className="text-[11px] uppercase text-muted-foreground">Voting opens</Label>
          <Input
            type="datetime-local"
            value={form.community_voting_start}
            onChange={(e) => setForm({ ...form, community_voting_start: e.target.value })}
            className="h-8 text-xs font-mono"
          />
        </div>
        <div className="space-y-1">
          <Label className="text-[11px] uppercase text-muted-foreground">Voting closes</Label>
          <Input
            type="datetime-local"
            value={form.community_voting_end}
            onChange={(e) => setForm({ ...form, community_voting_end: e.target.value })}
            className="h-8 text-xs font-mono"
          />
        </div>
        <div className="space-y-1">
          <Label className="text-[11px] uppercase text-muted-foreground">Votes per user (0 = unlimited)</Label>
          <Input
            type="number"
            min={0}
            value={form.votes_per_user}
            onChange={(e) => setForm({ ...form, votes_per_user: e.target.value })}
            className="h-8 text-xs font-mono"
          />
        </div>
        <div className="space-y-1">
          <Label className="text-[11px] uppercase text-muted-foreground">Who can vote</Label>
          <select
            value={form.voting_eligibility}
            onChange={(e) => setForm({ ...form, voting_eligibility: e.target.value as "any" | "registered" })}
            className="w-full h-8 rounded-md border border-border/40 bg-muted/20 px-2 text-xs font-mono"
          >
            <option value="any">Any signed-in user</option>
            <option value="registered">Only registered participants of this event</option>
          </select>
        </div>
        {[
          ["allow_self_vote", "Allow voting for your own team"],
          ["show_community_voting_results", "Show live vote counts during voting"],
          ["comments_enabled", "Allow comments on projects"],
        ].map(([key, label]) => (
          <label key={key} className="flex items-center gap-2 text-xs text-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={Boolean(form[key as keyof typeof form])}
              onChange={(e) => setForm({ ...form, [key]: e.target.checked })}
            />
            {label}
          </label>
        ))}
      </div>
      <div className="flex justify-end">
        <Button size="sm" onClick={save} disabled={saving} className="h-7 text-xs font-mono">
          {saving && <Loader2 className="size-3 mr-1 animate-spin" />}
          Save voting settings
        </Button>
      </div>

      {/* Abuse review */}
      <div className="space-y-2 border-t border-border/30 pt-4">
        <div className="flex items-center justify-between">
          <div className="text-[11px] font-mono uppercase text-muted-foreground flex items-center gap-1.5">
            <ShieldAlert className="size-3 text-amber-400" /> Flagged votes ({flaggedVotes.length})
          </div>
          <Button variant="ghost" size="sm" onClick={loadReview} className="h-6 text-[11px] font-mono">
            {loadingReview ? <Loader2 className="size-3 animate-spin" /> : "refresh"}
          </Button>
        </div>
        {flaggedVotes.length === 0 ? (
          <p className="text-[11px] text-muted-foreground">No votes flagged by the abuse heuristics.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[11px] font-mono">
              <thead>
                <tr className="text-muted-foreground border-b border-border/30">
                  <th className="py-1.5 pr-2 font-normal">Voter</th>
                  <th className="py-1.5 pr-2 font-normal">Project</th>
                  <th className="py-1.5 pr-2 font-normal">Flags</th>
                  <th className="py-1.5 font-normal text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {flaggedVotes.map((v) => (
                  <tr key={v.id}>
                    <td className="py-1.5 pr-2">@{v.voter_username}</td>
                    <td className="py-1.5 pr-2">{v.submission_title}</td>
                    <td className="py-1.5 pr-2">
                      {v.flags.map((f) => (
                        <Badge key={f} variant="outline" className="mr-1 text-[9px] text-amber-400 border-amber-500/30">
                          {f}
                        </Badge>
                      ))}
                    </td>
                    <td className="py-1.5 text-right">
                      {v.is_void ? (
                        <span className="text-muted-foreground">void</span>
                      ) : (
                        <Button variant="outline" size="xs" onClick={() => voidVote(v)} className="h-5 text-[10px]">
                          void
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Audit trail */}
      <div className="space-y-2 border-t border-border/30 pt-4">
        <div className="flex items-center justify-between">
          <div className="text-[11px] font-mono uppercase text-muted-foreground">Recent audit entries</div>
          {chain && (
            <span
              className={`text-[11px] font-mono flex items-center gap-1 ${chain.valid ? "text-emerald-400" : "text-destructive"}`}
            >
              {chain.valid ? <ShieldCheck className="size-3" /> : <ShieldAlert className="size-3" />}
              {chain.valid
                ? `Hash chain intact (${chain.entries_checked} entries)`
                : `Chain broken at entry #${chain.first_invalid_entry_id}`}
            </span>
          )}
        </div>
        <div className="max-h-48 overflow-y-auto space-y-1">
          {audit.length === 0 ? (
            <p className="text-[11px] text-muted-foreground">No community activity yet.</p>
          ) : (
            audit.map((a) => (
              <div key={a.id} className="text-[11px] font-mono text-muted-foreground flex gap-2">
                <span className="shrink-0">{new Date(a.timestamp).toLocaleString()}</span>
                <span className={a.flagged ? "text-amber-400" : "text-foreground"}>{a.action}</span>
                <span className="truncate">
                  {a.username ? `@${a.username}` : ""} {a.submission_title ? `→ ${a.submission_title}` : ""}
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Exports */}
      <div className="flex flex-wrap gap-2 border-t border-border/30 pt-4">
        {[
          ["Submissions CSV", api.getSubmissionsCsvUrl(event.id)],
          ["Judge assignments CSV", api.getAssignmentsCsvUrl(event.id)],
          ["Leaderboard CSV", api.getLeaderboardCsvUrl(event.id)],
          ["Rubric breakdown CSV", api.getRubricsCsvUrl(event.id)],
          ["Judge feedback CSV", api.getFeedbackCsvUrl(event.id)],
          ["Evaluation audit CSV", api.getEvaluationAuditCsvUrl(event.id)],
          ["Community votes CSV", api.getCommunityVotesCsvUrl(event.id)],
          ["Community audit CSV", api.getCommunityAuditCsvUrl(event.id)],
        ].map(([label, url]) => (
          <Button key={label} variant="outline" size="sm" onClick={() => download(url)} className="h-7 text-[11px] font-mono">
            <Download className="size-3 mr-1" />
            {label}
          </Button>
        ))}
      </div>
    </div>
  )
}
