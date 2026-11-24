<script setup lang="ts">
import { ref } from 'vue'
import { Download, X, Check, Loader2 } from 'lucide-vue-next'

const props = defineProps<{
  image: { url: string; title: string } | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const isDownloading = ref(false)
const isDownloaded = ref(false)

async function handleDownload(): Promise<void> {
  if (!props.image?.url || isDownloading.value) return
  isDownloading.value = true

  const filename = props.image.title || 'downloaded-image.png'
  const url = props.image.url

  try {
    if (url.startsWith('data:')) {
      const base64Data = url.split(',')[1] || ''
      if (window.api?.saveFileDialog) {
        const res = await window.api.saveFileDialog({
          title: `Save ${filename}`,
          defaultPath: filename,
          base64: base64Data
        })
        if (!res.canceled && res.filePath) {
          isDownloaded.value = true
          setTimeout(() => (isDownloaded.value = false), 2500)
        }
        return
      }

      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      isDownloaded.value = true
      setTimeout(() => (isDownloaded.value = false), 2500)
      return
    }

    // Remote HTTP URL
    if (window.api?.saveFileDialog) {
      try {
        const res = await fetch(url)
        const arrayBuf = await res.arrayBuffer()
        const bytes = new Uint8Array(arrayBuf)
        let binary = ''
        const len = bytes.byteLength
        for (let i = 0; i < len; i++) {
          binary += String.fromCharCode(bytes[i])
        }
        const base64Data = btoa(binary)
        const saveRes = await window.api.saveFileDialog({
          title: `Save ${filename}`,
          defaultPath: filename,
          base64: base64Data
        })
        if (!saveRes.canceled && saveRes.filePath) {
          isDownloaded.value = true
          setTimeout(() => (isDownloaded.value = false), 2500)
        }
        return
      } catch (fetchErr) {
        console.warn('[RedmineImageLightbox] Fetch error, falling back:', fetchErr)
      }
    }

    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    isDownloaded.value = true
    setTimeout(() => (isDownloaded.value = false), 2500)
  } catch (err) {
    console.error('[RedmineImageLightbox] Download failed:', err)
  } finally {
    isDownloading.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="props.image"
      class="fixed inset-0 z-[99999] bg-black/85 backdrop-blur-sm flex flex-col items-center justify-center p-4 select-none"
      @click="emit('close')"
    >
      <div class="w-full max-w-5xl flex items-center justify-between text-white pb-3 px-2" @click.stop>
        <span class="text-sm font-semibold truncate select-text">{{ props.image.title }}</span>
        <div class="flex items-center space-x-2">
          <button
            type="button"
            class="px-2.5 py-1 rounded-lg bg-[#202737] hover:bg-[#2b3548] text-xs text-sky-400 hover:text-sky-300 transition-colors flex items-center space-x-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed border border-[#2d384c]"
            title="Save image to computer"
            :disabled="isDownloading"
            @click.stop="handleDownload"
          >
            <Loader2 v-if="isDownloading" class="w-3.5 h-3.5 animate-spin text-sky-400" />
            <Check v-else-if="isDownloaded" class="w-3.5 h-3.5 text-emerald-400" />
            <Download v-else class="w-3.5 h-3.5" />
            <span>{{ isDownloading ? 'Saving...' : isDownloaded ? 'Saved!' : 'Download' }}</span>
          </button>
          <button
            type="button"
            class="p-1.5 rounded-lg bg-black/50 hover:bg-rose-600 text-white transition-colors cursor-pointer"
            @click="emit('close')"
          >
            <X class="w-5 h-5" />
          </button>
        </div>
      </div>

      <div class="max-w-5xl max-h-[85vh] overflow-hidden flex items-center justify-center" @click.stop>
        <img
          :src="props.image.url"
          :alt="props.image.title"
          class="max-w-full max-h-[80vh] object-contain rounded shadow-2xl border border-[#2b3548]"
        />
      </div>
    </div>
  </Teleport>
</template>
