"use client"

import React, { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import {
  api,
  User,
  Team,
  Certificate,
  WebhookEndpoint,
  WebhookDelivery,
} from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  CheckCircle2,
  AlertCircle,
  Trash2,
  Award,
  Download,
  Upload,
  FileJson,
  FileSpreadsheet,
  Share2,
  ExternalLink,
  Code,
  ShieldCheck,
  Send,
  Loader2,
  Copy,
  Check,
  RefreshCw,
} from "lucide-react"

export function AdminEventDashboard({
  eventId,
  eventObj,
  refreshEvent,
  isPlatformAdmin = false,
}: {
  eventId: number
  eventObj: any
  refreshEvent: () => void
  isPlatformAdmin?: boolean
}) {
  const router = useRouter()
  const [usersList, setUsersList] = useState<User[]>([])
  const [teamsList, setTeamsList] = useState<Team[]>([])
  const [certificates, setCertificates] = useState<Certificate[]>([])
  const [webhooks, setWebhooks] = useState<WebhookEndpoint[]>([])
  const [webhookEvents, setWebhookEvents] = useState<{ value: string; label: string }[]>([])
  
  const [activeTab, setActiveTab] = useState<
    "teams" | "judges" | "settings" | "certificates" | "portability" | "webhooks"
  >(isPlatformAdmin ? "teams" : "certificates")

  const [actionSuccess, setActionSuccess] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [loadingAction, setLoadingAction] = useState(false)

  // Portability state
  const [csvContent, setCsvContent] = useState("")
  const [archiveJson, setArchiveJson] = useState("")
  const [copiedEmbed, setCopiedEmbed] = useState(false)

  // Webhook state
  const [newWebhookUrl, setNewWebhookUrl] = useState("")
  const [newWebhookSecret, setNewWebhookSecret] = useState("")
  const [selectedEvents, setSelectedEvents] = useState<string[]>([])
  const [selectedWebhookDeliveries, setSelectedWebhookDeliveries] = useState<WebhookDelivery[] | null>(null)
  const [viewingWebhookId, setViewingWebhookId] = useState<number | null>(null)

  const fetchAdminData = async () => {
    try {
      const [uList, tms] = await Promise.all([
        api.listUsers(),
        api.listAllTeams(eventId),
      ])
      setUsersList(uList)
      setTeamsList(tms)
    } catch (err: any) {
      setActionError(err.message || "Failed to load admin data")
    }
  }

  const fetchCertificates = async () => {
    try {
      const certs = await api.listEventCertificates(eventId)
      setCertificates(certs)
    } catch (err: any) {
      console.error("Error loading certificates", err)
    }
  }

  const fetchWebhooks = async () => {
    try {
      const [hooks, evTypes] = await Promise.all([
        api.listWebhooks(eventId),
        api.getWebhookEvents().catch(() => ({ event_types: [] })),
      ])
      setWebhooks(hooks)
      if (evTypes.event_types && evTypes.event_types.length > 0) {
        setWebhookEvents(evTypes.event_types)
      } else {
        // Fallback default list
        setWebhookEvents([
          { value: "team.joined", label: "team.joined" },
          { value: "team.left", label: "team.left" },
          { value: "rubrics.updated", label: "rubrics.updated" },
          { value: "judges.assigned", label: "judges.assigned" },
          { value: "vote.voided", label: "vote.voided" },
          { value: "comment.moderated", label: "comment.moderated" },
          { value: "certificates.issued", label: "certificates.issued" },
          { value: "event.exported", label: "event.exported" },
          { value: "event.imported", label: "event.imported" },
        ])
      }
    } catch (err: any) {
      console.error("Error loading webhooks", err)
    }
  }

  useEffect(() => {
    // Teams/judges tabs use platform-admin endpoints; organizers manage those on the event page itself
    if (isPlatformAdmin) fetchAdminData()
  }, [eventId, isPlatformAdmin])

  useEffect(() => {
    if (activeTab === "certificates") fetchCertificates()
    if (activeTab === "webhooks") fetchWebhooks()
  }, [activeTab, eventId])

  const handleDeleteTeam = async (id: number) => {
    if (!confirm("Delete this team?")) return
    try {
      await api.deleteTeam(id)
      setActionSuccess("Team deleted")
      fetchAdminData()
    } catch (err: any) {
      setActionError(err.message)
    }
  }

  const handleGenerateCertificates = async () => {
    setLoadingAction(true)
    setActionError(null)
    setActionSuccess(null)
    try {
      const res = await api.generateCertificates(eventId)
      setActionSuccess(
        `Issued ${res.certificates_count} certificates and signed ${res.records_signed} judge participation records` +
          (res.revoked_count ? `; revoked ${res.revoked_count} superseded certificate(s).` : ".")
      )
      fetchCertificates()
    } catch (err: any) {
      setActionError(err.message || "Failed to generate certificates")
    } finally {
      setLoadingAction(false)
    }
  }

  const handleImportCsv = async () => {
    if (!csvContent.trim()) {
      setActionError("Please provide CSV content.")
      return
    }
    setLoadingAction(true)
    setActionError(null)
    setActionSuccess(null)
    try {
      const res = await api.importTeamsCsv(eventId, csvContent)
      const skipped = res.skipped || []
      setActionSuccess(
        `Imported ${res.teams_created} team(s) and ${res.members_added} participant(s).` +
          (skipped.length
            ? ` Skipped ${skipped.length} row(s): ` +
              skipped.map((r) => `line ${r.line}${r.username ? ` (${r.username})` : ""}: ${r.reason}`).join("; ")
            : "")
      )
      setCsvContent("")
      if (isPlatformAdmin) fetchAdminData()
      refreshEvent()
    } catch (err: any) {
      setActionError(err.message || "CSV import failed")
    } finally {
      setLoadingAction(false)
    }
  }

  const handleImportArchive = async () => {
    if (!archiveJson.trim()) {
      setActionError("Please provide JSON archive data.")
      return
    }
    setLoadingAction(true)
    setActionError(null)
    setActionSuccess(null)
    try {
      const parsed = JSON.parse(archiveJson)
      const res = await api.importBulkArchive(parsed)
      setActionSuccess(`Successfully recreated event! ID: ${res.event_id}`)
      setArchiveJson("")
      router.push(`/events/${res.event_id}`)
    } catch (err: any) {
      setActionError(err.message || "Archive import failed")
    } finally {
      setLoadingAction(false)
    }
  }

  const handleCreateWebhook = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newWebhookUrl.trim()) return
    setLoadingAction(true)
    setActionError(null)
    try {
      const created = await api.createWebhook(eventId, {
        target_url: newWebhookUrl.trim(),
        subscribed_events: selectedEvents.length > 0 ? selectedEvents : ["*"],
        secret: newWebhookSecret.trim() || undefined,
      })
      setActionSuccess(
        `Webhook registered. Signing secret (shown only once — store it to verify X-DogFood-Signature): ${created.secret}`
      )
      setNewWebhookUrl("")
      setNewWebhookSecret("")
      setSelectedEvents([])
      fetchWebhooks()
    } catch (err: any) {
      setActionError(err.message || "Failed to create webhook")
    } finally {
      setLoadingAction(false)
    }
  }

  const handleTestWebhook = async (webhookId: number) => {
    try {
      const res = await api.testWebhook(eventId, webhookId)
      if (res.status === "SUCCESS") {
        setActionSuccess(`Ping delivered — receiver answered HTTP ${res.status_code}.`)
      } else {
        setActionError(
          `Ping failed${res.status_code ? ` (HTTP ${res.status_code})` : ""}: ${res.response_body || "no response"}`
        )
      }
      if (viewingWebhookId === webhookId) handleViewDeliveries(webhookId)
    } catch (err: any) {
      setActionError(err.message || "Webhook test ping failed")
    }
  }

  const handleDeleteWebhook = async (webhookId: number) => {
    if (!confirm("Delete this webhook endpoint?")) return
    try {
      await api.deleteWebhook(eventId, webhookId)
      setActionSuccess("Webhook endpoint deleted.")
      fetchWebhooks()
    } catch (err: any) {
      setActionError(err.message)
    }
  }

  const handleViewDeliveries = async (webhookId: number) => {
    setViewingWebhookId(webhookId)
    try {
      const deliveries = await api.listWebhookDeliveries(eventId, webhookId)
      setSelectedWebhookDeliveries(deliveries)
    } catch (err: any) {
      setActionError(err.message || "Failed to load webhook delivery log")
    }
  }

  const embedSnippet =
    typeof window !== "undefined"
      ? `<iframe src="${window.location.origin}/embed/events/${eventId}/gallery" width="100%" height="700" frameborder="0" style="border:1px solid #222; border-radius:12px; overflow:hidden;" allow="clipboard-write"></iframe>`
      : `<iframe src="/embed/events/${eventId}/gallery" width="100%" height="700" frameborder="0"></iframe>`

  const copyEmbedSnippet = () => {
    if (typeof window !== "undefined") {
      navigator.clipboard.writeText(embedSnippet)
      setCopiedEmbed(true)
      setTimeout(() => setCopiedEmbed(false), 2000)
    }
  }

  return (
    <div className="rounded-xl border border-border/40 bg-background/80 p-5 backdrop-blur-md space-y-4 shadow-2xl mt-8">
      <div className="flex items-center justify-between border-b border-border/30 pb-4">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">
            Organizer Control Center & Platform Extensibility
          </h2>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Manage teams, sign certificates, export archives, and hook into real-time platform webhooks.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border/20 pb-2 overflow-x-auto">
        {(
          [
            "teams",
            "judges",
            "certificates",
            "portability",
            "webhooks",
            "settings",
          ] as const
        )
          .filter((t) => isPlatformAdmin || !["teams", "judges"].includes(t))
          .map((t) => (
          <Button
            key={t}
            variant={activeTab === t ? "default" : "outline"}
            size="sm"
            onClick={() => {
              setActiveTab(t)
              setActionSuccess(null)
              setActionError(null)
            }}
            className="capitalize text-xs h-7 font-mono"
          >
            {t === "portability" ? "Data Portability" : t}
          </Button>
        ))}
      </div>

      {/* Alerts */}
      {actionSuccess && (
        <div className="flex items-center gap-2 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 p-2.5 rounded">
          <CheckCircle2 className="size-4 shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}
      {actionError && (
        <div className="flex items-center gap-2 text-xs text-destructive bg-destructive/10 border border-destructive/20 p-2.5 rounded">
          <AlertCircle className="size-4 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* TEAMS TAB */}
      {activeTab === "teams" && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-border/40 text-[11px] text-muted-foreground uppercase">
                <th className="py-2 px-3 font-normal">Team Name</th>
                <th className="py-2 px-3 font-normal">Code</th>
                <th className="py-2 px-3 font-normal">Submission</th>
                <th className="py-2 px-3 font-normal text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/20">
              {teamsList.map((t) => (
                <tr
                  key={t.id}
                  className="hover:bg-muted/20 cursor-pointer"
                  onClick={() => router.push(`/events/${eventId}/teams/${t.id}`)}
                >
                  <td className="py-2.5 px-3 font-medium text-primary hover:underline">
                    {t.name}
                  </td>
                  <td className="py-2.5 px-3 text-muted-foreground">{t.code}</td>
                  <td className="py-2.5 px-3 text-muted-foreground">
                    {t.submission ? "Yes" : "No"}
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteTeam(t.id)
                      }}
                      className="h-6 text-[11px] font-mono text-destructive hover:bg-destructive/10"
                    >
                      Delete
                    </Button>
                  </td>
                </tr>
              ))}
              {teamsList.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-4 text-center text-muted-foreground">
                    No teams found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* JUDGES TAB */}
      {activeTab === "judges" && (
        <div className="space-y-4">
          <p className="text-xs text-muted-foreground">
            Current Judges:{" "}
            {eventObj.event_judges?.map((j: any) => j.username).join(", ") || "None"}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                const username = prompt("Enter username of judge to ADD to this event:")
                if (username) {
                  const targetUser = usersList.find((u) => u.username === username)
                  if (targetUser) {
                    try {
                      await api.addEventJudge(eventId, targetUser.id)
                      refreshEvent()
                      setActionSuccess("Judge added")
                    } catch (err: any) {
                      setActionError(err.message)
                    }
                  } else {
                    setActionError("User not found in user list.")
                  }
                }
              }}
              className="h-7 text-xs font-mono hover:text-emerald-400"
            >
              Add Judge
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                const username = prompt("Enter username of judge to REMOVE from this event:")
                if (username) {
                  const targetUser = usersList.find((u) => u.username === username)
                  if (targetUser) {
                    try {
                      await api.removeEventJudge(eventId, targetUser.id)
                      refreshEvent()
                      setActionSuccess("Judge removed")
                    } catch (err: any) {
                      setActionError(err.message)
                    }
                  } else {
                    setActionError("User not found in user list.")
                  }
                }
              }}
              className="h-7 text-xs font-mono hover:text-amber-400"
            >
              Remove Judge
            </Button>
          </div>
        </div>
      )}

      {/* CERTIFICATES TAB */}
      {activeTab === "certificates" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-lg bg-muted/20 border border-border/40">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-foreground flex items-center gap-2">
                <Award className="w-4 h-4 text-emerald-400" /> Cryptographic Certificate Issuance
              </h3>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Issue Ed25519-signed SVG certificates that anyone can verify with the public key: winners (by the official normalized leaderboard), all participants, and judges who scored. Requires published results; re-issuing revokes superseded certificates.
              </p>
            </div>
            <Button
              onClick={handleGenerateCertificates}
              disabled={loadingAction}
              className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-bold text-xs h-8 gap-1.5 shrink-0"
            >
              {loadingAction ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Award className="w-3.5 h-3.5" />
              )}
              Generate & Sign Certificates
            </Button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border/40 text-[11px] text-muted-foreground uppercase">
                  <th className="py-2 px-3 font-normal">Recipient</th>
                  <th className="py-2 px-3 font-normal">Role</th>
                  <th className="py-2 px-3 font-normal">Award Distinction</th>
                  <th className="py-2 px-3 font-normal">Certificate Code</th>
                  <th className="py-2 px-3 font-normal text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {certificates.map((cert) => (
                  <tr key={cert.id} className="hover:bg-muted/10">
                    <td className="py-2.5 px-3">
                      <span className="font-medium text-foreground block">
                        {cert.recipient_name}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        {cert.recipient_email}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <Badge
                        variant="outline"
                        className={`text-[10px] uppercase ${
                          cert.role === "winner"
                            ? "border-amber-500/40 text-amber-300 bg-amber-950/20"
                            : cert.role === "judge"
                            ? "border-purple-500/40 text-purple-300 bg-purple-950/20"
                            : "border-emerald-500/40 text-emerald-300 bg-emerald-950/20"
                        }`}
                      >
                        {cert.role}
                      </Badge>
                      {cert.status && cert.status !== "valid" && (
                        <Badge variant="outline" className="ml-1 text-[10px] uppercase border-red-500/40 text-red-300">
                          {cert.status}
                        </Badge>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-muted-foreground font-medium">
                      {cert.award_title}
                    </td>
                    <td className="py-2.5 px-3">
                      <Link
                        href={`/certificates/${cert.certificate_code}`}
                        target="_blank"
                        className="text-emerald-400 hover:underline font-mono text-[11px] flex items-center gap-1"
                      >
                        {cert.certificate_code} <ExternalLink className="w-2.5 h-2.5" />
                      </Link>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <a
                        href={api.getCertificateDownloadUrl(cert.certificate_code)}
                        download
                        className="inline-flex items-center gap-1 text-[11px] text-slate-300 hover:text-white bg-slate-800 px-2 py-1 rounded border border-slate-700 hover:border-slate-600 transition-colors"
                      >
                        <Download className="w-3 h-3 text-emerald-400" /> SVG
                      </a>
                    </td>
                  </tr>
                ))}
                {certificates.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-muted-foreground">
                      No certificates generated yet. Click &quot;Generate &amp; Sign Certificates&quot; to issue official credentials.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* PORTABILITY TAB */}
      {activeTab === "portability" && (
        <div className="space-y-6 text-xs">
          {/* Export section */}
          <div className="p-4 rounded-lg bg-muted/20 border border-border/40 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-foreground flex items-center gap-2">
                <FileJson className="w-4 h-4 text-emerald-400" /> Export Full Event Archive (Zero Lock-In)
              </h3>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Download a complete, lossless cryptographic JSON archive containing event metadata, rubrics, teams, submissions, evaluations, votes, and SHA-256 checksum.
              </p>
            </div>
            <a
              href={api.getExportBulkArchiveUrl(eventId)}
              download
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-bold text-xs shrink-0"
            >
              <Download className="w-3.5 h-3.5" /> Export JSON Archive
            </a>
          </div>

          {/* Import Archive section */}
          <div className="p-4 rounded-lg bg-muted/20 border border-border/40 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-foreground flex items-center gap-2">
              <Upload className="w-4 h-4 text-blue-400" /> Import / Clone Event from Archive
            </h3>
            <p className="text-[11px] text-muted-foreground">
              Paste or load an exported JSON archive to spin up an exact replica of an event.
            </p>
            <textarea
              value={archiveJson}
              onChange={(e) => setArchiveJson(e.target.value)}
              placeholder="Paste JSON archive payload here..."
              rows={3}
              className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-emerald-500"
            />
            <div className="flex justify-end">
              <Button
                onClick={handleImportArchive}
                disabled={loadingAction || !archiveJson.trim()}
                size="sm"
                className="bg-blue-600 hover:bg-blue-700 text-white text-xs h-7 gap-1"
              >
                {loadingAction ? <Loader2 className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
                Recreate Event from JSON
              </Button>
            </div>
          </div>

          {/* Bulk Import Teams CSV */}
          <div className="p-4 rounded-lg bg-muted/20 border border-border/40 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-foreground flex items-center gap-2">
              <FileSpreadsheet className="w-4 h-4 text-amber-400" /> Bulk Import Teams & Participants (CSV)
            </h3>
            <p className="text-[11px] text-muted-foreground">
              Format: <span className="font-mono text-slate-300">team_name,username,email,is_leader</span>
            </p>
            <textarea
              value={csvContent}
              onChange={(e) => setCsvContent(e.target.value)}
              placeholder="team_name,username,email,is_leader&#10;Alpha Team,alice,alice@example.com,true&#10;Alpha Team,bob,bob@example.com,false&#10;Beta Force,charlie,charlie@example.com,true"
              rows={4}
              className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-emerald-500"
            />
            <div className="flex justify-end">
              <Button
                onClick={handleImportCsv}
                disabled={loadingAction || !csvContent.trim()}
                size="sm"
                className="bg-amber-600 hover:bg-amber-700 text-white text-xs h-7 gap-1"
              >
                {loadingAction ? <Loader2 className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
                Bulk Import Teams
              </Button>
            </div>
          </div>

          {/* Embeddable Gallery Widget code */}
          <div className="p-4 rounded-lg bg-muted/20 border border-border/40 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-foreground flex items-center gap-2">
                <Code className="w-4 h-4 text-purple-400" /> Embeddable Gallery Widget
              </h3>
              <Link
                href={`/embed/events/${eventId}/gallery`}
                target="_blank"
                className="text-[11px] text-purple-400 hover:underline flex items-center gap-1"
              >
                Preview Widget <ExternalLink className="w-2.5 h-2.5" />
              </Link>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Copy this iframe snippet to embed the project showcase onto your blog, company website, or community portal.
            </p>
            <div className="relative">
              <pre className="bg-slate-950 p-3 rounded border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto whitespace-pre-wrap">
                {embedSnippet}
              </pre>
              <Button
                onClick={copyEmbedSnippet}
                variant="outline"
                size="sm"
                className="absolute top-2 right-2 h-7 text-xs border-slate-700 bg-slate-900 text-slate-200 gap-1"
              >
                {copiedEmbed ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                {copiedEmbed ? "Copied" : "Copy Code"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* WEBHOOKS TAB */}
      {activeTab === "webhooks" && (
        <div className="space-y-6 text-xs">
          {/* Register Webhook Form */}
          <form
            onSubmit={handleCreateWebhook}
            className="p-4 rounded-lg bg-muted/20 border border-border/40 space-y-4"
          >
            <h3 className="text-xs font-bold uppercase tracking-wider text-foreground flex items-center gap-2">
              <Send className="w-4 h-4 text-emerald-400" /> Register Webhook Target
            </h3>
            <p className="text-[11px] text-muted-foreground">
              Receive automated HTTP POST dispatches whenever actions happen in this event (e.g. member joins, rubrics update, judges assigned, certificates issued).
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-muted-foreground mb-1">
                  Target Endpoint URL *
                </label>
                <Input
                  type="url"
                  placeholder="https://example.com/api/webhooks/dogfood"
                  value={newWebhookUrl}
                  onChange={(e) => setNewWebhookUrl(e.target.value)}
                  required
                  className="h-8 text-xs font-mono bg-slate-900 border-slate-700"
                />
              </div>

              <div>
                <label className="block text-[11px] text-muted-foreground mb-1">
                  Signing secret (optional, min 16 chars — auto-generated if empty)
                </label>
                <Input
                  type="text"
                  placeholder="Custom secret for payload verification"
                  value={newWebhookSecret}
                  onChange={(e) => setNewWebhookSecret(e.target.value)}
                  className="h-8 text-xs font-mono bg-slate-900 border-slate-700"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] text-muted-foreground mb-2">
                Subscribed Events (Leave unselected to subscribe to ALL):
              </label>
              <div className="flex flex-wrap gap-2">
                {webhookEvents.map((ev) => {
                  const isChecked = selectedEvents.includes(ev.value)
                  return (
                    <button
                      type="button"
                      key={ev.value}
                      onClick={() => {
                        if (isChecked) {
                          setSelectedEvents(selectedEvents.filter((e) => e !== ev.value))
                        } else {
                          setSelectedEvents([...selectedEvents, ev.value])
                        }
                      }}
                      className={`text-[10px] px-2 py-1 rounded border transition-colors ${
                        isChecked
                          ? "bg-emerald-950 border-emerald-500 text-emerald-300 font-bold"
                          : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {ev.label}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="flex justify-end">
              <Button
                type="submit"
                disabled={loadingAction || !newWebhookUrl.trim()}
                className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-bold text-xs h-8 gap-1.5"
              >
                {loadingAction ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                Register Endpoint
              </Button>
            </div>
          </form>

          {/* Configured Endpoints Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border/40 text-[11px] text-muted-foreground uppercase">
                  <th className="py-2 px-3 font-normal">Target URL</th>
                  <th className="py-2 px-3 font-normal">Subscribed Events</th>
                  <th className="py-2 px-3 font-normal">Status</th>
                  <th className="py-2 px-3 font-normal text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {webhooks.map((hook) => (
                  <tr key={hook.id} className="hover:bg-muted/10">
                    <td className="py-2.5 px-3 font-mono text-slate-200 max-w-[200px] truncate">
                      {hook.target_url}
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="flex flex-wrap gap-1">
                        {hook.subscribed_events.slice(0, 3).map((e, idx) => (
                          <span
                            key={idx}
                            className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded border border-slate-700"
                          >
                            {e}
                          </span>
                        ))}
                        {hook.subscribed_events.length > 3 && (
                          <span className="text-[10px] text-muted-foreground">
                            +{hook.subscribed_events.length - 3}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 px-3">
                      <Badge
                        variant="outline"
                        className={`text-[10px] ${
                          hook.is_active
                            ? "border-emerald-500/40 text-emerald-300 bg-emerald-950/20"
                            : "border-slate-700 text-slate-400"
                        }`}
                      >
                        {hook.is_active ? "Active" : "Disabled"}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleTestWebhook(hook.id)}
                          className="h-6 text-[10px] font-mono border-slate-700 hover:text-emerald-400"
                        >
                          Ping
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleViewDeliveries(hook.id)}
                          className="h-6 text-[10px] font-mono border-slate-700 hover:text-blue-400"
                        >
                          Logs
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDeleteWebhook(hook.id)}
                          className="h-6 text-[10px] font-mono text-destructive border-slate-700 hover:bg-destructive/10"
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
                {webhooks.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-6 text-center text-muted-foreground">
                      No webhook endpoints registered yet. Add one above to listen for real-time dispatches.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Webhook Deliveries Modal */}
          {selectedWebhookDeliveries && (
            <div
              className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
              onClick={() => setSelectedWebhookDeliveries(null)}
            >
              <div
                className="bg-[#0e131f] border border-border/40 rounded-xl max-w-2xl w-full p-6 text-slate-200 max-h-[80vh] overflow-y-auto shadow-2xl relative"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
                  <h3 className="font-bold text-sm text-white flex items-center gap-2">
                    <Send className="w-4 h-4 text-emerald-400" /> Webhook Delivery History (Endpoint #{viewingWebhookId})
                  </h3>
                  <button
                    onClick={() => setSelectedWebhookDeliveries(null)}
                    className="text-slate-400 hover:text-white font-bold"
                  >
                    ✕
                  </button>
                </div>

                <div className="space-y-2">
                  {selectedWebhookDeliveries.map((d) => (
                    <div
                      key={d.id}
                      className="p-3 rounded bg-slate-950 border border-slate-800 text-xs font-mono space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-emerald-400 font-semibold">{d.event_type}</span>
                        <Badge
                          variant="outline"
                          className={`text-[10px] ${
                            d.status === "SUCCESS"
                              ? "border-emerald-500/40 text-emerald-300"
                              : "border-destructive/40 text-destructive"
                          }`}
                        >
                          {d.response_status ? `HTTP ${d.response_status}` : d.status}
                        </Badge>
                      </div>
                      <p className="text-[10px] text-slate-500">
                        {new Date(d.created_at).toLocaleString()} • {d.attempt_count} attempt(s)
                      </p>
                    </div>
                  ))}
                  {selectedWebhookDeliveries.length === 0 && (
                    <p className="text-center text-xs text-slate-500 py-6">
                      No webhook deliveries recorded yet for this endpoint.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* SETTINGS TAB */}
      {activeTab === "settings" && (
        <div className="space-y-4 text-xs mt-4">
          <div className="space-y-2">
            <h3 className="font-semibold text-sm">Submission Requirements</h3>
            <div className="flex flex-col gap-2">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={eventObj.require_github_url || false}
                  onChange={async (e) => {
                    try {
                      await api.updateEventAdmin(eventId, {
                        require_github_url: e.target.checked,
                      })
                      refreshEvent()
                      setActionSuccess("Updated setting")
                    } catch (err: any) {
                      setActionError(err.message)
                    }
                  }}
                />
                Require GitHub URL
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={eventObj.require_demo_url || false}
                  onChange={async (e) => {
                    try {
                      await api.updateEventAdmin(eventId, {
                        require_demo_url: e.target.checked,
                      })
                      refreshEvent()
                      setActionSuccess("Updated setting")
                    } catch (err: any) {
                      setActionError(err.message)
                    }
                  }}
                />
                Require Demo URL
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={eventObj.require_presentation || false}
                  onChange={async (e) => {
                    try {
                      await api.updateEventAdmin(eventId, {
                        require_presentation: e.target.checked,
                      })
                      refreshEvent()
                      setActionSuccess("Updated setting")
                    } catch (err: any) {
                      setActionError(err.message)
                    }
                  }}
                />
                Require Presentation
              </label>
            </div>
            <div className="mt-4">
              <Button
                size="sm"
                variant="outline"
                onClick={async () => {
                  const val = prompt(
                    "Enter Submission Guidelines:",
                    eventObj.submission_guidelines || ""
                  )
                  if (val !== null && val !== eventObj.submission_guidelines) {
                    try {
                      await api.updateEventAdmin(eventId, {
                        submission_guidelines: val,
                      })
                      refreshEvent()
                      setActionSuccess("Updated guidelines")
                    } catch (err: any) {
                      setActionError(err.message)
                    }
                  }
                }}
              >
                Edit Guidelines
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
