"use client"

import React, { createContext, useContext, useEffect, useState, useCallback } from "react"
import { useRouter, usePathname } from "next/navigation"
import { api, User } from "@/lib/api"

interface AuthContextType {
  user: User | null
  isLoading: boolean
  login: (credentials: { username: string; password: string }) => Promise<void>
  register: (payload: {
    username: string
    email: string
    password: string
    confirm_password: string
    role: "participant" | "organizer"
  }) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

// ?next=/events/3?join=HACK-AB12 support (invite links). Only same-site paths are accepted,
// so the parameter can't be abused as an open redirect.
function safeNextPath(): string | null {
  if (typeof window === "undefined") return null
  const next = new URLSearchParams(window.location.search).get("next")
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return null
  return next
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()
  const pathname = usePathname()

  const refreshUser = useCallback(async () => {
    try {
      const userData = await api.getMe()
      setUser(userData)
    } catch (error) {
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshUser()
  }, [refreshUser])

  const login = async (credentials: { username: string; password: string }) => {
    const res = await api.login(credentials)
    setUser(res.user)
    const next = safeNextPath()
    if (next) {
      router.push(next)
    } else if (res.user.role === "organizer" || res.user.role === "judge" || res.user.role === "admin") {
      router.push("/dashboard")
    } else {
      router.push("/")
    }
  }

  const register = async (payload: {
    username: string
    email: string
    password: string
    confirm_password: string
    role: "participant" | "organizer"
  }) => {
    const res = await api.register(payload)
    setUser(res.user)
    const next = safeNextPath()
    if (next) {
      router.push(next)
    } else if (res.user.role === "organizer" || res.user.role === "admin") {
      router.push("/dashboard")
    } else {
      router.push("/")
    }
  }

  const logout = async () => {
    try {
      await api.logout()
    } catch (e) {
      // Proceed even if network/auth error on logout
    }
    setUser(null)
    router.push("/login")
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
