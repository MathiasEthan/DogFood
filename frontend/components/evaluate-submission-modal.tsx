"use client"

import React, { useState, useEffect } from "react"
import { api, EventRubric, ProjectSubmission, ProjectEvaluation } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Shield,
  Award,
  Sparkles,
  Calculator,
} from "lucide-react"

interface EvaluateSubmissionModalProps {
  eventId: number
  submission: ProjectSubmission
  isOpen: boolean
  onClose: () => void
  onEvaluated?: (evaluation: ProjectEvaluation) => void
}

export function EvaluateSubmissionModal({
  eventId,
  submission,
  isOpen,
  onClose,
  onEvaluated,
}: EvaluateSubmissionModalProps) {
  const [rubrics, setRubrics] = useState<EventRubric[]>([])
  const [scores, setScores] = useState<Record<number, number>>({})
  const [feedback, setFeedback] = useState("")
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return

    const fetchRubricsAndEvaluation = async () => {
      setLoading(true)
      setError(null)
      try {
        const [rubricsData, myEvalRes] = await Promise.all([
          api.getEventRubrics(eventId),
          api.getMyEvaluation(eventId, submission.id).catch(() => ({ evaluated: false, evaluation: null })),
        ])

        setRubrics(rubricsData)

        // Initialize scores
        const initialScores: Record<number, number> = {}
        if (myEvalRes.evaluated && myEvalRes.evaluation) {
          myEvalRes.evaluation.scores.forEach((s) => {
            initialScores[s.rubric] = s.score
          })
          setFeedback(myEvalRes.evaluation.feedback || "")
        } else {
          rubricsData.forEach((r) => {
            if (r.id) initialScores[r.id] = Math.ceil((r.max_score || 10) * 0.7) // neutral starting score
          })
        }
        setScores(initialScores)
      } catch (err: any) {
        setError(err.message || "Failed to load judging rubrics.")
      } finally {
        setLoading(false)
      }
    }

    fetchRubricsAndEvaluation()
  }, [isOpen, eventId, submission.id])

  if (!isOpen) return null

  // Calculate weighted total score
  const totalConfiguredWeight = rubrics.reduce((acc, r) => acc + (r.weight || 0), 0)

  const calculateWeightedTotal = () => {
    if (rubrics.length === 0) return 0
    let weightedSum = 0
    rubrics.forEach((r) => {
      if (r.id && scores[r.id] !== undefined) {
        const weightFactor = totalConfiguredWeight > 0 ? r.weight / totalConfiguredWeight : 1 / rubrics.length
        // Each mark is rescaled to /10 by the rubric's own max before weighting (same as the backend)
        weightedSum += (scores[r.id] / (r.max_score || 10)) * 10 * weightFactor
      }
    })
    return Number(weightedSum.toFixed(2))
  }

  const calculatedTotal = calculateWeightedTotal()

  const handleScoreChange = (rubricId: number, val: number, max: number = 10) => {
    setScores((prev) => ({
      ...prev,
      [rubricId]: Math.max(1, Math.min(max, val)),
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    setSuccess(null)

    try {
      const scoresPayload = rubrics.map((r) => ({
        rubric_id: r.id!,
        score: scores[r.id!] ?? 7,
      }))

      const res = await api.submitEvaluation(eventId, submission.id, {
        scores: scoresPayload,
        feedback,
      })

      setSuccess(`Evaluation logged! Total score: ${res.evaluation.total_score} / 10`)
      if (onEvaluated) {
        onEvaluated(res.evaluation)
      }
      setTimeout(() => {
        onClose()
      }, 1000)
    } catch (err: any) {
      setError(err.message || "Failed to submit evaluation.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-md overflow-y-auto">
      <div className="relative w-full max-w-2xl rounded-xl border border-border/60 bg-background/95 p-6 shadow-2xl space-y-5 font-mono my-8 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-border/30 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Shield className="size-4 text-amber-400" />
              <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
                Judge Evaluation Panel
              </span>
            </div>
            <h2 className="text-base font-semibold text-foreground pt-0.5">
              Score: {submission.title}
            </h2>
            <p className="text-xs text-muted-foreground">
              Team: <strong className="text-foreground">{submission.team_name}</strong>
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-colors"
          >
            <X className="size-4" />
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-3 text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-md">
            <AlertCircle className="size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="flex items-center gap-2 p-3 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-md">
            <CheckCircle2 className="size-4 shrink-0" />
            <span>{success}</span>
          </div>
        )}

        {loading ? (
          <div className="p-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
            <Loader2 className="size-4 animate-spin text-foreground" />
            Loading rubrics...
          </div>
        ) : rubrics.length === 0 ? (
          <div className="p-8 text-center rounded-lg border border-border/30 bg-muted/10 space-y-2">
            <AlertCircle className="size-6 text-amber-400 mx-auto" />
            <div className="text-xs font-semibold text-foreground">No Rubrics Defined Yet</div>
            <p className="text-[11px] text-muted-foreground">
              The organizer has not configured evaluation rubrics for this event yet.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Rubrics List */}
            <div className="space-y-4">
              {rubrics.map((r, index) => {
                const maxMark = r.max_score || 10
                const currentScore = scores[r.id!] ?? Math.ceil(maxMark * 0.7)
                const weightRatio = totalConfiguredWeight > 0 ? r.weight / totalConfiguredWeight : 1 / rubrics.length
                const contribution = ((currentScore / maxMark) * 10 * weightRatio).toFixed(2)

                return (
                  <div
                    key={r.id || index}
                    className="p-4 rounded-lg border border-border/40 bg-muted/10 space-y-3"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                      <div>
                        <div className="text-xs font-semibold text-foreground flex items-center gap-2">
                          <span>{r.title}</span>
                          <Badge
                            variant="outline"
                            className="text-[10px] font-mono border-amber-500/30 text-amber-400 bg-amber-500/10 py-0"
                          >
                            Weight: {r.weight}%
                          </Badge>
                        </div>
                        {r.description && (
                          <p className="text-[11px] text-muted-foreground font-sans pt-0.5">
                            {r.description}
                          </p>
                        )}
                      </div>

                      {/* Contribution preview */}
                      <div className="text-right text-[11px] font-mono text-muted-foreground">
                        Contribution:{" "}
                        <strong className="text-foreground">
                          +{contribution}
                        </strong>{" "}
                        / 10
                      </div>
                    </div>

                    {/* 1-10 Score Selector */}
                    <div className="space-y-1.5 pt-1">
                      <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-muted-foreground">
                        <span>Mark (1 = Poor, {maxMark} = Exceptional):</span>
                        <span className="text-xs font-bold text-foreground">
                          {currentScore} / {maxMark}
                        </span>
                      </div>

                      <div className="flex items-center gap-1 sm:gap-1.5">
                        {Array.from({ length: maxMark }, (_, i) => i + 1).map((num) => (
                          <button
                            key={num}
                            type="button"
                            onClick={() => handleScoreChange(r.id!, num, maxMark)}
                            className={`flex-1 h-8 rounded text-xs font-mono font-semibold transition-all cursor-pointer ${
                              currentScore === num
                                ? "bg-amber-400 text-black shadow-md scale-105"
                                : "bg-muted/30 border border-border/40 text-muted-foreground hover:text-foreground hover:bg-muted/50"
                            }`}
                          >
                            {num}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Live Calculation Summary Banner */}
            <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Calculator className="size-4 text-amber-400 shrink-0" />
                <div>
                  <div className="text-xs font-semibold text-amber-300">
                    Calculated Weighted Mark
                  </div>
                  <div className="text-[10px] text-amber-400/80">
                    Formula: Σ (Mark / Max × 10 × Weight share)
                  </div>
                </div>
              </div>

              <div className="text-right">
                <div className="text-xl font-extrabold text-amber-300">
                  {calculatedTotal.toFixed(2)}{" "}
                  <span className="text-xs font-normal text-amber-400/80">/ 10</span>
                </div>
                <div className="text-[10px] text-amber-400/80">
                  Equivalent to {(calculatedTotal * 10).toFixed(1)}%
                </div>
              </div>
            </div>

            {/* Qualitative Feedback */}
            <div className="space-y-1.5">
              <Label className="text-xs text-foreground font-semibold">
                Judge Remarks & Qualitative Feedback (Optional)
              </Label>
              <textarea
                rows={3}
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="Notes on execution, strengths, areas for improvement, or pitch feedback..."
                className="w-full rounded-md border border-border/50 bg-background px-3 py-2 text-xs font-mono focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber-500"
              />
            </div>

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-border/30">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onClose}
                className="h-8 text-xs font-mono"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={submitting}
                className="h-8 text-xs font-mono bg-amber-500 text-black hover:bg-amber-400 font-semibold"
              >
                {submitting ? (
                  <>
                    <Loader2 className="size-3 animate-spin mr-1.5" />
                    Recording Score...
                  </>
                ) : (
                  <>
                    <Award className="size-3.5 mr-1.5" />
                    Submit Evaluation ({calculatedTotal.toFixed(2)}/10)
                  </>
                )}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
