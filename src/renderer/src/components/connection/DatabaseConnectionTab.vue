<script setup lang="ts">
import { Eye, EyeOff, ChevronsUpDown, HelpCircle } from 'lucide-vue-next'

defineProps<{
  dbHost: string
  dbPort: number
  dbUser: string
  dbPassword: string
  showDbPassword: boolean
  dbSavePassword: boolean
  database: string
}>()

const emit = defineEmits<{
  (e: 'update:dbHost', val: string): void
  (e: 'update:dbPort', val: number): void
  (e: 'update:dbUser', val: string): void
  (e: 'update:dbPassword', val: string): void
  (e: 'update:showDbPassword', val: boolean): void
  (e: 'update:dbSavePassword', val: boolean): void
  (e: 'update:database', val: string): void
}>()
</script>

<template>
  <!-- Host & Port -->
  <div class="flex items-center">
    <label class="w-36 text-[#C2C9D6] text-xs font-medium">Host</label>
    <div class="flex-1 flex items-center space-x-2">
      <input
        :value="dbHost"
        type="text"
        placeholder="127.0.0.1"
        class="flex-1 bg-[#161922] border border-[#2D3547] rounded-lg px-3 py-1.5 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
        @input="emit('update:dbHost', ($event.target as HTMLInputElement).value)"
      />
      <div class="relative w-28">
        <input
          :value="dbPort"
          type="number"
          class="w-full bg-[#161922] border border-[#2D3547] rounded-lg px-3 py-1.5 pr-6 text-xs text-white focus:outline-none focus:border-blue-500 transition-colors"
          @input="emit('update:dbPort', Number(($event.target as HTMLInputElement).value) || 3306)"
        />
        <ChevronsUpDown
          class="w-3.5 h-3.5 text-[#64748B] absolute right-2 top-2 pointer-events-none"
        />
      </div>
    </div>
  </div>

  <!-- User -->
  <div class="flex items-center">
    <label class="w-36 text-[#C2C9D6] text-xs font-medium">User</label>
    <div class="flex-1">
      <input
        :value="dbUser"
        type="text"
        placeholder="root"
        class="w-full bg-[#161922] border border-[#2D3547] rounded-lg px-3 py-1.5 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
        @input="emit('update:dbUser', ($event.target as HTMLInputElement).value)"
      />
    </div>
  </div>

  <!-- Password -->
  <div class="flex items-center">
    <label class="w-36 text-[#C2C9D6] text-xs font-medium">Password</label>
    <div class="flex-1 relative">
      <input
        :value="dbPassword"
        :type="showDbPassword ? 'text' : 'password'"
        placeholder="••••••••••••"
        class="w-full bg-[#161922] border border-[#2D3547] rounded-lg px-3 py-1.5 pr-8 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
        @input="emit('update:dbPassword', ($event.target as HTMLInputElement).value)"
      />
      <button
        type="button"
        class="absolute right-2.5 top-2 text-[#64748B] hover:text-white transition-colors"
        @click="emit('update:showDbPassword', !showDbPassword)"
      >
        <Eye v-if="!showDbPassword" class="w-3.5 h-3.5" />
        <EyeOff v-else class="w-3.5 h-3.5" />
      </button>
    </div>
  </div>

  <!-- Save password checkbox -->
  <div class="flex items-center">
    <div class="w-36"></div>
    <div class="flex-1 flex items-center space-x-2">
      <input
        id="save-db-password-checkbox"
        :checked="dbSavePassword"
        type="checkbox"
        class="w-4 h-4 rounded bg-[#161922] border-[#2D3547] text-blue-500 focus:ring-0 focus:ring-offset-0 cursor-pointer accent-blue-500"
        @change="emit('update:dbSavePassword', ($event.target as HTMLInputElement).checked)"
      />
      <label for="save-db-password-checkbox" class="text-xs text-[#C2C9D6] cursor-pointer">
        Save password
      </label>
      <HelpCircle class="w-3.5 h-3.5 text-[#64748B] cursor-help" />
    </div>
  </div>

  <!-- Database -->
  <div class="flex items-center">
    <label class="w-36 text-[#C2C9D6] text-xs font-medium">Database</label>
    <div class="flex-1">
      <input
        :value="database"
        type="text"
        placeholder="Optional"
        class="w-full bg-[#161922] border border-[#2D3547] rounded-lg px-3 py-1.5 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
        @input="emit('update:database', ($event.target as HTMLInputElement).value)"
      />
    </div>
  </div>
</template>

