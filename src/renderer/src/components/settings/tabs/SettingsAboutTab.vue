<script setup lang="ts">
import { Server, Shield, Heart } from 'lucide-vue-next'

const appInfo = {
  name: 'Pullman SSH Client & Database Workbench',
  version: '2.0.0',
  electron: '30.0.0',
  chromium: '124.0.6367.243',
  node: '20.12.2',
  v8: '12.4.254.20-electron.0',
  os: navigator.userAgent.includes('Mac') ? 'macOS' : 'Windows x64'
}
</script>

<template>
  <div class="space-y-6 text-xs text-slate-200">
    <!-- Hero / App Header -->
    <div class="p-6 rounded-xl bg-gradient-to-br from-[#1E2536] to-[#141822] border border-[#2B3245] flex items-center space-x-4">
      <div class="w-14 h-14 rounded-2xl bg-blue-600 flex items-center justify-center text-white shadow-lg shadow-blue-500/20 shrink-0">
        <Server class="w-7 h-7" />
      </div>
      <div>
        <h2 class="text-base font-bold text-white tracking-tight">{{ appInfo.name }}</h2>
        <div class="flex items-center space-x-2 mt-1">
          <span class="px-2 py-0.5 rounded-full bg-blue-500/20 border border-blue-400/30 text-blue-300 font-mono text-[11px] font-semibold">
            v{{ appInfo.version }}
          </span>
          <span class="text-slate-400 text-[11px]">Production Release</span>
        </div>
      </div>
    </div>

    <!-- Software Environment & Runtime -->
    <div class="space-y-3">
      <h3 class="text-xs font-semibold text-white uppercase tracking-wider text-slate-400">
        System & Runtime Stack
      </h3>

      <div class="p-4 rounded-lg bg-[#1D222E] border border-[#2B3245] space-y-2.5">
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div class="p-2.5 rounded-lg bg-[#161B26] border border-[#252C3D]">
            <div class="text-[10px] text-slate-400">Electron</div>
            <div class="text-xs font-mono font-semibold text-slate-200 mt-0.5">{{ appInfo.electron }}</div>
          </div>
          <div class="p-2.5 rounded-lg bg-[#161B26] border border-[#252C3D]">
            <div class="text-[10px] text-slate-400">Chromium</div>
            <div class="text-xs font-mono font-semibold text-slate-200 mt-0.5">{{ appInfo.chromium }}</div>
          </div>
          <div class="p-2.5 rounded-lg bg-[#161B26] border border-[#252C3D]">
            <div class="text-[10px] text-slate-400">Node.js</div>
            <div class="text-xs font-mono font-semibold text-slate-200 mt-0.5">{{ appInfo.node }}</div>
          </div>
          <div class="p-2.5 rounded-lg bg-[#161B26] border border-[#252C3D]">
            <div class="text-[10px] text-slate-400">Platform</div>
            <div class="text-xs font-mono font-semibold text-slate-200 mt-0.5">{{ appInfo.os }}</div>
          </div>
          <div class="p-2.5 rounded-lg bg-[#161B26] border border-[#252C3D]">
            <div class="text-[10px] text-slate-400">Frontend Engine</div>
            <div class="text-xs font-mono font-semibold text-slate-200 mt-0.5">Vue 3 + Monaco</div>
          </div>
          <div class="p-2.5 rounded-lg bg-[#161B26] border border-[#252C3D]">
            <div class="text-[10px] text-slate-400">Terminal Core</div>
            <div class="text-xs font-mono font-semibold text-slate-200 mt-0.5">Xterm.js 5.5.0</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Security & License -->
    <div class="p-4 rounded-lg bg-[#1D222E] border border-[#2B3245] flex items-center justify-between text-slate-400 text-[11px]">
      <div class="flex items-center space-x-2">
        <Shield class="w-4 h-4 text-emerald-400" />
        <span>End-to-end encrypted credential storage using OS native keychain</span>
      </div>
      <div class="flex items-center space-x-1 text-slate-500">
        <span>Crafted with</span>
        <Heart class="w-3 h-3 text-rose-500 fill-rose-500" />
      </div>
    </div>
  </div>
</template>
