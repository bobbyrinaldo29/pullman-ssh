import { GitGraphCommit } from '../types'

export const LANE_COLORS = [
  '#0ea5e9', // Sky blue (matches screenshot lane 0)
  '#ec4899', // Hot Pink / Magenta (matches screenshot lane 1)
  '#10b981', // Emerald green
  '#f59e0b', // Amber
  '#8b5cf6', // Violet
  '#06b6d4', // Cyan
  '#f43f5e'  // Rose
]

export function getLaneColor(lane: number): string {
  return LANE_COLORS[Math.abs(lane) % LANE_COLORS.length]
}

export function parseGitGraphCommits(rawText: string): GitGraphCommit[] {
  if (!rawText.trim()) return []

  const lines = rawText.trim().split('\n').filter(Boolean)
  const commits: GitGraphCommit[] = []
  const activeLanes: (string | null)[] = []

  for (const line of lines) {
    const parts = line.split('\t')
    if (parts.length < 6) continue

    const hash = parts[0]?.trim()
    if (!hash || hash.length < 6) continue

    const shortHash = parts[1]?.trim() || hash.slice(0, 7)
    const parents = parts[2] ? parts[2].split(' ').filter(Boolean) : []
    const author = parts[3]?.trim() || 'Unknown'
    const email = parts[4]?.trim() || ''
    const date = parts[5]?.trim() || ''
    const subject = parts[6]?.trim() || 'No commit message'
    const refsRaw = parts[7]?.trim() || ''
    const refs = refsRaw
      ? refsRaw.split(',').map((r) => r.trim()).filter(Boolean)
      : []

    // Calculate lane
    let lane = activeLanes.indexOf(hash)
    if (lane === -1) {
      lane = activeLanes.indexOf(null)
      if (lane === -1) {
        lane = activeLanes.length
        activeLanes.push(hash)
      } else {
        activeLanes[lane] = hash
      }
    }

    // Set first parent to continue this lane
    if (parents.length > 0) {
      activeLanes[lane] = parents[0]
      // Additional parents (merges) get other lanes
      for (let p = 1; p < parents.length; p++) {
        const parentHash = parents[p]
        if (!activeLanes.includes(parentHash)) {
          const emptySlot = activeLanes.indexOf(null)
          if (emptySlot === -1) {
            activeLanes.push(parentHash)
          } else {
            activeLanes[emptySlot] = parentHash
          }
        }
      }
    } else {
      activeLanes[lane] = null
    }

    // Clean trailing nulls
    while (activeLanes.length > 0 && activeLanes[activeLanes.length - 1] === null) {
      activeLanes.pop()
    }

    commits.push({
      hash,
      shortHash,
      parents,
      author,
      email,
      date,
      subject,
      refs,
      lane
    })
  }

  return commits
}

export function parseCommitDetails(raw: string): {
  body: string
  files: { status: 'M' | 'A' | 'D'; path: string }[]
} {
  if (!raw.trim()) return { body: '', files: [] }

  if (raw.includes('PULLMAN_META_START')) {
    const s = raw.indexOf('PULLMAN_META_START'), e = raw.indexOf('PULLMAN_META_END')
    if (e > s) {
      const meta = raw.substring(s + 18, e).trim().split('\n')
      const body = meta.slice(5).join('\n').trim() || meta[4]?.trim() || ''
      const files: { status: 'M' | 'A' | 'D'; path: string }[] = []
      for (const line of raw.substring(e + 16).split('\n')) {
        const trimmed = line.trim()
        if (trimmed.match(/^[MADRC]\t/)) {
          const [status, filePath] = trimmed.split('\t')
          if (filePath) files.push({ status: (status[0] as 'M' | 'A' | 'D') || 'M', path: filePath })
        }
      }
      return { body, files }
    }
  }

  const lines = raw.trim().split('\n')
  const files: { status: 'M' | 'A' | 'D'; path: string }[] = []
  const bodyLines: string[] = []

  let parsingFiles = false

  for (const line of lines) {
    if (line.match(/^[MAD]\t/)) {
      parsingFiles = true
      const [status, filePath] = line.split('\t')
      files.push({
        status: status as 'M' | 'A' | 'D',
        path: filePath
      })
    } else if (!parsingFiles) {
      bodyLines.push(line)
    }
  }

  return {
    body: bodyLines.join('\n'),
    files
  }
}

export interface GraphConnection {
  d: string
  color: string
}

export interface GraphNode {
  cx: number
  cy: number
  color: string
  hash: string
}

export function computeGraphLayout(
  commits: GitGraphCommit[],
  rowHeight = 28,
  laneWidth = 18,
  startX = 14
): {
  connections: GraphConnection[]
  nodes: GraphNode[]
  width: number
  height: number
} {
  const connections: GraphConnection[] = []
  const nodes: GraphNode[] = []
  const commitMap = new Map<string, number>()

  commits.forEach((c, idx) => {
    commitMap.set(c.hash, idx)
    const cx = startX + c.lane * laneWidth
    const cy = idx * rowHeight + rowHeight / 2
    nodes.push({
      cx,
      cy,
      color: getLaneColor(c.lane),
      hash: c.hash
    })
  })

  let maxLane = 0

  commits.forEach((c, idx) => {
    if (c.lane > maxLane) maxLane = c.lane
    const cx = startX + c.lane * laneWidth
    const cy = idx * rowHeight + rowHeight / 2

    if (c.parents.length === 0) return

    c.parents.forEach((pHash, pIdx) => {
      const pIndex = commitMap.get(pHash)
      if (pIndex !== undefined && pIndex > idx) {
        const parent = commits[pIndex]
        const px = startX + parent.lane * laneWidth
        const py = pIndex * rowHeight + rowHeight / 2
        const color = pIdx === 0 && c.lane !== 0 ? getLaneColor(c.lane) : getLaneColor(parent.lane)

        if (cx === px) {
          connections.push({
            d: `M ${cx} ${cy} L ${px} ${py}`,
            color
          })
        } else {
          // Smooth curve matching screenshot
          const r = Math.min(16, (py - cy) / 2)
          const d = `M ${cx} ${cy} L ${cx} ${py - r} C ${cx} ${py - r * 0.2}, ${px + (cx > px ? r * 0.2 : -r * 0.2)} ${py}, ${px} ${py}`
          connections.push({ d, color })
        }
      } else {
        connections.push({
          d: `M ${cx} ${cy} L ${cx} ${cy + rowHeight * 1.2}`,
          color: getLaneColor(c.lane)
        })
      }
    })
  })

  const width = Math.max(90, (maxLane + 1) * laneWidth + 24)
  const height = Math.max(commits.length * rowHeight, 100)

  return { connections, nodes, width, height }
}
