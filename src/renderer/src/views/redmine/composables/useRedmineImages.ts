import { ref, watch, type Ref } from 'vue'
import type { RedmineAttachment, RedmineConfig, RedmineIssue } from '../types'
import { findWikiImageNames, isImageFile } from '../utils/issueDisplay'

/**
 * Resolves and caches Redmine attachment images (with authenticated data URL loading)
 * so both description/journal inline wiki images and attachment grids render reliably.
 */
export function useRedmineImages(
  issue: () => RedmineIssue,
  config: () => RedmineConfig | undefined,
  loadAttachmentDataUrl?: (contentUrl: string) => Promise<string | null>
): {
  imageCache: Ref<Record<string, string>>
  getAttachmentUrl: (att: { content_url: string }) => string
  getImageSrc: (att?: RedmineAttachment | null, fallbackUrl?: string) => string
} {
  const imageCache = ref<Record<string, string>>({})
  const loadingImages = new Set<string>()

  function getAttachmentUrl(att: { content_url: string }): string {
    if (!att?.content_url) return ''
    const separator = att.content_url.includes('?') ? '&' : '?'
    const apiKey = config()?.apiKey
    const key = apiKey ? `key=${encodeURIComponent(apiKey)}` : ''
    return key ? `${att.content_url}${separator}${key}` : att.content_url
  }

  function triggerLoadImage(contentUrl?: string, filename?: string): void {
    if (!contentUrl || loadingImages.has(contentUrl) || !loadAttachmentDataUrl) return
    loadingImages.add(contentUrl)
    loadAttachmentDataUrl(contentUrl)
      .then((dataUrl) => {
        loadingImages.delete(contentUrl)
        if (dataUrl) {
          imageCache.value[contentUrl] = dataUrl
          if (filename) imageCache.value[filename] = dataUrl
        }
      })
      .catch(() => {
        loadingImages.delete(contentUrl)
      })
  }

  async function preloadImages(): Promise<void> {
    const currentIssue = issue()
    const attachments = currentIssue.attachments || []

    for (const att of attachments) {
      if (!isImageFile(att.filename)) continue
      if (imageCache.value[att.filename] || imageCache.value[att.content_url]) continue
      if (loadAttachmentDataUrl && att.content_url) {
        try {
          const dataUrl = await loadAttachmentDataUrl(att.content_url)
          if (dataUrl) {
            imageCache.value[att.content_url] = dataUrl
            imageCache.value[att.filename] = dataUrl
            imageCache.value[String(att.id)] = dataUrl
          }
        } catch (err) {
          console.warn('Failed to load image data URL:', att.filename, err)
        }
      }
    }

    const allNames = [
      ...findWikiImageNames(currentIssue.description),
      ...(currentIssue.journals || []).flatMap((j) => findWikiImageNames(j.notes))
    ]

    for (const name of allNames) {
      if (imageCache.value[name]) continue
      const matched = attachments.find(
        (a) => a.filename.toLowerCase() === name.toLowerCase() || name.toLowerCase().endsWith(a.filename.toLowerCase())
      )
      if (matched?.content_url && !imageCache.value[matched.content_url] && loadAttachmentDataUrl) {
        try {
          const dataUrl = await loadAttachmentDataUrl(matched.content_url)
          if (dataUrl) {
            imageCache.value[matched.content_url] = dataUrl
            imageCache.value[matched.filename] = dataUrl
            imageCache.value[name] = dataUrl
          }
        } catch (err) {
          console.warn('Failed to load wiki image:', name, err)
        }
      }
    }
  }

  watch(
    () => [issue().id, issue().attachments],
    () => {
      preloadImages()
    },
    { immediate: true, deep: true }
  )

  function getImageSrc(att?: RedmineAttachment | null, fallbackUrl?: string): string {
    if (att) {
      if (att.filename && imageCache.value[att.filename]) return imageCache.value[att.filename]
      if (att.content_url && imageCache.value[att.content_url]) return imageCache.value[att.content_url]
      if (att.content_url) {
        triggerLoadImage(att.content_url, att.filename)
        return getAttachmentUrl({ content_url: att.content_url })
      }
    }
    if (fallbackUrl) {
      if (imageCache.value[fallbackUrl]) return imageCache.value[fallbackUrl]
      const matched = (issue().attachments || []).find(
        (a) =>
          a.filename.toLowerCase() === fallbackUrl.toLowerCase() ||
          fallbackUrl.toLowerCase().endsWith(a.filename.toLowerCase())
      )
      if (matched) {
        if (imageCache.value[matched.filename]) return imageCache.value[matched.filename]
        if (imageCache.value[matched.content_url]) return imageCache.value[matched.content_url]
        if (matched.content_url) {
          triggerLoadImage(matched.content_url, matched.filename)
          return getAttachmentUrl(matched)
        }
      }
      return fallbackUrl
    }
    return ''
  }

  return {
    imageCache,
    getAttachmentUrl,
    getImageSrc
  }
}

