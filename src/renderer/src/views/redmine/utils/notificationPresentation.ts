import {
  PlusCircle,
  ArrowRightLeft,
  UserCheck,
  AlertTriangle,
  MessageSquare,
  FileText,
  Paperclip,
  Bell
} from 'lucide-vue-next'
import type { Component } from 'vue'
import type { RedmineChangeType } from '../types'

export interface ChangePresentation {
  icon: Component
  iconColorClass: string
  bgClass: string
  borderClass: string
  label: string
}

const PRESENTATION_MAP: Record<RedmineChangeType, ChangePresentation> = {
  new_issue: {
    icon: PlusCircle,
    iconColorClass: 'text-emerald-400',
    bgClass: 'bg-emerald-500/15',
    borderClass: 'border-emerald-500/40',
    label: 'Tiket Baru'
  },
  status: {
    icon: ArrowRightLeft,
    iconColorClass: 'text-sky-400',
    bgClass: 'bg-sky-500/15',
    borderClass: 'border-sky-500/40',
    label: 'Status Berubah'
  },
  assignee: {
    icon: UserCheck,
    iconColorClass: 'text-purple-400',
    bgClass: 'bg-purple-500/15',
    borderClass: 'border-purple-500/40',
    label: 'Assignee Berubah'
  },
  priority: {
    icon: AlertTriangle,
    iconColorClass: 'text-amber-400',
    bgClass: 'bg-amber-500/15',
    borderClass: 'border-amber-500/40',
    label: 'Prioritas Berubah'
  },
  comment: {
    icon: MessageSquare,
    iconColorClass: 'text-cyan-400',
    bgClass: 'bg-cyan-500/15',
    borderClass: 'border-cyan-500/40',
    label: 'Komentar Baru'
  },
  description: {
    icon: FileText,
    iconColorClass: 'text-indigo-400',
    bgClass: 'bg-indigo-500/15',
    borderClass: 'border-indigo-500/40',
    label: 'Deskripsi Diubah'
  },
  attachment: {
    icon: Paperclip,
    iconColorClass: 'text-teal-400',
    bgClass: 'bg-teal-500/15',
    borderClass: 'border-teal-500/40',
    label: 'Lampiran Baru'
  },
  update: {
    icon: Bell,
    iconColorClass: 'text-slate-300',
    bgClass: 'bg-slate-500/15',
    borderClass: 'border-slate-500/40',
    label: 'Pembaruan'
  }
}

export function getChangePresentation(type: RedmineChangeType): ChangePresentation {
  return PRESENTATION_MAP[type] || PRESENTATION_MAP.update
}

export function formatShortRelativeTime(isoDate?: string | null): string {
  if (!isoDate) return '-'
  const ts = new Date(isoDate).getTime()
  if (isNaN(ts)) return '-'
  const diffSec = Math.max(0, Math.floor((Date.now() - ts) / 1000))
  if (diffSec < 15) return 'Baru saja'
  if (diffSec < 60) return `${diffSec}d lalu`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m lalu`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour}j lalu`
  const diffDay = Math.floor(diffHour / 24)
  return `${diffDay}h lalu`
}

