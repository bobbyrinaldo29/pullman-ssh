import {
  PlusCircle,
  ArrowRightLeft,
  UserCheck,
  AlertTriangle,
  MessageSquare,
  FileText,
  SlidersHorizontal
} from 'lucide-vue-next'
import type { RedmineNotificationSettings } from '../../../views/redmine/types'

export const INTERVAL_PRESETS = [
  { label: 'Realtime (0s)', value: 0, isRealtime: true },
  { label: '5 seconds', value: 5, isRealtime: false },
  { label: '15 seconds', value: 15, isRealtime: false },
  { label: '30 seconds', value: 30, isRealtime: false },
  { label: '1 minute', value: 60, isRealtime: false },
  { label: '5 minutes', value: 300, isRealtime: false }
]

export const SCOPE_OPTIONS: Array<{
  value: RedmineNotificationSettings['scope']
  label: string
  description: string
}> = [
  {
    value: 'involved',
    label: 'My Tickets (Assignee & Author)',
    description: 'Track tickets created by or assigned to you'
  },
  {
    value: 'assigned_to_me',
    label: 'Assigned to Me Only',
    description: 'Only tickets where assignee is your Redmine account'
  },
  {
    value: 'project',
    label: 'Specific Project',
    description: 'Track all changes within a selected project'
  },
  {
    value: 'all',
    label: 'All Redmine Tickets',
    description: 'Track all accessible ticket updates across Redmine'
  }
]

export const EVENT_TOGGLE_ITEMS = [
  {
    key: 'newIssue' as const,
    label: 'New Ticket',
    desc: 'When a new issue or bug is created',
    icon: PlusCircle,
    color: 'text-emerald-400'
  },
  {
    key: 'statusChange' as const,
    label: 'Status Change',
    desc: 'E.g. In Progress → Ready to test',
    icon: ArrowRightLeft,
    color: 'text-sky-400'
  },
  {
    key: 'assigneeChange' as const,
    label: 'Assignee Change',
    desc: 'When a ticket is reassigned',
    icon: UserCheck,
    color: 'text-purple-400'
  },
  {
    key: 'priorityChange' as const,
    label: 'Priority Change',
    desc: 'E.g. Normal → High / Urgent',
    icon: AlertTriangle,
    color: 'text-amber-400'
  },
  {
    key: 'newComment' as const,
    label: 'New Comment / Notes',
    desc: 'Team comments or journal notes',
    icon: MessageSquare,
    color: 'text-cyan-400'
  },
  {
    key: 'descriptionOrAttachment' as const,
    label: 'Description & Attachments',
    desc: 'Description edits or new file uploads',
    icon: FileText,
    color: 'text-indigo-400'
  },
  {
    key: 'otherUpdates' as const,
    label: 'Other Updates',
    desc: 'Progress % done, due dates, custom fields',
    icon: SlidersHorizontal,
    color: 'text-slate-300'
  }
]
