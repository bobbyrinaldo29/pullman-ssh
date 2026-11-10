<script setup lang="ts">
import { ShieldAlert } from 'lucide-vue-next'

withDefaults(
  defineProps<{
    size?: 'sm' | 'md'
  }>(),
  {
    size: 'md'
  }
)
</script>

<template>
  <span
    class="inline-flex items-center font-bold uppercase select-none shrink-0 transition-colors"
    :class="[
      size === 'sm'
        ? 'space-x-1 px-1.5 py-0.5 rounded-[5px] text-[9px] border border-[#852634] bg-[#33171F] text-[#FFA4A6]'
        : 'space-x-1.5 px-2 py-0.5 rounded-[7px] text-[10px] border border-[#8C2836] bg-[#361922] text-[#FFA4A6]'
    ]"
  >
    <ShieldAlert
      :class="size === 'sm' ? 'w-2 h-2 text-[#FFA4A6]' : 'w-2.5 h-2.5 text-[#FFA4A6]'"
      stroke-width="2.2"
    />
    <span class="tracking-wide leading-none">PROD</span>
  </span>
</template>

