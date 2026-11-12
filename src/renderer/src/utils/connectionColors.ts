export interface ColorOption {
  id: string
  hex: string
  border: string
  name: string
}

export const PRESET_COLORS: ColorOption[] = [
  { id: 'dark', hex: '#64748B', border: '#475569', name: 'Dark / Slate' },
  { id: 'green', hex: '#10B981', border: '#059669', name: 'Green' },
  { id: 'yellow', hex: '#F59E0B', border: '#D97706', name: 'Yellow' },
  { id: 'orange', hex: '#F97316', border: '#EA580C', name: 'Orange' },
  { id: 'red', hex: '#EF4444', border: '#DC2626', name: 'Red' },
  { id: 'blue', hex: '#3B82F6', border: '#2563EB', name: 'Blue' },
  { id: 'purple', hex: '#A855F7', border: '#9333EA', name: 'Purple' }
]

export function getConnectionColor(color?: string): string {
  if (!color) return '#3B82F6'
  const trimmed = color.trim()
  if (trimmed.startsWith('#') || trimmed.startsWith('rgb')) {
    return trimmed
  }
  const match = PRESET_COLORS.find((c) => c.id.toLowerCase() === trimmed.toLowerCase())
  return match ? match.hex : '#3B82F6'
}

