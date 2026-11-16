import { RedminePriority, RedmineStatus, RedmineTracker } from '../types'

export const DEFAULT_TRACKERS: RedmineTracker[] = [
  { id: 1, name: 'Bug' },
  { id: 2, name: 'Feature' },
  { id: 3, name: 'Support' },
  { id: 4, name: 'Task' }
]

export const DEFAULT_STATUSES: RedmineStatus[] = [
  { id: 1, name: 'New' },
  { id: 2, name: 'In Progress' },
  { id: 3, name: 'Resolved' },
  { id: 4, name: 'Feedback' },
  { id: 5, name: 'Closed', is_closed: true }
]

export const DEFAULT_PRIORITIES: RedminePriority[] = [
  { id: 1, name: 'Low' },
  { id: 2, name: 'Normal', is_default: true },
  { id: 3, name: 'High' },
  { id: 4, name: 'Urgent' },
  { id: 5, name: 'Immediate' }
]
