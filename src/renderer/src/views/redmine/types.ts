export interface RedmineUser {
  id: number
  login: string
  firstname: string
  lastname: string
  mail?: string
  api_key?: string
  created_on?: string
  last_login_on?: string
}

export interface RedmineProject {
  id: number
  name: string
  identifier: string
  description?: string
  status?: number
  is_public?: boolean
  created_on?: string
  updated_on?: string
}

export interface RedmineTracker {
  id: number
  name: string
}

export interface RedmineStatus {
  id: number
  name: string
  is_closed?: boolean
}

export interface RedminePriority {
  id: number
  name: string
  is_default?: boolean
}

export interface RedmineJournalDetail {
  property: string
  name: string
  old_value?: string
  new_value?: string
}

export interface RedmineJournal {
  id: number
  user: { id: number; name: string }
  notes?: string
  created_on: string
  details?: RedmineJournalDetail[]
}

export interface RedmineCustomField {
  id: number
  name: string
  value: string | string[] | null
}

export interface RedmineAttachment {
  id: number
  filename: string
  filesize: number
  content_type?: string
  description?: string
  content_url: string
  thumbnail_url?: string
  author?: { id: number; name: string }
  created_on?: string
}

export interface RedmineUploadItem {
  token: string
  filename: string
  description?: string
  content_type?: string
}

export interface RedmineIssue {
  id: number
  project: { id: number; name: string }
  tracker: RedmineTracker
  status: RedmineStatus
  priority: RedminePriority
  author: { id: number; name: string }
  assigned_to?: { id: number; name: string }
  subject: string
  description?: string
  start_date?: string
  due_date?: string
  done_ratio: number
  is_private?: boolean
  estimated_hours?: number
  created_on: string
  updated_on: string
  custom_fields?: RedmineCustomField[]
  journals?: RedmineJournal[]
  attachments?: RedmineAttachment[]
}

export interface RedmineQuery {
  id: number
  name: string
  is_public: boolean
  project_id?: number | null
}

export interface RedmineConfig {
  url: string
  apiKey: string
}

export interface RedmineFilterOptions {
  status: 'open' | 'closed' | 'all'
  trackerId: number | 'all'
  priorityId: number | 'all'
  queryId: number | 'all'
  assignedToMe: boolean
  search: string
}

export interface OpenIssueTab {
  id: number
  issue: RedmineIssue
}

export type RedmineNotificationScope = 'assigned_to_me' | 'involved' | 'project' | 'all'

export interface RedmineNotificationEvents {
  newIssue: boolean
  statusChange: boolean
  assigneeChange: boolean
  priorityChange: boolean
  newComment: boolean
  descriptionOrAttachment: boolean
  otherUpdates: boolean
}

export interface RedmineNotificationSettings {
  enabled: boolean
  intervalSeconds: number
  scope: RedmineNotificationScope
  projectId: number | 'all'
  ignoreOwnChanges: boolean
  desktopNotification: boolean
  inAppToast: boolean
  soundEnabled: boolean
  autoRefreshList: boolean
  events: RedmineNotificationEvents
}

export type RedmineChangeType =
  | 'new_issue'
  | 'status'
  | 'assignee'
  | 'priority'
  | 'comment'
  | 'description'
  | 'attachment'
  | 'update'

export interface RedmineChangeNotification {
  id: string
  issueId: number
  issueSubject: string
  projectName: string
  authorName: string
  changeType: RedmineChangeType
  title: string
  summary: string
  detailLines: string[]
  timestamp: string
  read: boolean
  isSimulated?: boolean
}


