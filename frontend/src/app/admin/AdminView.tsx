"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { CheckCircle, XCircle } from "lucide-react"
import Image from "next/image"
import { Header } from "@/components/Header"
import { IconCheck } from "@/components/ui/icons"
import type { AdminUser } from "./page"

/* ─── Helpers ─────────────────────────────────────────────────────────────── */

function formatRelativeDate(iso: string): string {
  const date = new Date(iso)
  const diffDays = Math.floor((Date.now() - date.getTime()) / 86_400_000)
  if (diffDays === 0) return "Today"
  if (diffDays === 1) return "Yesterday"
  if (diffDays < 7) return `${diffDays}d ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

/* ─── Status badge ────────────────────────────────────────────────────────── */

function StatusBadge({ status }: { status: string }) {
  if (status === "approved") {
    return (
      <span className="inline-flex items-center gap-1 py-0.5 px-1.5 rounded-md text-xs font-medium bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400">
        <IconCheck />
        Approved
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 py-0.5 px-1.5 rounded-md text-xs font-medium bg-surface-overlay text-text-tertiary">
      Pending
    </span>
  )
}

/* ─── User avatar ─────────────────────────────────────────────────────────── */

function UserAvatar({ user }: { user: AdminUser }) {
  if (user.avatar_url) {
    return (
      <Image
        src={user.avatar_url}
        alt=""
        width={28}
        height={28}
        className="rounded-[8px] object-cover shrink-0"
      />
    )
  }
  return (
    <div className="h-7 w-7 rounded-[8px] bg-surface-overlay flex items-center justify-center text-xs font-medium text-text-tertiary shrink-0">
      {(user.name ?? user.email).charAt(0).toUpperCase()}
    </div>
  )
}

/* ─── Users table ─────────────────────────────────────────────────────────── */

interface UsersTableProps {
  users: AdminUser[]
  onApprove: (id: string) => Promise<void>
  onRevoke: (id: string) => Promise<void>
  actionInProgress: string | null
}

function UsersTable({ users, onApprove, onRevoke, actionInProgress }: UsersTableProps) {
  if (users.length === 0) {
    return <p className="text-sm text-text-secondary py-2">No users to show.</p>
  }

  return (
    <div className="rounded-2xl overflow-hidden border border-border-subtle overflow-x-auto">
      <table className="w-full min-w-[560px] table-fixed text-sm">
        <thead>
          <tr className="bg-surface-base border-b border-border-subtle">
            <th className="px-4 h-9 text-left text-xs font-medium text-text-tertiary tracking-wider w-[55%]">
              User
            </th>
            <th className="px-4 h-9 text-left text-xs font-medium text-text-tertiary tracking-wider w-[15%]">
              Joined
            </th>
            <th className="px-4 h-9 text-left text-xs font-medium text-text-tertiary tracking-wider w-[15%]">
              Status
            </th>
            <th className="px-4 h-9 text-left text-xs font-medium text-text-tertiary tracking-wider w-[15%]">
              Action
            </th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr
              key={user.id}
              className="bg-surface-elevated border-t border-border-subtle transition-colors"
            >
              {/* User */}
              <td className="px-4 py-3.5">
                <div className="flex items-center gap-3">
                  <UserAvatar user={user} />
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <p className="text-sm font-medium text-text-primary truncate">
                        {user.name ?? "—"}
                      </p>
                      {user.is_admin && (
                        <span className="text-xs text-text-tertiary font-normal shrink-0">Admin</span>
                      )}
                    </div>
                    <p className="text-xs text-text-tertiary truncate mt-0.5">{user.email}</p>
                  </div>
                </div>
              </td>

              {/* Joined */}
              <td className="px-4 py-3.5">
                <span suppressHydrationWarning className="text-xs text-text-tertiary whitespace-nowrap">
                  {formatRelativeDate(user.created_at)}
                </span>
              </td>

              {/* Status */}
              <td className="px-4 py-3.5">
                <StatusBadge status={user.status} />
              </td>

              {/* Action */}
              <td className="px-4 py-3.5">
                {user.status === "pending" && (
                  <button
                    onClick={() => onApprove(user.id)}
                    disabled={actionInProgress === user.id}
                    className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-[8px] text-xs font-medium border border-border-default bg-surface-elevated text-text-secondary hover:bg-surface-base hover:border-border-strong hover:text-text-primary transition-colors disabled:opacity-50"
                  >
                    <CheckCircle className="h-3.5 w-3.5" />
                    Approve
                  </button>
                )}
                {!user.is_admin && user.status === "approved" && (
                  <button
                    onClick={() => onRevoke(user.id)}
                    disabled={actionInProgress === user.id}
                    className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-[8px] text-xs font-medium border border-border-default bg-surface-elevated text-red-600 border-red-200 dark:border-red-900/40 hover:bg-red-50 dark:hover:bg-red-950/20 hover:text-red-600 transition-colors disabled:opacity-50"
                  >
                    <XCircle className="h-3.5 w-3.5" />
                    Revoke
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ─── View ────────────────────────────────────────────────────────────────── */

export function AdminView({ users: initialUsers }: { users: AdminUser[] }) {
  const router = useRouter()
  const [actionInProgress, setActionInProgress] = useState<string | null>(null)

  async function handleApprove(userId: string) {
    setActionInProgress(userId)
    await fetch(`/api/admin/users/${userId}/approve`, { method: "POST" })
    setActionInProgress(null)
    router.refresh()
  }

  async function handleRevoke(userId: string) {
    setActionInProgress(userId)
    await fetch(`/api/admin/users/${userId}/revoke`, { method: "POST" })
    setActionInProgress(null)
    router.refresh()
  }

  const pending = initialUsers.filter((u) => u.status === "pending")

  return (
    <div className="min-h-screen bg-surface-elevated">
      <Header />
      <div className="h-14" />

      <div className="max-w-5xl mx-auto px-6 lg:px-16 pt-12 pb-24 space-y-10">

        {/* Page header */}
        <div className="flex flex-col gap-1 pb-8 border-b border-zinc-950/5 dark:border-white/5">
          <h2 className="text-lg font-medium text-text-primary tracking-[-0.2px]">Admin</h2>
          <p className="text-sm text-text-secondary">Manage user access</p>
        </div>

        {/* Pending approvals */}
        <div>
          <div className="mb-4">
            <h3 className="text-sm font-medium text-text-primary">Pending Approval</h3>
            <p className="text-sm text-text-secondary mt-0.5">
              {pending.length} user{pending.length !== 1 ? "s" : ""} awaiting access
            </p>
          </div>
          <UsersTable
            users={pending}
            onApprove={handleApprove}
            onRevoke={handleRevoke}
            actionInProgress={actionInProgress}
          />
        </div>

        {/* All users */}
        <div>
          <div className="mb-4">
            <h3 className="text-sm font-medium text-text-primary">All Users</h3>
            <p className="text-sm text-text-secondary mt-0.5">
              {initialUsers.length} user{initialUsers.length !== 1 ? "s" : ""} total
            </p>
          </div>
          <UsersTable
            users={initialUsers}
            onApprove={handleApprove}
            onRevoke={handleRevoke}
            actionInProgress={actionInProgress}
          />
        </div>

      </div>
    </div>
  )
}
