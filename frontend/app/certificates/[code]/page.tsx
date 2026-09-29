"use client"

import React, { useState, useEffect, use } from "react"
import Link from "next/link"
import { api, Certificate } from "@/lib/api"
import { Header } from "@/components/header"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  ShieldCheck,
  ShieldAlert,
  Download,
  Share2,
  CheckCircle2,
  Calendar,
  Award,
  ExternalLink,
  Loader2,
  Copy,
  Check,
} from "lucide-react"

export default function CertificateVerificationPage({
  params,
}: {
  params: Promise<{ code: string }>
}) {
  const resolvedParams = use(params)
  const code = resolvedParams.code

  const [cert, setCert] = useState<Certificate | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    async function loadCert() {
      try {
        const data = await api.getPublicCertificate(code)
        setCert(data)
      } catch (err: any) {
        setError(err.message || "Failed to load certificate")
      } finally {
        setLoading(false)
      }
    }
    loadCert()
  }, [code])

  const copyUrl = () => {
    if (typeof window !== "undefined") {
      navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const downloadUrl = api.getCertificateDownloadUrl(code)

  return (
    <div className="min-h-screen bg-[#07090e] text-slate-100 font-mono selection:bg-emerald-500/30 selection:text-emerald-300">
      <Header />

      <main className="max-w-4xl mx-auto px-4 py-12">
        {loading ? (
          <div className="py-24 flex flex-col items-center justify-center gap-3 text-slate-400">
            <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
            <p className="text-sm">Cryptographically verifying credential...</p>
          </div>
        ) : error || !cert ? (
          <div className="max-w-md mx-auto text-center border border-red-500/30 bg-red-950/20 rounded-xl p-8">
            <ShieldAlert className="w-12 h-12 text-red-400 mx-auto mb-3" />
            <h2 className="text-lg font-bold text-white mb-2">Certificate Not Found</h2>
            <p className="text-xs text-slate-400 mb-6 leading-relaxed">
              No issued credential matched the verification code <span className="text-red-300 font-bold">{code}</span>.
              The certificate may have been revoked or entered incorrectly.
            </p>
            <Link href="/">
              <Button variant="outline" className="text-xs border-slate-700">
                Return to Home
              </Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Status Header */}
            <div className="text-center space-y-3">
              {cert.status === "revoked" ? (
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-950/60 border border-amber-500/40 text-amber-300 text-xs">
                  <ShieldAlert className="w-4 h-4 text-amber-400" />
                  <span className="font-semibold tracking-wide">
                    REVOKED{cert.revoked_at ? ` ON ${new Date(cert.revoked_at).toLocaleDateString()}` : ""}
                    {cert.revocation_reason ? ` — ${cert.revocation_reason.toUpperCase()}` : ""}
                  </span>
                </div>
              ) : cert.status === "invalid" || (!cert.status && !cert.is_valid) ? (
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-red-950/60 border border-red-500/40 text-red-300 text-xs">
                  <ShieldAlert className="w-4 h-4 text-red-400" />
                  <span className="font-semibold tracking-wide">SIGNATURE INVALID — DO NOT TRUST THIS CERTIFICATE</span>
                </div>
              ) : (
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 text-xs">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  <span className="font-semibold tracking-wide">SIGNATURE VERIFIED · VALID CREDENTIAL</span>
                </div>
              )}
              <h1 className="text-3xl font-extrabold text-white tracking-tight">
                {cert.title}
              </h1>
              <p className="text-slate-400 text-sm">
                Issued for outstanding participation in{" "}
                <span className="text-emerald-400 font-semibold">{cert.event_title}</span>
              </p>
            </div>

            {/* Certificate Visual Card */}
            <div className="relative rounded-2xl border border-emerald-500/30 bg-gradient-to-b from-[#0f1422] to-[#0a0d16] p-6 sm:p-10 shadow-2xl overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none" />

              <div className="border border-emerald-500/20 rounded-xl p-6 sm:p-8 bg-[#090c14]/80 backdrop-blur-sm relative">
                {/* SVG Visual Representation Preview */}
                <div className="flex flex-col items-center text-center space-y-4">
                  <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/40 flex items-center justify-center text-emerald-400 mb-2">
                    <Award className="w-8 h-8" />
                  </div>

                  <span className="text-xs uppercase tracking-widest text-emerald-400/90 font-bold">
                    Official Award of Recognition
                  </span>

                  <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-wide font-sans">
                    {cert.recipient_name}
                  </h2>

                  <div className="h-0.5 w-24 bg-emerald-500/40 my-2" />

                  <p className="text-xs text-slate-300 max-w-lg leading-relaxed">
                    has officially been recognized with the distinction of{" "}
                    <span className="text-emerald-300 font-semibold">{cert.award_title}</span> in{" "}
                    <span className="text-white font-medium">{cert.event_title}</span>.
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full pt-6 mt-4 border-t border-slate-800/80 text-left text-xs">
                    <div>
                      <span className="text-slate-500 block text-[10px] uppercase">Recipient Role</span>
                      <span className="text-slate-200 capitalize font-medium">{cert.role}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px] uppercase">Issued Date</span>
                      <span className="text-slate-200">
                        {new Date(cert.issued_at).toLocaleDateString(undefined, {
                          year: "numeric",
                          month: "long",
                          day: "numeric",
                        })}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px] uppercase">Certificate Code</span>
                      <span className="text-emerald-400 font-mono font-semibold">{cert.certificate_code}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px] uppercase">Integrity Status</span>
                      <span
                        className={`flex items-center gap-1 ${
                          cert.status === "valid" ? "text-emerald-400" : cert.status === "revoked" ? "text-amber-400" : "text-red-400"
                        }`}
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />{" "}
                        {cert.status === "valid" ? "Valid & Untampered" : cert.status === "revoked" ? "Revoked" : "Signature invalid"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="mt-6 flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-slate-800">
                <div className="flex items-center gap-2">
                  <a href={downloadUrl} download>
                    <Button className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold text-xs h-9 gap-1.5 shadow-lg shadow-emerald-500/20">
                      <Download className="w-3.5 h-3.5" /> Download SVG Certificate
                    </Button>
                  </a>
                  <Button
                    onClick={copyUrl}
                    variant="outline"
                    className="border-slate-700 hover:bg-slate-800 text-slate-300 text-xs h-9 gap-1.5"
                  >
                    {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    {copied ? "Link Copied" : "Copy Verification URL"}
                  </Button>
                </div>

                <div className="text-[11px] text-slate-500">
                  Signed with Ed25519 (public key)
                </div>
              </div>
            </div>

            {/* Cryptographic Proof Card */}
            <div className="rounded-xl border border-slate-800 bg-[#0b0e17] p-5 text-xs">
              <h3 className="text-slate-400 font-semibold uppercase tracking-wider text-[11px] mb-3 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" /> Cryptographic Authenticity Proof
              </h3>
              <div className="space-y-2 font-mono text-[11px] break-all">
                <div className="bg-slate-950 p-2.5 rounded border border-slate-800/80">
                  <span className="text-slate-500 block text-[10px]">DIGITAL SIGNATURE ({cert.signature_algorithm || "Ed25519"})</span>
                  <span className="text-emerald-400">{cert.signature}</span>
                </div>
                <div className="bg-slate-950 p-2.5 rounded border border-slate-800/80">
                  <span className="text-slate-500 block text-[10px]">PLATFORM PUBLIC KEY</span>
                  <span className="text-slate-300">{cert.public_key_hex}</span>
                </div>
                {cert.signed_payload && (
                  <div className="bg-slate-950 p-2.5 rounded border border-slate-800/80">
                    <span className="text-slate-500 block text-[10px]">SIGNED CLAIMS (CANONICAL JSON)</span>
                    <pre className="text-slate-300 whitespace-pre-wrap">{JSON.stringify(cert.signed_payload, null, 2)}</pre>
                  </div>
                )}
                <div className="text-[10px] text-slate-500 leading-relaxed">
                  Verify independently: serialize the signed claims with sorted keys and no whitespace, then check the
                  Ed25519 signature against the public key published at{" "}
                  <a className="text-emerald-400 hover:underline" href={api.getSigningKeyUrl()} target="_blank" rel="noreferrer">
                    /api/signing-key/
                  </a>
                  . No trust in this website is required.
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
