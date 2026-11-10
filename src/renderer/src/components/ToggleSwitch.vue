<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    modelValue: boolean
    disabled?: boolean
    size?: 'sm' | 'md'
    label?: string
    description?: string
  }>(),
  {
    disabled: false,
    size: 'md',
    label: '',
    description: ''
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

function toggle(): void {
  if (props.disabled) return
  emit('update:modelValue', !props.modelValue)
}
</script>

<template>
  <div
    class="flex items-center justify-between gap-3"
    :class="props.disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'"
    @click="toggle"
  >
    <div v-if="props.label || props.description || $slots.default" class="flex-1 min-w-0">
      <slot>
        <div class="text-xs font-medium text-slate-200 leading-snug">{{ props.label }}</div>
        <div v-if="props.description" class="text-[11px] text-slate-400 leading-snug mt-0.5">
          {{ props.description }}
        </div>
      </slot>
    </div>

    <button
      type="button"
      role="switch"
      :aria-checked="props.modelValue"
      :disabled="props.disabled"
      class="relative inline-flex shrink-0 rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/70"
      :class="[
        props.size === 'sm' ? 'h-4 w-7' : 'h-5 w-9',
        props.modelValue ? 'bg-emerald-500' : 'bg-[#2c3547]',
        props.disabled ? 'cursor-not-allowed' : 'cursor-pointer'
      ]"
      @click.stop="toggle"
    >
      <span
        class="pointer-events-none inline-block transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
        :class="[
          props.size === 'sm' ? 'h-3 w-3' : 'h-4 w-4',
          props.modelValue
            ? props.size === 'sm'
              ? 'translate-x-3'
              : 'translate-x-4'
            : 'translate-x-0'
        ]"
      />
    </button>
  </div>
</template>

