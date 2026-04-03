<template>
  <button
    :type="type"
    :disabled="disabled"
    :class="['mf-btn', 'mf-btn--primary', sizeClass, { 'mf-btn--block': block }]"
  >
    <slot />
  </button>
</template>

<script>
export default {
  name: 'PrimaryButton',
  props: {
    type: {
      type: String,
      default: 'button',
    },
    disabled: {
      type: Boolean,
      default: false,
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
    sizeClass() {
      if (this.size === 'sm') return 'mf-btn--sm'
      if (this.size === 'lg') return 'mf-btn--lg'
      return ''
    },
  },
}
</script>
