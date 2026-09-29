"use client"

import React, { useCallback, useEffect, useState } from "react"
import { api, Event as EventType, JudgingProgressResponse } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { AlertCircle, CheckCircle2, Gauge, Loader2, RefreshCw, Scale, TriangleAlert } from "lucide-react"

const fmt = (v: number | null | undefined, digits = 2) => (v === null || v === undefined ? "—" : v.toFixed(digits))

/**
 * Organizer-only judge progress dashboard (T2): algorithmic assignment, per-judge telemetry
 * (completion, review time, calibration μ/σ, flatline warning) and a per-project saturation matrix
 * with raw vs normalized scores.
 */
export function JudgingProgressPanel({ event, onUpdated }: { event: EventType; onUpdated: () => void }) {
  const [data, setData] = useState<JudgingProgressResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [k, setK] = useState(String(event.judges_per_project ?? 3))
  const [assigning, setAssigning] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await api.getJudgingProgress(event.id))
    } catch (e: any) {
      setMessage({ ok: false, text: e.message || "Failed to load judging progress" })
    } finally {
      setLoading(false)
    }
  }, [event.id])

  useEffect(() => {
    load()
  }, [load])

  const runAssignment = async () => {
    setAssigning(true)
    setMessage(null)
    try {
      const res = await api.assignJudges(event.id, Math.max(1, parseInt(k, 10) || 3))
      const workload = Object.entries(res.workload_distribution)
        .map(([name, n]) => `@${name}: ${n}`)
        .join(", ")
      setMessage({
        ok: !res.warning,
        text:
          `Assigned ${res.total_submissions} project(s) to ${res.total_judges} judge(s), K=${res.target_k}, ` +
          `${res.total_assignments_created} new assignment(s), zero conflicts of interest. Workload → ${workload}.` +
          (res.warning ? ` ⚠ ${res.warning}` : ""),
      })
      onUpdated()
      load()
    } catch (e: any) {
      setMessage({ ok: false, text: e.message || "Assignment failed" })
    } finally {
      setAssigning(false)
    }
  }

  const s = data?.summary

  return (
    <div className="rounded-xl border border-border/40 bg-background/80 p-5 backdrop-blur-md space-y-5 shadow-2xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/30 pb-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground flex items-center gap-2">
            <Gauge className="size-4 text-primary" />
            Judge Assignment & Progress
          </h2>
          <p className="text-[11px] text-muted-foreground">
            Conflict-free load-balanced assignment, live review progress and cross-judge calibration.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-muted-foreground font-mono">Judges per project (K)</span>
          <Input
            type="number"
            min={1}
            max={20}
            value={k}
            onChange={(e) => setK(e.target.value)}
            className="h-7 w-16 text-xs font-mono"
            aria-label="Judges per project"
          />
          <Button size="sm" onClick={runAssignment} disabled={assigning} className="h-7 text-xs font-mono">
            {assigning ? <Loader2 className="size-3 mr-1 animate-spin" /> : <Scale className="size-3 mr-1" />}
            Run auto-assignment
          </Button>
          <Button size="sm" variant="ghost" onClick={load} className="h-7 text-xs font-mono" aria-label="Refresh progress">
            <RefreshCw className={`size-3 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {message && (
        <div
          className={`flex items-start gap-2 text-xs p-2 rounded border ${
            message.ok
              ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
              : "text-amber-400 bg-amber-500/10 border-amber-500/20"
          }`}
        >
          {message.ok ? <CheckCircle2 className="size-3.5 mt-0.5 shrink-0" /> : <AlertCircle className="size-3.5 mt-0.5 shrink-0" />}
          <span>{message.text}</span>
        </div>
      )}

      {s && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
          {[
            ["Projects", s.total_submissions],
            ["Judges", s.total_judges],
            ["Reviews done", `${s.completed_assignments}/${s.total_assignments}`],
            ["Progress", `${s.overall_progress_percent}%`],
            ["Target K", s.target_reviews_per_project ?? "—"],
            ["Fully reviewed", `${s.saturation_percent ?? 0}%`],
            ["Under-reviewed", s.under_reviewed_count],
            ["Flagged scores", s.flagged_evaluations ?? 0],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded-lg border border-border/40 bg-muted/10 p-2.5">
              <div className="text-[10px] uppercase text-muted-foreground">{label}</div>
              <div className="text-base font-semibold text-foreground">{value}</div>
            </div>
          ))}
        </div>
      )}

      {data && (
        <div className="space-y-2">
          <div className="text-[11px] font-mono uppercase text-muted-foreground">Judges</div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[11px] font-mono">
              <thead>
                <tr className="text-muted-foreground border-b border-border/30">
                  <th className="py-1.5 pr-2 font-normal">Judge</th>
                  <th className="py-1.5 pr-2 font-normal">Done</th>
                  <th className="py-1.5 pr-2 font-normal w-40">Progress</th>
                  <th className="py-1.5 pr-2 font-normal">Avg review</th>
                  <th className="py-1.5 pr-2 font-normal">Raw mean</th>
                  <th className="py-1.5 pr-2 font-normal">Calibrated μ / σ</th>
                  <th className="py-1.5 font-normal">Flags</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {data.judges.map((j) => (
                  <tr key={j.judge_id}>
                    <td className="py-1.5 pr-2 text-foreground">@{j.username}</td>
                    <td className="py-1.5 pr-2">
                      {j.completed}/{j.assigned}
                    </td>
                    <td className="py-1.5 pr-2">
                      <div className="h-1.5 rounded bg-muted/40 overflow-hidden">
                        <div className="h-full bg-emerald-500" style={{ width: `${j.progress_percent}%` }} />
                      </div>
                    </td>
                    <td className="py-1.5 pr-2">{j.avg_review_seconds ? `${Math.round(j.avg_review_seconds)}s` : "—"}</td>
                    <td className="py-1.5 pr-2">{fmt(j.raw_mean)}</td>
                    <td className="py-1.5 pr-2">
                      {fmt(j.shrunk_mean)} / {fmt(j.shrunk_std)}
                    </td>
                    <td className="py-1.5">
                      {j.flatline_warning ? (
                        <Badge variant="outline" className="text-[9px] text-amber-400 border-amber-500/30">
                          <TriangleAlert className="size-3 mr-1" /> flatline
                        </Badge>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data?.projects && (
        <div className="space-y-2">
          <div className="text-[11px] font-mono uppercase text-muted-foreground">Projects</div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[11px] font-mono">
              <thead>
                <tr className="text-muted-foreground border-b border-border/30">
                  <th className="py-1.5 pr-2 font-normal">Project</th>
                  <th className="py-1.5 pr-2 font-normal">Reviews</th>
                  <th className="py-1.5 pr-2 font-normal">Status</th>
                  <th className="py-1.5 pr-2 font-normal">Raw</th>
                  <th className="py-1.5 pr-2 font-normal">Normalized ± SE</th>
                  <th className="py-1.5 font-normal">Outliers</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {data.projects.map((p) => (
                  <tr key={p.submission_id}>
                    <td className="py-1.5 pr-2 text-foreground">
                      {p.title} <span className="text-muted-foreground">· {p.team_name}</span>
                    </td>
                    <td className="py-1.5 pr-2">
                      {p.reviews_completed}/{p.target_reviews} ({p.assigned_judges} assigned)
                    </td>
                    <td className="py-1.5 pr-2">
                      <Badge
                        variant="outline"
                        className={`text-[9px] ${
                          p.saturation === "SATISFIED"
                            ? "text-emerald-400 border-emerald-500/30"
                            : p.saturation === "IN_PROGRESS"
                            ? "text-sky-400 border-sky-500/30"
                            : "text-amber-400 border-amber-500/30"
                        }`}
                      >
                        {p.saturation}
                      </Badge>
                    </td>
                    <td className="py-1.5 pr-2">{fmt(p.raw_score)}</td>
                    <td className="py-1.5 pr-2">
                      {fmt(p.normalized_score)}
                      {p.standard_error !== null ? ` ± ${fmt(p.standard_error, 2)}` : ""}
                    </td>
                    <td className="py-1.5">{p.outliers_flagged || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
