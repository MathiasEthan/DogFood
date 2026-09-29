"use client"

import React, { useState, useEffect } from "react"
import { api, Event, EventRubric } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { X, Loader2, Save, AlertCircle, Plus, Trash2, Shield } from "lucide-react"

interface EditEventModalProps {
  event: Event
  isOpen: boolean
  onClose: () => void
  onUpdated: (updatedEvent: Event) => void
}

export function EditEventModal({
  event,
  isOpen,
  onClose,
  onUpdated,
}: EditEventModalProps) {
  const [formData, setFormData] = useState({
    title: event.title || "",
    description: event.description || "",
    mode: event.mode || "virtual",
    location: event.location || "",
    prize_pool: event.prize_pool || "",
    max_team_size: event.max_team_size || 4,
    require_github_url: Boolean(event.require_github_url),
    require_demo_url: Boolean(event.require_demo_url),
    require_presentation: Boolean(event.require_presentation),
    submission_guidelines: event.submission_guidelines || "",
  })

  const [rubrics, setRubrics] = useState<EventRubric[]>(event.rubrics || [])
  const [isFetchingRubrics, setIsFetchingRubrics] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen || !event?.id) return

    setFormData({
      title: event.title || "",
      description: event.description || "",
      mode: event.mode || "virtual",
      location: event.location || "",
      prize_pool: event.prize_pool || "",
      max_team_size: event.max_team_size || 4,
      require_github_url: Boolean(event.require_github_url),
      require_demo_url: Boolean(event.require_demo_url),
      require_presentation: Boolean(event.require_presentation),
      submission_guidelines: event.submission_guidelines || "",
    })

    if (event.rubrics && event.rubrics.length > 0) {
      setRubrics(event.rubrics)
    }

    const loadRubrics = async () => {
      setIsFetchingRubrics(true)
      try {
        const fetchedRubrics = await api.getEventRubrics(event.id)
        if (Array.isArray(fetchedRubrics)) {
          setRubrics(fetchedRubrics)
        }
      } catch (err) {
        console.error("Failed to fetch event rubrics:", err)
      } finally {
        setIsFetchingRubrics(false)
      }
    }

    loadRubrics()
  }, [isOpen, event?.id])

  if (!isOpen) return null

  const totalWeight = rubrics.reduce((acc, r) => acc + (Number(r.weight) || 0), 0)

  const handleAddRubric = () => {
    setRubrics([
      ...rubrics,
      {
        title: "",
        description: "",
        weight: 20,
        max_score: 10,
      },
    ])
  }

  const handleRemoveRubric = (index: number) => {
    setRubrics(rubrics.filter((_, idx) => idx !== index))
  }

  const handleRubricChange = (index: number, field: keyof EventRubric, val: any) => {
    const updated = [...rubrics]
    updated[index] = { ...updated[index], [field]: val }
    setRubrics(updated)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      const updated = await api.updateEvent(event.id, {
        title: formData.title,
        description: formData.description,
        mode: formData.mode,
        location: formData.location,
        prize_pool: formData.prize_pool,
        max_team_size: Number(formData.max_team_size),
        require_github_url: formData.require_github_url,
        require_demo_url: formData.require_demo_url,
        require_presentation: formData.require_presentation,
        submission_guidelines: formData.submission_guidelines,
        rubrics: rubrics.map((r) => ({
          ...(r.id ? { id: r.id } : {}),
          title: r.title,
          description: r.description || "",
          weight: Number(r.weight) || 0,
          max_score: Number(r.max_score) || 10,
        })),
      })
      onUpdated(updated)
      onClose()
    } catch (err: any) {
      setError(err.message || "Failed to update event")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-md overflow-y-auto">
      <div className="relative w-full max-w-2xl rounded-xl border border-border/60 bg-background/95 p-6 shadow-2xl space-y-5 font-mono my-8 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border/30 pb-4">
          <div>
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
              Event Management
            </span>
            <h2 className="text-base font-semibold text-foreground">
              Edit Contest Configuration
            </h2>
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

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* Title */}
          <div className="space-y-1.5">
            <Label className="text-xs text-foreground font-semibold">Contest Title</Label>
            <Input
              type="text"
              required
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="h-8 text-xs font-mono"
            />
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <Label className="text-xs text-foreground font-semibold">Description / About</Label>
            <textarea
              rows={3}
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full rounded-md border border-border/50 bg-background px-3 py-2 text-xs font-mono focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
            />
          </div>

          {/* Mode, Location, Prize Pool, Max Team Size */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label className="text-xs text-foreground font-semibold">Competition Mode</Label>
              <select
                value={formData.mode}
                onChange={(e) => setFormData({ ...formData, mode: e.target.value as any })}
                className="w-full h-8 rounded-md border border-border/50 bg-background px-2.5 text-xs font-mono focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
              >
                <option value="virtual">Virtual</option>
                <option value="in_person">In-Person</option>
                <option value="hybrid">Hybrid</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs text-foreground font-semibold">Location / Platform</Label>
              <Input
                type="text"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                className="h-8 text-xs font-mono"
                placeholder="e.g. Discord or Auditorium B"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs text-foreground font-semibold">Prize Pool</Label>
              <Input
                type="text"
                value={formData.prize_pool}
                onChange={(e) => setFormData({ ...formData, prize_pool: e.target.value })}
                className="h-8 text-xs font-mono"
                placeholder="e.g. $10,000 USD"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs text-foreground font-semibold">Max Team Size</Label>
              <Input
                type="number"
                min={1}
                max={10}
                value={formData.max_team_size}
                onChange={(e) => setFormData({ ...formData, max_team_size: Number(e.target.value) })}
                className="h-8 text-xs font-mono"
              />
            </div>
          </div>

          {/* Deliverables Checklist */}
          <div className="space-y-2 pt-2 border-t border-border/30">
            <Label className="text-xs text-foreground font-semibold">
              Required Submission Deliverables
            </Label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <label className="flex items-center gap-2 p-2.5 rounded-lg border border-border/30 bg-muted/10 cursor-pointer hover:bg-muted/20">
                <Checkbox
                  checked={formData.require_github_url}
                  onCheckedChange={(checked) =>
                    setFormData({ ...formData, require_github_url: Boolean(checked) })
                  }
                />
                <span className="text-[11px] text-foreground">GitHub Code Repo</span>
              </label>

              <label className="flex items-center gap-2 p-2.5 rounded-lg border border-border/30 bg-muted/10 cursor-pointer hover:bg-muted/20">
                <Checkbox
                  checked={formData.require_demo_url}
                  onCheckedChange={(checked) =>
                    setFormData({ ...formData, require_demo_url: Boolean(checked) })
                  }
                />
                <span className="text-[11px] text-foreground">Live Demo / Video</span>
              </label>

              <label className="flex items-center gap-2 p-2.5 rounded-lg border border-border/30 bg-muted/10 cursor-pointer hover:bg-muted/20">
                <Checkbox
                  checked={formData.require_presentation}
                  onCheckedChange={(checked) =>
                    setFormData({ ...formData, require_presentation: Boolean(checked) })
                  }
                />
                <span className="text-[11px] text-foreground">Slide Presentation</span>
              </label>
            </div>
          </div>

          {/* Judging Rubrics Configuration */}
          <div className="space-y-3 pt-3 border-t border-border/30">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <Label className="text-xs text-foreground font-semibold flex items-center gap-1.5">
                  <Shield className="size-3.5 text-amber-400" />
                  Judging Rubrics, Weights & Max Marks
                </Label>
                <p className="text-[11px] text-muted-foreground">
                  Define evaluation criteria and their percentage weights for judges.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <Badge
                  variant="outline"
                  className={`text-[10px] font-mono py-0.5 ${
                    totalWeight === 100
                      ? "border-emerald-500/30 text-emerald-400 bg-emerald-500/10"
                      : "border-amber-500/30 text-amber-400 bg-amber-500/10"
                  }`}
                >
                  Total: {totalWeight}%
                </Badge>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleAddRubric}
                  className="h-7 text-[11px] font-mono hover:text-amber-400"
                >
                  <Plus className="size-3 mr-1" /> Add Rubric
                </Button>
              </div>
            </div>

            {isFetchingRubrics ? (
              <div className="p-4 text-center text-xs text-muted-foreground flex items-center justify-center gap-2 border border-border/20 rounded bg-muted/5 font-mono">
                <Loader2 className="size-3.5 animate-spin text-amber-400" />
                Loading event rubrics...
              </div>
            ) : rubrics.length === 0 ? (
              <p className="text-[11px] text-muted-foreground italic p-2 border border-border/20 rounded bg-muted/5">
                No rubrics configured yet. Click &quot;Add Rubric&quot; to define criteria for judges.
              </p>
            ) : (
              <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
                {rubrics.map((rubric, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg border border-border/30 bg-muted/10 space-y-2 text-xs"
                  >
                    <div className="grid grid-cols-1 sm:grid-cols-12 gap-2 items-center">
                      <div className="sm:col-span-8 space-y-1">
                        <Input
                          placeholder="Criterion Name (e.g. Technical Execution)"
                          value={rubric.title}
                          onChange={(e) => handleRubricChange(idx, "title", e.target.value)}
                          className="h-7 text-xs font-mono"
                          required
                        />
                      </div>
                      <div className="sm:col-span-3 flex items-center gap-1.5">
                        <Input
                          type="number"
                          min={1}
                          max={100}
                          placeholder="Weight %"
                          value={rubric.weight}
                          onChange={(e) => handleRubricChange(idx, "weight", Number(e.target.value))}
                          className="h-7 text-xs font-mono"
                          required
                        />
                        <span className="text-[11px] text-muted-foreground">%</span>
                        <Input
                          type="number"
                          min={1}
                          max={100}
                          placeholder="Max"
                          title="Maximum mark for this criterion"
                          aria-label="Maximum mark"
                          value={rubric.max_score ?? 10}
                          onChange={(e) => handleRubricChange(idx, "max_score", Number(e.target.value))}
                          className="h-7 w-20 text-xs font-mono"
                          required
                        />
                        <span className="text-[11px] text-muted-foreground whitespace-nowrap">max</span>
                      </div>
                      <div className="sm:col-span-1 text-right">
                        <button
                          type="button"
                          onClick={() => handleRemoveRubric(idx)}
                          className="text-muted-foreground hover:text-rose-400 p-1 cursor-pointer"
                          title="Remove rubric"
                        >
                          <Trash2 className="size-3.5" />
                        </button>
                      </div>
                    </div>
                    <Input
                      placeholder="Optional scoring instructions/rubric guideline for judges..."
                      value={rubric.description || ""}
                      onChange={(e) => handleRubricChange(idx, "description", e.target.value)}
                      className="h-7 text-[11px] font-mono text-muted-foreground"
                    />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Guidelines */}
          <div className="space-y-1.5 pt-2 border-t border-border/30">
            <Label className="text-xs text-foreground font-semibold">
              Evaluation Rubric & Submission Guidelines
            </Label>
            <textarea
              rows={3}
              value={formData.submission_guidelines}
              onChange={(e) => setFormData({ ...formData, submission_guidelines: e.target.value })}
              placeholder="Outline specific rules, judging criteria, or guidelines for participants..."
              className="w-full rounded-md border border-border/50 bg-background px-3 py-2 text-xs font-mono focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
            />
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-2 pt-4 border-t border-border/30">
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
              disabled={isLoading}
              className="h-8 text-xs font-mono bg-foreground text-background hover:bg-foreground/90"
            >
              {isLoading ? (
                <>
                  <Loader2 className="size-3 animate-spin mr-1.5" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="size-3 mr-1.5" />
                  Save Changes
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
