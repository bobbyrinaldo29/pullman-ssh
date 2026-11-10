import {
  RedmineChangeNotification,
  RedmineChangeType,
  RedmineIssue,
  RedmineJournal,
  RedmineNotificationEvents,
  RedminePriority,
  RedmineStatus
} from '../types'

export interface IssueSnapshot {
  id: number
  updated_on: string
  created_on: string
  statusId?: number
  statusName: string
  priorityId?: number
  priorityName: string
  assignedToId?: number
  assignedToName: string
  subject: string
  done_ratio: number
  lastJournalId?: number
}

export function createIssueSnapshot(issue: RedmineIssue): IssueSnapshot {
  const journals = issue.journals || []
  const lastJournalId = journals.length > 0 ? journals[journals.length - 1].id : undefined
  return {
    id: issue.id,
    updated_on: issue.updated_on,
    created_on: issue.created_on,
    statusId: issue.status?.id,
    statusName: issue.status?.name || '',
    priorityId: issue.priority?.id,
    priorityName: issue.priority?.name || '',
    assignedToId: issue.assigned_to?.id,
    assignedToName: issue.assigned_to?.name || '',
    subject: issue.subject || '',
    done_ratio: issue.done_ratio ?? 0,
    lastJournalId
  }
}

export function getLatestRelevantJournal(
  issue: RedmineIssue,
  prev?: IssueSnapshot
): RedmineJournal | null {
  const journals = issue.journals || []
  if (journals.length === 0) return null

  const sorted = [...journals].sort((a, b) => a.id - b.id)
  if (prev?.lastJournalId !== undefined) {
    const newer = sorted.filter((j) => j.id > prev.lastJournalId!)
    if (newer.length > 0) return newer[newer.length - 1]
  }

  const latest = sorted[sorted.length - 1]
  const issueUpdatedMs = new Date(issue.updated_on).getTime()
  const journalCreatedMs = new Date(latest.created_on).getTime()
  // Redmine timestamps match closely when update created a journal
  if (!isNaN(issueUpdatedMs) && !isNaN(journalCreatedMs)) {
    if (Math.abs(issueUpdatedMs - journalCreatedMs) <= 180_000) {
      return latest
    }
  }
  return prev ? null : latest
}

function truncateText(text: string, maxLen = 110): string {
  const normalized = text.replace(/\s+/g, ' ').trim()
  if (normalized.length <= maxLen) return normalized
  return `${normalized.slice(0, maxLen - 1)}…`
}

export function analyzeIssueChange(params: {
  issue: RedmineIssue
  prev?: IssueSnapshot
  isBrandNew: boolean
  statuses: RedmineStatus[]
  priorities: RedminePriority[]
  knownUsers: Map<number, string>
  enabledEvents: RedmineNotificationEvents
  currentUserId?: number
  ignoreOwnChanges: boolean
}): RedmineChangeNotification | null {
  const {
    issue,
    prev,
    isBrandNew,
    statuses,
    priorities,
    knownUsers,
    enabledEvents,
    currentUserId,
    ignoreOwnChanges
  } = params

  const statusMap = new Map(statuses.map((s) => [s.id, s.name]))
  const priorityMap = new Map(priorities.map((p) => [p.id, p.name]))

  const latestJournal = isBrandNew ? null : getLatestRelevantJournal(issue, prev)
  const actorId = isBrandNew
    ? issue.author?.id
    : latestJournal?.user?.id || undefined
  const actorName = isBrandNew
    ? issue.author?.name || 'Seseorang'
    : latestJournal?.user?.name || issue.author?.name || 'Tim Redmine'

  if (ignoreOwnChanges && currentUserId && actorId === currentUserId) {
    return null
  }

  const detectedFlags = {
    newIssue: isBrandNew,
    statusChange: false,
    assigneeChange: false,
    priorityChange: false,
    newComment: false,
    descriptionOrAttachment: false,
    otherUpdates: false
  }

  const detailLines: string[] = []
  let primaryType: RedmineChangeType = isBrandNew ? 'new_issue' : 'update'

  if (isBrandNew) {
    const trackerName = issue.tracker?.name || 'Issue'
    const assignee = issue.assigned_to?.name ? ` • Assignee: ${issue.assigned_to.name}` : ''
    detailLines.push(`${trackerName} baru dibuat oleh ${actorName}${assignee}`)
  } else {
    const details = latestJournal?.details || []

    // Inspect structured journal details first
    for (const d of details) {
      if (d.name === 'status_id') {
        detectedFlags.statusChange = true
        const oldName = d.old_value ? statusMap.get(Number(d.old_value)) || d.old_value : '-'
        const newName = d.new_value ? statusMap.get(Number(d.new_value)) || d.new_value : '-'
        detailLines.push(`Status: ${oldName} → ${newName}`)
      } else if (d.name === 'assigned_to_id') {
        detectedFlags.assigneeChange = true
        const oldName = d.old_value
          ? knownUsers.get(Number(d.old_value)) || `User #${d.old_value}`
          : 'Unassigned'
        const newName = d.new_value
          ? knownUsers.get(Number(d.new_value)) || `User #${d.new_value}`
          : 'Unassigned'
        detailLines.push(`Assignee: ${oldName} → ${newName}`)
      } else if (d.name === 'priority_id') {
        detectedFlags.priorityChange = true
        const oldName = d.old_value ? priorityMap.get(Number(d.old_value)) || d.old_value : '-'
        const newName = d.new_value ? priorityMap.get(Number(d.new_value)) || d.new_value : '-'
        detailLines.push(`Prioritas: ${oldName} → ${newName}`)
      } else if (d.name === 'description') {
        detectedFlags.descriptionOrAttachment = true
        detailLines.push('Deskripsi diperbarui')
      } else if (d.property === 'attachment') {
        detectedFlags.descriptionOrAttachment = true
        const fileName = d.new_value || d.name || 'lampiran'
        detailLines.push(`File ditambahkan: ${fileName}`)
      } else if (d.name === 'done_ratio') {
        detectedFlags.otherUpdates = true
        detailLines.push(`Progress: ${d.old_value || 0}% → ${d.new_value || 0}%`)
      } else if (d.name === 'subject') {
        detectedFlags.otherUpdates = true
        detailLines.push('Subject diperbarui')
      } else if (d.name === 'due_date' || d.name === 'start_date') {
        detectedFlags.otherUpdates = true
        const fieldLabel = d.name === 'due_date' ? 'Due date' : 'Start date'
        detailLines.push(`${fieldLabel}: ${d.new_value || '-'}`)
      } else {
        detectedFlags.otherUpdates = true
        const customField = issue.custom_fields?.find((cf) => String(cf.id) === String(d.name))
        if (customField) {
          detailLines.push(`${customField.name}: ${d.new_value || '-'}`)
        }
      }
    }

    // Fallback diff against snapshot if journal details weren't present
    if (prev) {
      if (!detectedFlags.statusChange && issue.status?.id !== prev.statusId) {
        detectedFlags.statusChange = true
        detailLines.push(`Status: ${prev.statusName || '-'} → ${issue.status?.name || '-'}`)
      }
      if (!detectedFlags.assigneeChange && issue.assigned_to?.id !== prev.assignedToId) {
        detectedFlags.assigneeChange = true
        detailLines.push(
          `Assignee: ${prev.assignedToName || 'Unassigned'} → ${issue.assigned_to?.name || 'Unassigned'}`
        )
      }
      if (!detectedFlags.priorityChange && issue.priority?.id !== prev.priorityId) {
        detectedFlags.priorityChange = true
        detailLines.push(
          `Prioritas: ${prev.priorityName || '-'} → ${issue.priority?.name || '-'}`
        )
      }
      if (issue.done_ratio !== prev.done_ratio && !detailLines.some((l) => l.startsWith('Progress:'))) {
        detectedFlags.otherUpdates = true
        detailLines.push(`Progress: ${prev.done_ratio}% → ${issue.done_ratio}%`)
      }
      if (issue.subject !== prev.subject && !detailLines.includes('Subject diperbarui')) {
        detectedFlags.otherUpdates = true
        detailLines.push('Subject diperbarui')
      }
    }

    if (latestJournal?.notes && latestJournal.notes.trim()) {
      detectedFlags.newComment = true
      detailLines.push(`Komentar: "${truncateText(latestJournal.notes, 90)}"`)
    }

    if (detailLines.length === 0) {
      detectedFlags.otherUpdates = true
      detailLines.push('Tiket diperbarui')
    }

    // Determine primary icon / color category
    if (detectedFlags.statusChange) primaryType = 'status'
    else if (detectedFlags.assigneeChange) primaryType = 'assignee'
    else if (detectedFlags.newComment) primaryType = 'comment'
    else if (detectedFlags.priorityChange) primaryType = 'priority'
    else if (details.some((d) => d.property === 'attachment')) primaryType = 'attachment'
    else if (detectedFlags.descriptionOrAttachment) primaryType = 'description'
  }

  // Check user's configured event filters
  const matchesFilter =
    (detectedFlags.newIssue && enabledEvents.newIssue) ||
    (detectedFlags.statusChange && enabledEvents.statusChange) ||
    (detectedFlags.assigneeChange && enabledEvents.assigneeChange) ||
    (detectedFlags.priorityChange && enabledEvents.priorityChange) ||
    (detectedFlags.newComment && enabledEvents.newComment) ||
    (detectedFlags.descriptionOrAttachment && enabledEvents.descriptionOrAttachment) ||
    (detectedFlags.otherUpdates && enabledEvents.otherUpdates)

  if (!matchesFilter) {
    return null
  }

  const projectName = issue.project?.name || 'Redmine'
  let title = `Update #${issue.id} • ${projectName}`
  if (primaryType === 'new_issue') title = `Tiket Baru #${issue.id} • ${projectName}`
  else if (primaryType === 'status') title = `Status #${issue.id} • ${issue.status?.name || ''}`
  else if (primaryType === 'comment') title = `Komentar Baru #${issue.id} • ${projectName}`
  else if (primaryType === 'assignee') title = `Penugasan #${issue.id} • ${projectName}`

  const summary =
    primaryType === 'new_issue'
      ? `${actorName} membuat ${issue.tracker?.name || 'Issue'}: "${truncateText(issue.subject, 80)}"`
      : `${actorName}: ${detailLines.slice(0, 2).join(' | ')}`

  return {
    id: `${issue.id}-${issue.updated_on}-${latestJournal?.id || '0'}-${Date.now()}`,
    issueId: issue.id,
    issueSubject: issue.subject,
    projectName,
    authorName: actorName,
    changeType: primaryType,
    title,
    summary,
    detailLines,
    timestamp: new Date().toISOString(),
    read: false
  }
}

