import { HostItem } from '../../types/connection'

export interface EditorFileNode {
  name: string
  path: string
  isDirectory: boolean
  size?: number
  modifyTime?: number
  children?: EditorFileNode[]
  isExpanded?: boolean
  isLoading?: boolean
}

export interface EditorTab {
  id: string
  name: string
  path: string
  content: string
  originalContent: string
  isDirty: boolean
  isSaving: boolean
  language: string
  readOnly?: boolean
  viewType?: 'code' | 'git-graph' | 'diff'
  diffContent?: string
  diffOriginal?: string
  diffModified?: string
}

export interface GitGraphCommit {
  hash: string
  shortHash: string
  parents: string[]
  author: string
  email: string
  date: string
  subject: string
  refs: string[]
  lane: number
}

export interface EditorCursorPos {
  line: number
  col: number
}

export interface EditorGitInfo {
  isGit: boolean
  branch: string
  isDirty: boolean
}

export interface GitBlameInfo {
  author: string
  timeAgo: string
  summary: string
  hash: string
  isUncommitted: boolean
}

export interface GitChangeItem {
  path: string
  relPath: string
  status: 'M' | 'A' | 'D' | 'U'
  staged: boolean
  isDirectory?: boolean
}

export interface GitStatusResult {
  isGit: boolean
  branch: string
  root: string
  files: GitChangeItem[]
}

export interface EditorConnectionTab {
  id: string
  host: HostItem
  title: string
  status: 'connecting' | 'connected' | 'disconnected' | 'error'
}
