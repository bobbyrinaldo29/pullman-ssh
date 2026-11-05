<script setup lang="ts">
import { ref } from 'vue'
import { Server, Terminal, Database, Bell, CheckCircle2, Sparkles } from 'lucide-vue-next'

const appVersion = '1.3.1'
const activeTab = ref('hosts')
</script>

<template>
  <div class="flex h-screen w-screen bg-[#0D0E12] text-slate-100 font-sans select-none overflow-hidden">
    <!-- Sidebar -->
    <aside class="w-64 bg-[#13151B] border-r border-[#1E212B] flex flex-col justify-between p-4">
      <div class="space-y-6">
        <!-- Logo / App Header -->
        <div class="flex items-center space-x-3 px-2">
          <div class="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-lg shadow-blue-500/20">
            <Server class="w-5 h-5" />
          </div>
          <div>
            <h1 class="text-sm font-semibold tracking-wide text-white">DO.MBA Pull Manager</h1>
            <p class="text-xs text-slate-400">v{{ appVersion }} (Electron + Vue)</p>
          </div>
        </div>

        <!-- Navigation Links -->
        <nav class="space-y-1">
          <button
            :class="[
              'w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
              activeTab === 'hosts' ? 'bg-blue-600/10 text-blue-400 border border-blue-500/20' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            ]"
            @click="activeTab = 'hosts'"
          >
            <Server class="w-4 h-4" />
            <span>Pull Blast</span>
          </button>

          <button
            :class="[
              'w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
              activeTab === 'terminal' ? 'bg-blue-600/10 text-blue-400 border border-blue-500/20' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            ]"
            @click="activeTab = 'terminal'"
          >
            <Terminal class="w-4 h-4" />
            <span>SFTP & Terminal</span>
          </button>

          <button
            :class="[
              'w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
              activeTab === 'db' ? 'bg-blue-600/10 text-blue-400 border border-blue-500/20' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            ]"
            @click="activeTab = 'db'"
          >
            <Database class="w-4 h-4" />
            <span>DB Blast</span>
          </button>

          <button
            :class="[
              'w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
              activeTab === 'redmine' ? 'bg-blue-600/10 text-blue-400 border border-blue-500/20' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            ]"
            @click="activeTab = 'redmine'"
          >
            <Bell class="w-4 h-4" />
            <span>Redmine Tasks</span>
          </button>
        </nav>
      </div>

      <!-- Environment Ready Status -->
      <div class="p-3 bg-[#181A22] border border-[#262936] rounded-xl text-xs space-y-1.5">
        <div class="flex items-center space-x-2 text-emerald-400 font-medium">
          <CheckCircle2 class="w-4 h-4" />
          <span>Environment Siap</span>
        </div>
        <p class="text-slate-400 text-[11px] leading-relaxed">
          Vue 3 + TypeScript + Tailwind + Electron-Vite berhasil dikonfigurasi.
        </p>
      </div>
    </aside>

    <!-- Main Content Area -->
    <main class="flex-1 flex flex-col bg-[#0D0E12]">
      <!-- Header -->
      <header class="h-14 border-b border-[#1E212B] px-6 flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <Sparkles class="w-4 h-4 text-blue-400" />
          <span class="text-sm font-semibold capitalize text-slate-200">{{ activeTab }} Module</span>
        </div>
        <div class="text-xs text-slate-500 font-mono">
          Ready for Module Implementation
        </div>
      </header>

      <!-- Content Canvas -->
      <div class="flex-1 p-6 flex flex-col items-center justify-center text-center">
        <div class="max-w-md space-y-4">
          <div class="w-14 h-14 rounded-2xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center text-blue-400 mx-auto">
            <Server class="w-7 h-7" />
          </div>
          <h2 class="text-lg font-semibold text-white">DO.MBA Pull Manager v2</h2>
          <p class="text-sm text-slate-400 leading-relaxed">
            Struktur project Electron dengan <strong class="text-slate-200">Vue 3, TypeScript, Lucide Icons, Pinia, dan Tailwind CSS</strong> telah terpasang dan teruji siap digunakan.
          </p>
        </div>
      </div>
    </main>
  </div>
</template>
