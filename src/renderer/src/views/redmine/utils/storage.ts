import type { RedmineProject, RedmineQuery, RedmineUser } from '../types'

const STORAGE_USER_KEY = 'redmine_current_user'
const STORAGE_QUERIES_KEY = 'redmine_cached_queries'
const STORAGE_PROJECTS_KEY = 'redmine_cached_projects'
const STORAGE_PAGE_SIZE_KEY = 'redmine_issues_page_size'

export const ALLOWED_PAGE_SIZES = [25, 50, 100] as const

export function loadStoredCurrentUser(): RedmineUser | null {
  try {
    const raw = localStorage.getItem(STORAGE_USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function persistCurrentUser(user: RedmineUser | null): void {
  try {
    if (user) {
      localStorage.setItem(STORAGE_USER_KEY, JSON.stringify(user))
    } else {
      localStorage.removeItem(STORAGE_USER_KEY)
    }
  } catch {
    // ignore storage errors
  }
}

export function loadStoredQueries(): RedmineQuery[] {
  try {
    const raw = localStorage.getItem(STORAGE_QUERIES_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

export function persistQueries(items: RedmineQuery[]): void {
  try {
    if (items && items.length > 0) {
      localStorage.setItem(STORAGE_QUERIES_KEY, JSON.stringify(items))
    } else {
      localStorage.removeItem(STORAGE_QUERIES_KEY)
    }
  } catch {
    // ignore storage errors
  }
}

export function loadStoredProjects(): RedmineProject[] {
  try {
    const raw = localStorage.getItem(STORAGE_PROJECTS_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

export function persistProjects(items: RedmineProject[]): void {
  try {
    if (items && items.length > 0) {
      localStorage.setItem(STORAGE_PROJECTS_KEY, JSON.stringify(items))
    } else {
      localStorage.removeItem(STORAGE_PROJECTS_KEY)
    }
  } catch {
    // ignore storage errors
  }
}

export function loadStoredPageSize(): number {
  try {
    const raw = Number(localStorage.getItem(STORAGE_PAGE_SIZE_KEY))
    if ((ALLOWED_PAGE_SIZES as readonly number[]).includes(raw)) {
      return raw
    }
  } catch {
    // ignore storage errors
  }
  return 100
}

export function persistPageSize(size: number): void {
  try {
    if ((ALLOWED_PAGE_SIZES as readonly number[]).includes(size)) {
      localStorage.setItem(STORAGE_PAGE_SIZE_KEY, String(size))
    }
  } catch {
    // ignore storage errors
  }
}
