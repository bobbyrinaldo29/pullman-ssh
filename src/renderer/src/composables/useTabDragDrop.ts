import { ref, type Ref } from 'vue'

export function useTabDragDrop<T>(
  tabsRef: Ref<T[]>,
  onReorder?: (newTabs: T[]) => void
) {
  const draggedIndex = ref<number | null>(null)
  const dragOverIndex = ref<number | null>(null)

  function handleDragStart(event: DragEvent, index: number): void {
    draggedIndex.value = index
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = 'move'
      event.dataTransfer.setData('text/plain', String(index))
    }
  }

  function handleDragOver(event: DragEvent, index: number): void {
    event.preventDefault()
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = 'move'
    }
    dragOverIndex.value = index
  }

  function handleDragLeave(_event: DragEvent, index: number): void {
    if (dragOverIndex.value === index) {
      dragOverIndex.value = null
    }
  }

  function handleDrop(event: DragEvent, toIndex: number): void {
    event.preventDefault()
    const fromIndex = draggedIndex.value
    if (fromIndex !== null && fromIndex !== toIndex) {
      const list = [...tabsRef.value]
      const [moved] = list.splice(fromIndex, 1)
      list.splice(toIndex, 0, moved)
      tabsRef.value = list
      onReorder?.(list)
    }
    draggedIndex.value = null
    dragOverIndex.value = null
  }

  function handleDragEnd(): void {
    draggedIndex.value = null
    dragOverIndex.value = null
  }

  return {
    draggedIndex,
    dragOverIndex,
    handleDragStart,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleDragEnd
  }
}
