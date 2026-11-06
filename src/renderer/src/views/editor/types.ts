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
}

export interface GitStatusResult {
  isGit: boolean
  branch: string
  root: string
  files: GitChangeItem[]
}
