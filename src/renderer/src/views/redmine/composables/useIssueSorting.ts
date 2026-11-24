import { ref, computed } from 'vue'
import type { RedmineIssue } from '../types'

export type SortDirection = 'asc' | 'desc' | null

export function useIssueSorting(getIssues: () => RedmineIssue[]) {
  const sortKey = ref<string | null>(null)
  const sortDirection = ref<SortDirection>(null)

  try {
    const saved = localStorage.getItem('redmine_issues_sort')
    if (saved) {
      const parsed = JSON.parse(saved) as { key: string; direction: 'asc' | 'desc' }
      if (parsed.key && (parsed.direction === 'asc' || parsed.direction === 'desc')) {
        sortKey.value = parsed.key
        sortDirection.value = parsed.direction
      }
    }
  } catch {
    // ignore local storage errors
  }

  function saveSortState(): void {
    try {
      if (sortKey.value && sortDirection.value) {
        localStorage.setItem(
          'redmine_issues_sort',
          JSON.stringify({ key: sortKey.value, direction: sortDirection.value })
        )
      } else {
        localStorage.removeItem('redmine_issues_sort')
      }
    } catch {
      // ignore local storage errors
    }
  }

  function toggleSort(key: string): void {
    if (sortKey.value !== key) {
      sortKey.value = key
      sortDirection.value = 'asc'
    } else {
      if (sortDirection.value === 'asc') {
        sortDirection.value = 'desc'
      } else if (sortDirection.value === 'desc') {
        sortKey.value = null
        sortDirection.value = null
      } else {
        sortDirection.value = 'asc'
      }
    }
    saveSortState()
  }

  const sortedIssues = computed(() => {
    const raw = getIssues()
    if (!sortKey.value || !sortDirection.value) {
      return raw
    }

    const key = sortKey.value
    const dir = sortDirection.value === 'asc' ? 1 : -1

    return [...raw].sort((a, b) => {
      let valA: string | number
      let valB: string | number

      switch (key) {
        case 'id':
          return (a.id - b.id) * dir
        case 'project':
          valA = a.project?.name || ''
          valB = b.project?.name || ''
          return valA.localeCompare(valB, undefined, { sensitivity: 'base', numeric: true }) * dir
        case 'tracker':
          valA = a.tracker?.name || ''
          valB = b.tracker?.name || ''
          return valA.localeCompare(valB, undefined, { sensitivity: 'base' }) * dir
        case 'status':
          valA = a.status?.name || ''
          valB = b.status?.name || ''
          return valA.localeCompare(valB, undefined, { sensitivity: 'base' }) * dir
        case 'priority': {
          const prioDiff = (a.priority?.id || 0) - (b.priority?.id || 0)
          if (prioDiff !== 0) return prioDiff * dir
          valA = a.priority?.name || ''
          valB = b.priority?.name || ''
          return valA.localeCompare(valB, undefined, { sensitivity: 'base' }) * dir
        }
        case 'subject':
          valA = a.subject || ''
          valB = b.subject || ''
          return valA.localeCompare(valB, undefined, { sensitivity: 'base', numeric: true }) * dir
        case 'assignee':
          valA = a.assigned_to?.name || ''
          valB = b.assigned_to?.name || ''
          return valA.localeCompare(valB, undefined, { sensitivity: 'base' }) * dir
        case 'updated':
          valA = new Date(a.updated_on || 0).getTime()
          valB = new Date(b.updated_on || 0).getTime()
          return (valA - valB) * dir
        case 'done_ratio':
          return ((a.done_ratio || 0) - (b.done_ratio || 0)) * dir
        default:
          return 0
      }
    })
  })

  return {
    sortKey,
    sortDirection,
    toggleSort,
    sortedIssues
  }
}
