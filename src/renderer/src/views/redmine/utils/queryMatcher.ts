import { RedmineProject, RedmineStatus, RedmineTracker } from '../types'

export function getMatchedStatus(
  queryName: string,
  statuses: RedmineStatus[]
): RedmineStatus | undefined {
  const qLower = queryName.toLowerCase().replace(/[-_]/g, ' ')
  return statuses.find((s) => {
    const sLower = s.name.toLowerCase().replace(/[-_]/g, ' ')
    return qLower.includes(sLower) || sLower.includes(qLower)
  })
}

export function getMatchedTracker(
  queryName: string,
  trackers: RedmineTracker[]
): RedmineTracker | undefined {
  const qLower = queryName.toLowerCase()
  if (qLower.includes('bug')) {
    const bug = trackers.find((t) => t.name.toLowerCase().includes('bug'))
    if (bug) return bug
  }
  if (qLower.includes('enhancement')) {
    const enh = trackers.find((t) => t.name.toLowerCase().includes('enhancement'))
    if (enh) return enh
  }
  if (qLower.includes('support')) {
    const sup = trackers.find((t) => t.name.toLowerCase().includes('support'))
    if (sup) return sup
  }
  if (qLower.includes('feature')) {
    const feat = trackers.find((t) => t.name.toLowerCase().includes('feature'))
    if (feat) return feat
  }
  return trackers.find((t) => {
    const tLower = t.name.toLowerCase()
    return tLower !== 'task' && qLower.includes(tLower)
  })
}

export function getMatchedProject(
  queryName: string,
  projects: RedmineProject[]
): RedmineProject | undefined {
  const qLower = queryName.toLowerCase()
  return projects.find((p) => {
    const pName = p.name.toLowerCase()
    const pIdent = p.identifier.toLowerCase()
    return (pIdent.length > 2 && qLower.includes(pIdent)) || qLower.includes(pName)
  })
}
