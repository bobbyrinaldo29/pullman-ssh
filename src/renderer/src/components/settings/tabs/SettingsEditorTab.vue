<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import {
  Code2, FolderOpen, Play, CheckCircle2, AlertCircle, RefreshCw, ShieldCheck, Key
} from 'lucide-vue-next'
import ToggleSwitch from '../../ToggleSwitch.vue'
import GitCredentialModal from '../../GitCredentialModal.vue'
import { useEditorSettings, ExternalEditorId } from '../../../composables/useEditorSettings'
import { useGlobalGitCredentials } from '../../../composables/useGlobalGitCredentials'

const {
  fontFamily, fontSize, tabSize, fontLigatures, minimap, lineNumbers, wordWrap,
  formatOnSave, externalEditorType, customEditorPath, customEditorArgs,
  openExternalByDefault, autoSyncExternal, fontFamilies
} = useEditorSettings()

const isCustomFont = computed(() => !fontFamilies.some((f) => f.value === fontFamily.value))
const customFontInput = ref(isCustomFont.value ? fontFamily.value : '')

watch(fontFamily, (newVal) => {
  if (isCustomFont.value) customFontInput.value = newVal
})

function handleFontSelect(e: Event): void {
  const target = e.target as HTMLSelectElement
  if (target.value === 'custom') {
    if (!customFontInput.value) customFontInput.value = 'Hack, monospace'
    fontFamily.value = customFontInput.value
  } else {
    fontFamily.value = target.value
  }
}

function handleCustomFontInput(e: Event): void {
  const val = (e.target as HTMLInputElement).value
  customFontInput.value = val
  if (val.trim()) fontFamily.value = val.trim()
}

const {
  globalCredentials, hasCredentials, isGitCredentialModalOpen, openModal, closeModal
} = useGlobalGitCredentials()

interface DetectedEditor {
  id: string
  name: string
  command: string
  detected: boolean
  executablePath?: string
}

interface EditorPresetOption {
  id: ExternalEditorId
  title: string
  desc: string
  cmdTag?: string
  isBuiltin?: boolean
  isCustom?: boolean
}

const EDITOR_PRESETS: EditorPresetOption[] = [
  { id: 'internal', title: 'Monaco Editor', desc: 'Default integrated editor inside Pullman.', isBuiltin: true },
  { id: 'vscode', title: 'Visual Studio Code', desc: 'Syncs remote files locally and launches `code`.', cmdTag: 'code' },
  { id: 'cursor', title: 'Cursor AI', desc: 'AI-first editor with real-time remote sync.', cmdTag: 'cursor' },
  { id: 'sublime', title: 'Sublime Text', desc: 'Ultra-fast native code and text editor.', cmdTag: 'subl' },
  { id: 'notepad++', title: 'Notepad++', desc: 'Lightweight tabbed editor for Windows.', cmdTag: 'notepad++' },
  { id: 'custom', title: 'Custom Executable', desc: 'Specify your own binary (e.g. Zed, Neovim, IDEA).', isCustom: true }
]

const detectedEditors = ref<DetectedEditor[]>([])
const isDetecting = ref(false)
const testStatus = ref<{ loading: boolean; success?: boolean; message?: string } | null>(null)

async function refreshDetectedEditors(): Promise<void> {
  if (!window.api?.detectExternalEditors) return
  isDetecting.value = true
  try {
    const list = await window.api.detectExternalEditors()
    detectedEditors.value = list
  } catch (err) {
    console.warn('Failed to detect editors:', err)
  } finally {
    isDetecting.value = false
  }
}

async function handleBrowseExecutable(): Promise<void> {
  if (!window.api?.openFileDialog) return
  try {
    const res = await window.api.openFileDialog({
      title: 'Select External Editor Executable',
      filters: [
        { name: 'Executables (*.exe, *.cmd, *.bat)', extensions: ['exe', 'cmd', 'bat'] },
        { name: 'All Files', extensions: ['*'] }
      ]
    })
    if (!res.canceled && res.filePath) {
      customEditorPath.value = res.filePath
    }
  } catch (err) {
    console.error('File dialog error:', err)
  }
}

async function handleTestLaunch(): Promise<void> {
  if (!window.api?.testExternalEditorLaunch) return
  testStatus.value = { loading: true }
  try {
    const res = await window.api.testExternalEditorLaunch({
      editorType: externalEditorType.value,
      customPath: customEditorPath.value,
      customArgs: customEditorArgs.value
    })
    testStatus.value = { loading: false, success: res.success, message: res.message }
  } catch (err) {
    testStatus.value = {
      loading: false,
      success: false,
      message: err instanceof Error ? err.message : String(err)
    }
  }
}

function getDetectedInfo(id: ExternalEditorId): DetectedEditor | undefined {
  return detectedEditors.value.find((e) => e.id === id)
}

onMounted(() => {
  refreshDetectedEditors()
})
</script>

<template>
  <div class="space-y-6 text-xs text-slate-200">
    <!-- External Editor Section -->
    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
          <Code2 class="w-3.5 h-3.5 text-blue-400" />
          <span>External Editor Integration</span>
        </h3>
        <button
          type="button"
          class="text-[11px] text-blue-400 hover:text-blue-300 flex items-center space-x-1 transition-colors"
          :disabled="isDetecting"
          @click="refreshDetectedEditors"
        >
          <RefreshCw class="w-3 h-3" :class="{ 'animate-spin': isDetecting }" />
          <span>Detect Installed</span>
        </button>
      </div>

      <div class="p-4 rounded-lg bg-[#1D222E] border border-[#2B3245] space-y-4">
        <!-- Editor Selection Cards -->
        <div class="space-y-2">
          <label class="font-medium text-slate-300 block">Choose Active Editor Mode</label>
          <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
            <button
              v-for="preset in EDITOR_PRESETS"
              :key="preset.id"
              type="button"
              class="p-3 rounded-lg border text-left transition-all relative flex flex-col justify-between"
              :class="[
                externalEditorType === preset.id
                  ? 'bg-blue-600/15 border-blue-500 text-white shadow-sm'
                  : 'bg-[#161B26] border-[#2B3245] text-slate-300 hover:border-slate-500 hover:text-white'
              ]"
              @click="externalEditorType = preset.id"
            >
              <div class="flex items-center justify-between mb-1.5">
                <span class="font-semibold text-xs flex items-center space-x-1.5">
                  <Code2 v-if="preset.isBuiltin" class="w-3.5 h-3.5 text-blue-400" />
                  <span>{{ preset.title }}</span>
                </span>
                <span
                  v-if="preset.isBuiltin"
                  class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                >
                  Built-in
                </span>
                <span
                  v-else-if="preset.isCustom"
                  class="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30"
                >
                  Custom
                </span>
                <span
                  v-else-if="getDetectedInfo(preset.id)?.detected"
                  class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                >
                  Detected
                </span>
                <span v-else-if="preset.cmdTag" class="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/50 text-slate-400">
                  {{ preset.cmdTag }}
                </span>
              </div>
              <p class="text-[11px] text-slate-400 leading-tight">{{ preset.desc }}</p>
            </button>
          </div>
        </div>

        <!-- Custom Path & Arguments Configuration (Shown if external or custom) -->
        <div v-if="externalEditorType !== 'internal'" class="pt-2 border-t border-[#252C3D] space-y-3">
          <div class="space-y-1.5">
            <div class="flex items-center justify-between">
              <label class="font-medium text-slate-300">
                Executable Path {{ externalEditorType === 'custom' ? '(Required)' : '(Optional Override)' }}
              </label>
              <span v-if="getDetectedInfo(externalEditorType)?.executablePath" class="text-[11px] text-slate-400 font-mono truncate max-w-[280px]">
                Auto: {{ getDetectedInfo(externalEditorType)?.executablePath }}
              </span>
            </div>
            <div class="flex items-center space-x-2">
              <input
                v-model="customEditorPath"
                type="text"
                :placeholder="getDetectedInfo(externalEditorType)?.executablePath || 'e.g. C:\\Program Files\\...\\editor.exe'"
                class="flex-1 px-2.5 py-1.5 bg-[#161B26] border border-[#2B3245] rounded-lg text-xs text-white font-mono focus:outline-none focus:border-blue-500"
              />
              <button
                type="button"
                class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5 shrink-0"
                @click="handleBrowseExecutable"
              >
                <FolderOpen class="w-3.5 h-3.5" />
                <span>Browse...</span>
              </button>
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div class="space-y-1.5">
              <div class="flex items-center justify-between">
                <label class="font-medium text-slate-300">Custom Arguments (Optional)</label>
                <button
                  v-if="customEditorArgs"
                  type="button"
                  class="text-[10px] text-slate-400 hover:text-rose-400 transition-colors"
                  title="Reset to default arguments"
                  @click="customEditorArgs = ''"
                >
                  Clear (Reset)
                </button>
              </div>
              <input
                v-model="customEditorArgs"
                type="text"
                placeholder="Leave blank for default (or e.g. -r {file})"
                class="w-full px-2.5 py-1.5 bg-[#161B26] border border-[#2B3245] rounded-lg text-xs text-white font-mono focus:outline-none focus:border-blue-500"
              />
            </div>

            <div class="flex items-end">
              <button
                type="button"
                :disabled="testStatus?.loading"
                class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1.5"
                @click="handleTestLaunch"
              >
                <Play v-if="!testStatus?.loading" class="w-3.5 h-3.5" />
                <RefreshCw v-else class="w-3.5 h-3.5 animate-spin" />
                <span>{{ testStatus?.loading ? 'Launching...' : 'Test Launch Editor' }}</span>
              </button>
            </div>
          </div>

          <!-- Test Feedback Alert -->
          <div
            v-if="testStatus && !testStatus.loading"
            class="p-2.5 rounded-lg border text-xs flex items-center space-x-2"
            :class="[
              testStatus.success
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
            ]"
          >
            <CheckCircle2 v-if="testStatus.success" class="w-4 h-4 shrink-0 text-emerald-400" />
            <AlertCircle v-else class="w-4 h-4 shrink-0 text-rose-400" />
            <span class="truncate">{{ testStatus.message }}</span>
          </div>
        </div>

        <!-- External Sync Options -->
        <div class="pt-2 border-t border-[#252C3D] divide-y divide-[#252C3D] space-y-3">
          <ToggleSwitch
            v-model="openExternalByDefault"
            size="sm"
            label="Open in External Editor by Default"
            description="When opening files from the Explorer tree, automatically launch them in your configured external editor."
          />
          <div class="pt-3">
            <ToggleSwitch
              v-model="autoSyncExternal"
              size="sm"
              label="Auto-sync Changes on Save"
              description="Automatically upload changes back to the remote server via SFTP whenever you save in the external editor."
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Font & Typography Section -->
    <div class="space-y-3">
      <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400">
        Typography & Display (Built-in Monaco)
      </h3>

      <div class="p-4 rounded-lg bg-[#1D222E] border border-[#2B3245] space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <div class="flex items-center justify-between">
              <label class="font-medium text-slate-300">Editor Font Family</label>
              <span
                v-if="isCustomFont"
                class="text-[10px] text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded border border-blue-500/20"
              >
                Custom
              </span>
            </div>
            <select
              :value="isCustomFont ? 'custom' : fontFamily"
              class="w-full px-2.5 py-1.5 bg-[#161B26] border border-[#2B3245] rounded-lg text-xs text-white focus:outline-none focus:border-blue-500 cursor-pointer"
              @change="handleFontSelect"
            >
              <option v-for="f in fontFamilies" :key="f.value" :value="f.value">
                {{ f.label }}
              </option>
              <option value="custom">Custom Font...</option>
            </select>
            <input
              v-if="isCustomFont"
              :value="customFontInput"
              type="text"
              placeholder="e.g. 'Hack', 'Operator Mono', monospace"
              class="w-full mt-1.5 px-2.5 py-1.5 bg-[#161B26] border border-[#2B3245] rounded-lg text-xs text-white font-mono focus:outline-none focus:border-blue-500"
              @input="handleCustomFontInput"
            />
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-1.5">
              <label class="font-medium text-slate-300">Font Size (px)</label>
              <input
                v-model.number="fontSize"
                type="number"
                min="10"
                max="32"
                class="w-full px-2.5 py-1.5 bg-[#161B26] border border-[#2B3245] rounded-lg text-xs text-white font-mono focus:outline-none focus:border-blue-500"
              />
            </div>

            <div class="space-y-1.5">
              <label class="font-medium text-slate-300">Tab Size</label>
              <select
                v-model.number="tabSize"
                class="w-full px-2.5 py-1.5 bg-[#161B26] border border-[#2B3245] rounded-lg text-xs text-white font-mono focus:outline-none focus:border-blue-500 cursor-pointer"
              >
                <option :value="2">2 spaces</option>
                <option :value="4">4 spaces</option>
                <option :value="8">8 spaces</option>
              </select>
            </div>
          </div>
        </div>

        <div class="pt-2">
          <ToggleSwitch
            v-model="fontLigatures"
            size="sm"
            label="Enable Font Ligatures"
            description="Render special multi-character programming symbols (e.g., =>, !==, ->)."
          />
        </div>
      </div>
    </div>

    <!-- Layout & Controls Section -->
    <div class="space-y-3">
      <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400">
        Editor Behaviors
      </h3>

      <div class="p-4 rounded-lg bg-[#1D222E] border border-[#2B3245] divide-y divide-[#252C3D] space-y-3">
        <ToggleSwitch
          v-model="minimap"
          size="sm"
          label="Show Code Minimap"
          description="Display an overview slider map on the right side of the editor pane."
        />
        <div class="pt-3">
          <ToggleSwitch
            v-model="lineNumbers"
            size="sm"
            label="Line Numbers Gutter"
            description="Show continuous line numbering next to source code lines."
          />
        </div>
        <div class="pt-3">
          <ToggleSwitch
            v-model="wordWrap"
            size="sm"
            label="Soft Word Wrap"
            description="Wrap long lines to fit the current editor viewport width without horizontal scrolling."
          />
        </div>
        <div class="pt-3">
          <ToggleSwitch
            v-model="formatOnSave"
            size="sm"
            label="Format on Save"
            description="Automatically format document syntax when saving (Ctrl+S / Cmd+S)."
          />
        </div>
      </div>
    </div>

    <!-- Git Version Control & Global Credentials Section -->
    <div class="space-y-3">
      <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400">
        Git Version Control & Credentials
      </h3>

      <div class="p-4 rounded-lg bg-[#1D222E] border border-[#2B3245] flex items-center justify-between">
        <div class="flex items-start space-x-3">
          <div class="p-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 shrink-0">
            <ShieldCheck class="w-5 h-5 text-blue-400" />
          </div>
          <div class="space-y-1">
            <div class="text-sm font-semibold text-slate-100 flex items-center space-x-2">
              <span>Git Credential Global</span>
              <span
                v-if="hasCredentials"
                class="px-2 py-0.5 rounded-full text-[10px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
              >
                Aktif ({{ globalCredentials.username }})
              </span>
              <span
                v-else
                class="px-2 py-0.5 rounded-full text-[10px] bg-slate-700/50 text-slate-400 border border-slate-600/30"
              >
                Belum diatur
              </span>
            </div>
            <p class="text-xs text-slate-400 leading-relaxed max-w-xl">
              Dipakai untuk semua koneksi SSH yang menjalankan Git Pull, Git Push, atau Cherry-pick.
            </p>
          </div>
        </div>

        <button
          type="button"
          class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm flex items-center space-x-1.5 shrink-0"
          @click="openModal"
        >
          <Key class="w-3.5 h-3.5" />
          <span>{{ hasCredentials ? 'Ubah Credential' : 'Atur Credential' }}</span>
        </button>
      </div>

      <GitCredentialModal
        :show="isGitCredentialModalOpen"
        @close="closeModal"
      />
    </div>
  </div>
</template>
