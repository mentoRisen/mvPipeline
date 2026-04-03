<template>
  <button
    :type="type"
    :disabled="disabled"
    :class="['mf-btn', variantClass, sizeClass, { 'mf-btn--block': block }]"
  >
    <slot />
  </button>
</template>

<script>
export default {
  name: 'SecondaryButton',
  props: {
    type: {
      type: String,
      default: 'button',
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    /** `outline`: bordered surface (default). `ghost`: minimal for toolbars. */
    variant: {
      type: String,
      default: 'outline',
      validator: (v) => ['outline', 'ghost'].includes(v),
    },
    size: {
      type: String,
      default: 'md',
      validator: (v) => ['sm', 'md', 'lg'].includes(v),
    },
    block: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    variantClass() {
      return this.variant === 'ghost' ? 'mf-btn--ghost' : 'mf-btn--secondary'
    },
    sizeClass() {
      if (this.size === 'sm') return 'mf-btn--sm'
      if (this.size === 'lg') return 'mf-btn--lg'
      return ''
    },
  },
}
</script>
