import { ref } from 'vue'

export interface ColumnDef {
  key: string
  label: string
  width: number
  minWidth: number
  align?: 'left' | 'center' | 'right'
}

export function useIssueColumns() {
  const columns = ref<ColumnDef[]>([
    { key: 'id', label: '#', width: 75, minWidth: 50, align: 'center' },
    { key: 'project', label: 'Project', width: 230, minWidth: 120, align: 'left' },
    { key: 'tracker', label: 'Tracker', width: 135, minWidth: 80, align: 'left' },
    { key: 'status', label: 'Status', width: 135, minWidth: 80, align: 'left' },
    { key: 'priority', label: 'Priority', width: 100, minWidth: 70, align: 'left' },
    { key: 'subject', label: 'Subject', width: 440, minWidth: 200, align: 'left' },
    { key: 'assignee', label: 'Assignee', width: 170, minWidth: 90, align: 'left' },
    { key: 'updated', label: 'Updated', width: 110, minWidth: 80, align: 'left' },
    { key: 'done_ratio', label: '% Done', width: 115, minWidth: 80, align: 'right' }
  ])

  function loadColumnWidths(): void {
    try {
      const savedStr = localStorage.getItem('redmine_issues_column_widths')
      if (!savedStr) return
      const saved = JSON.parse(savedStr) as Array<{ key: string; width: number }>
      for (const s of saved) {
        const col = columns.value.find((c) => c.key === s.key)
        if (col && s.width >= col.minWidth) {
          col.width = s.width
        }
      }
    } catch {
      // ignore invalid persisted column widths
    }
  }

  function saveColumnWidths(): void {
    try {
      const saved = columns.value.map((c) => ({ key: c.key, width: c.width }))
      localStorage.setItem('redmine_issues_column_widths', JSON.stringify(saved))
    } catch {
      // ignore storage errors
    }
  }

  loadColumnWidths()

  const resizingColIndex = ref<number | null>(null)
  let startX = 0
  let startWidth = 0

  function startResize(index: number, e: MouseEvent): void {
    e.preventDefault()
    resizingColIndex.value = index
    startX = e.clientX
    startWidth = columns.value[index].width
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const onMouseMove = (moveEvent: MouseEvent): void => {
      if (resizingColIndex.value === null) return
      const deltaX = moveEvent.clientX - startX
      const col = columns.value[resizingColIndex.value]
      col.width = Math.max(col.minWidth, startWidth + deltaX)
    }

    const onMouseUp = (): void => {
      resizingColIndex.value = null
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      saveColumnWidths()
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  return {
    columns,
    startResize
  }
}
