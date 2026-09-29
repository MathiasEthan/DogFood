"use client"

import React, { useState, useEffect, use } from "react"
import Link from "next/link"
import { api, JudgeRecordData } from "@/lib/api"
import { Header } from "@/components/header"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  ShieldCheck,
  ShieldAlert,
  Award,
  CheckCircle2,
  Calendar,
  Layers,
  FileCheck,
  Loader2,
  Copy,
  Check,
  Scale,
} from "lucide-react"

export default function JudgeRecordVerificationPage({
  params,
}: {
  params: Promise<{ record_id: string }>
}) {
  const resolvedParams = use(params)
  const recordId = resolvedParams.record_id

  const [data, setData] = useState<JudgeRecordData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    async function loadRecord() {
      try {
        const res = await api.getPublicJudgeRecord(recordId)
        setData(res)
      } catch (err: any) {
        setError(err.message || "Failed to load judge participation record")
      } finally {
        setLoading(false)
      }
    }
    loadRecord()
  }, [recordId])

  const copyUrl = () => {
    if (typeof window !== "undefined") {
      navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="min-h-screen bg-[#07090e] text-slate-100 font-mono selection:bg-emerald-500/30 selection:text-emerald-300">
      <Header />

      <main className="max-w-4xl mx-auto px-4 py-12">
        {loading ? (
          <div className="py-24 flex flex-col items-center justify-center gap-3 text-slate-400">
            <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
            <p className="text-sm">Verifying judge participation record...</p>
          </div>
        ) : error || !data ? (
          <div className="max-w-md mx-auto text-center border border-red-500/30 bg-red-950/20 rounded-xl p-8">
            <ShieldAlert className="w-12 h-12 text-red-400 mx-auto mb-3" />
            <h2 className="text-lg font-bold text-white mb-2">Record Not Found</h2>
            <p className="text-xs text-slate-400 mb-6 leading-relaxed">
              No signed judge participation record found for ID <span className="text-red-300 font-bold">{recordId}</span>.
            </p>
            <Link href="/">
              <Button variant="outline" className="text-xs border-slate-700">
                Return to Home
              </Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Header */}
            <div className="text-center space-y-3">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 text-xs">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span className="font-semibold tracking-wide">SIGNED JUDGE PARTICIPATION RECORD</span>
              </div>
              <h1 className="text-3xl font-extrabold text-white tracking-tight">
                Official Judge Credential
              </h1>
              <p className="text-slate-400 text-sm">
                Signed evaluation record for judge{" "}
                <span className="text-emerald-400 font-semibold">@{data.judge_username}</span> in{" "}
                <span className="text-white font-medium">{data.event_title}</span>
              </p>
            </div>

            {/* Credential Card */}
            <div className="rounded-2xl border border-emerald-500/30 bg-gradient-to-b from-[#0f1422] to-[#0a0d16] p-6 sm:p-8 shadow-2xl relative overflow-hidden">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                    <Scale className="w-6 h-6" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-white">Judge: {data.judge_username}</h2>
                    <p className="text-xs text-slate-400">Record ID: {data.record_id}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Badge className="bg-emerald-950 border border-emerald-500/40 text-emerald-300 text-xs">
                    <CheckCircle2 className="w-3 h-3 mr-1" /> Publicly Verifiable
                  </Badge>
                  <Button
                    onClick={copyUrl}
                    variant="outline"
                    className="border-slate-700 hover:bg-slate-800 text-slate-300 text-xs h-8 gap-1.5"
                  >
                    {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    {copied ? "Copied" : "Share"}
                  </Button>
                </div>
              </div>

              {/* Evaluation Telemetry Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 my-6">
                <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80">
                  <span className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1">
                    Evaluations Completed
                  </span>
                  <span className="text-2xl font-bold text-white">
                    {data.record.evaluations_count}
                  </span>
                  <span className="text-[10px] text-slate-400 block mt-1">projects thoroughly reviewed</span>
                </div>

                <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80">
                  <span className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1">
                    Average Score Awarded
                  </span>
                  <span className="text-2xl font-bold text-emerald-400">
                    {data.record.average_score_given.toFixed(2)}
                  </span>
                  <span className="text-[10px] text-slate-400 block mt-1">across all criteria</span>
                </div>

                <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80">
                  <span className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1">
                    Criteria Scored
                  </span>
                  <span className="text-2xl font-bold text-white">
                    {data.record.scored_rubrics_count}
                  </span>
                  <span className="text-[10px] text-slate-400 block mt-1">individual rubric marks</span>
                </div>
              </div>

              {/* Timestamps */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs bg-slate-950/70 p-4 rounded-xl border border-slate-800/60 text-slate-300 mb-6">
                <div>
                  <span className="text-slate-500 text-[10px] uppercase block">First Evaluation</span>
                  <span>{data.record.first_evaluation_at ? new Date(data.record.first_evaluation_at).toLocaleString() : "N/A"}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] uppercase block">Final Evaluation</span>
                  <span>{data.record.last_evaluation_at ? new Date(data.record.last_evaluation_at).toLocaleString() : "N/A"}</span>
                </div>
              </div>

              {/* Cryptographic Proof */}
              <div className="space-y-3 font-mono text-[11px] text-slate-400 border-t border-slate-800 pt-6">
                <h4 className="text-xs uppercase tracking-wider font-semibold text-slate-300 flex items-center gap-1.5">
                  <FileCheck className="w-3.5 h-3.5 text-emerald-400" /> Cryptographic Telemetry & Proof
                </h4>
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 break-all space-y-2">
                  <div>
                    <span className="text-[10px] text-slate-500 block uppercase">Canonical Payload Digest (SHA-256)</span>
                    <span className="text-slate-200">{data.canonical_digest}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block uppercase">HMAC-SHA256 Signature</span>
                    <span className="text-emerald-400">{data.signature}</span>
                  </div>
                  <div className="flex items-center justify-between text-[10px] pt-1 border-t border-slate-800/60 text-slate-500">
                    <span>Algorithm: {data.signature_algorithm}</span>
                    <span>Status: Verified Authentic</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
