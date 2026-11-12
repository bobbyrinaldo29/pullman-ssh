<script setup lang="ts">
import { ref } from 'vue'
import SftpView from '../views/sftp/SftpView.vue'
import { HostItem } from '../types/connection'

defineProps<{
  hosts: HostItem[]
  initialHostId?: number | null
}>()

const emit = defineEmits<{
  (e: 'back-to-hosts'): void
}>()

const innerRef = ref<InstanceType<typeof SftpView> | null>(null)

function openNewTabForHost(host: HostItem): void {
  innerRef.value?.openNewTabForHost(host)
}

defineExpose({
  openNewTabForHost
})
</script>

<template>
  <SftpView
    ref="innerRef"
    :hosts="hosts"
    :initial-host-id="initialHostId"
    @back-to-hosts="emit('back-to-hosts')"
  />
</template>
