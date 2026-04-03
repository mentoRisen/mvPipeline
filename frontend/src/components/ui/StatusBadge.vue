<template>
  <span :class="['mf-badge', variantClass, { 'mf-badge--dot': dot }]">
    <slot />
  </span>
</template>

<script>
const VARIANT_MAP = {
  success: 'mf-badge--success',
  warning: 'mf-badge--warning',
  error: 'mf-badge--error',
  info: 'mf-badge--info',
  neutral: 'mf-badge--neutral',
  /** Premium / workflow emphasis */
  accent: 'mf-badge--accent',
}

export default {
  name: 'StatusBadge',
  props: {
    variant: {
      type: String,
      default: 'neutral',
      validator: (v) => v in VARIANT_MAP,
    },
    /** Reserved for future pulse dot; shows a quiet cyan emphasis when true */
    dot: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    variantClass() {
      return VARIANT_MAP[this.variant] || VARIANT_MAP.neutral
    },
  },
}
</script>

<style scoped>
.mf-badge--accent {
  background: rgba(124, 58, 237, 0.1);
  color: var(--color-accent-violet);
  border-color: rgba(124, 58, 237, 0.22);
}

.mf-badge--dot::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: var(--radius-pill);
  background: var(--color-accent-cyan);
  flex-shrink: 0;
  box-shadow: 0 0 0 2px var(--color-accent-cyan-muted);
}
</style>
