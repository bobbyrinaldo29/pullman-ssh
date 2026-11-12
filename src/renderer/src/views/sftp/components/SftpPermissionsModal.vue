<script setup lang="ts">
import { Shield, X } from 'lucide-vue-next'
import { SftpFileItem } from '../types'

defineProps<{
  show: boolean
  permItem: SftpFileItem | null
  isPermSudo: boolean
  permNumeric: string
  permOwnerRead: boolean
  permOwnerWrite: boolean
  permOwnerExec: boolean
  permGroupRead: boolean
  permGroupWrite: boolean
  permGroupExec: boolean
  permPublicRead: boolean
  permPublicWrite: boolean
  permPublicExec: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save'): void
  (e: 'update:permNumeric', val: string): void
  (e: 'update:permOwnerRead', val: boolean): void
  (e: 'update:permOwnerWrite', val: boolean): void
  (e: 'update:permOwnerExec', val: boolean): void
  (e: 'update:permGroupRead', val: boolean): void
  (e: 'update:permGroupWrite', val: boolean): void
  (e: 'update:permGroupExec', val: boolean): void
  (e: 'update:permPublicRead', val: boolean): void
  (e: 'update:permPublicWrite', val: boolean): void
  (e: 'update:permPublicExec', val: boolean): void
  (e: 'checkbox-change'): void
  (e: 'numeric-change', val: string): void
}>()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show && permItem"
      class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 select-none"
      @click.self="emit('close')"
    >
      <div class="bg-[#1C202B] border border-[#2D3446] rounded-xl shadow-2xl w-full max-w-sm p-4 text-slate-200">
        <div class="flex items-center justify-between pb-3 border-b border-[#2B3244] mb-3">
          <h3 class="text-sm font-semibold text-white flex items-center space-x-2">
            <Shield class="w-4 h-4" :class="isPermSudo ? 'text-amber-400' : 'text-sky-400'" />
            <span>Change File Attributes {{ isPermSudo ? '(as Sudo)' : '' }}</span>
          </h3>
          <button
            type="button"
            class="text-slate-400 hover:text-white p-1 rounded"
            @click="emit('close')"
          >
            <X class="w-4 h-4" />
          </button>
        </div>

        <p class="text-xs text-slate-400 mb-3 truncate">
          Please select the new permissions for <span class="text-white font-mono font-medium">{{ permItem.name }}</span>:
        </p>

        <div class="grid grid-cols-3 gap-3 mb-4">
          <!-- Owner permissions -->
          <div class="p-2.5 rounded-lg bg-[#141720] border border-[#272E3E]">
            <div class="text-[11px] font-semibold text-slate-300 mb-2">Owner</div>
            <label class="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer mb-1">
              <input
                :checked="permOwnerRead"
                type="checkbox"
                class="rounded bg-[#1C202B] border-slate-600 text-blue-600 focus:ring-0"
                @change="emit('update:permOwnerRead', ($event.target as HTMLInputElement).checked); emit('checkbox-change')"
              />
              <span>Read</span>
            </label>
            <label class="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer mb-1">
              <input
                :checked="permOwnerWrite"
                type="checkbox"
                class="rounded bg-[#1C202B] border-slate-600 text-blue-600 focus:ring-0"
                @change="emit('update:permOwnerWrite', ($event.target as HTMLInputElement).checked); emit('checkbox-change')"
              />
              <span>Write</span>
            </label>
            <label class="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer">
              <input
                :checked="permOwnerExec"
                type="checkbox"
                class="rounded bg-[#1C202B] border-slate-600 text-blue-600 focus:ring-0"
                @change="emit('update:permOwnerExec', ($event.target as HTMLInputElement).checked); emit('checkbox-change')"
              />
              <span>Execute</span>
            </label>
          </div>

          <!-- Group permissions -->
          <div class="p-2.5 rounded-lg bg-[#141720] border border-[#272E3E]">
            <div class="text-[11px] font-semibold text-slate-300 mb-2">Group</div>
            <label class="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer mb-1">
              <input
                :checked="permGroupRead"
                type="checkbox"
                class="rounded bg-[#1C202B] border-slate-600 text-blue-600 focus:ring-0"
                @change="emit('update:permGroupRead', ($event.target as HTMLInputElement).checked); emit('checkbox-change')"
              />
              <span>Read</span>
            </label>
            <label class="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer mb-1">
              <input
                :checked="permGroupWrite"
                type="checkbox"
                class="rounded bg-[#1C202B] border-slate-600 text-blue-600 focus:ring-0"
                @change="emit('update:permGroupWrite', ($event.target as HTMLInputElement).checked); emit('checkbox-change')"
              />
              <span>Write</span>
            </label>
            <label class="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer">
              <input
                :checked="permGroupExec"
                type="checkbox"
                class="rounded bg-[#1C202B] border-slate-600 text-blue-600 focus:ring-0"
                @change="emit('update:permGroupExec', ($event.target as HTMLInputElement).checked); emit('checkbox-change')"
              />
              <span>Execute</span>
            </label>
          </div>

          <!-- Public permissions -->
          <div class="p-2.5 rounded-lg bg-[#141720] border border-[#272E3E]">
            <div class="text-[11px] font-semibold text-slate-300 mb-2">Public</div>
            <label class="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer mb-1">
              <input
                :checked="permPublicRead"
                type="checkbox"
                class="rounded bg-[#1C202B] border-slate-600 text-blue-600 focus:ring-0"
                @change="emit('update:permPublicRead', ($event.target as HTMLInputElement).checked); emit('checkbox-change')"
              />
              <span>Read</span>
            </label>
            <label class="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer mb-1">
              <input
                :checked="permPublicWrite"
                type="checkbox"
                class="rounded bg-[#1C202B] border-slate-600 text-blue-600 focus:ring-0"
                @change="emit('update:permPublicWrite', ($event.target as HTMLInputElement).checked); emit('checkbox-change')"
              />
              <span>Write</span>
            </label>
            <label class="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer">
              <input
                :checked="permPublicExec"
                type="checkbox"
                class="rounded bg-[#1C202B] border-slate-600 text-blue-600 focus:ring-0"
                @change="emit('update:permPublicExec', ($event.target as HTMLInputElement).checked); emit('checkbox-change')"
              />
              <span>Execute</span>
            </label>
          </div>
        </div>

        <!-- Numeric value input -->
        <div class="p-2.5 rounded-lg bg-[#141720] border border-[#272E3E] flex items-center justify-between mb-4">
          <span class="text-xs text-slate-300 font-medium">Numeric value:</span>
          <input
            :value="permNumeric"
            type="text"
            maxlength="4"
            class="w-20 bg-[#1C202B] border border-[#2D3547] text-white rounded px-2.5 py-1 text-xs text-center font-mono font-bold focus:outline-none focus:border-blue-500"
            @input="emit('numeric-change', ($event.target as HTMLInputElement).value)"
            @keydown.enter="emit('save')"
          />
        </div>

        <div class="flex items-center justify-end space-x-2 pt-2 border-t border-[#2B3244]">
          <button
            type="button"
            class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 text-xs font-medium transition-colors"
            @click="emit('close')"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm"
            @click="emit('save')"
          >
            OK
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

