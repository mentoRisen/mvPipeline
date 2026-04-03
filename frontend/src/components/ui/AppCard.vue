<template>
  <div :class="cardClass">
    <div v-if="title || $slots.title" class="mf-card__header">
      <slot name="title">{{ title }}</slot>
    </div>
    <div class="mf-card__body">
      <slot />
    </div>
  </div>
</template>

<script>
export default {
  name: 'AppCard',
  props: {
    title: {
      type: String,
      default: '',
    },
    /** Softer elevation */
    quiet: {
      type: Boolean,
      default: false,
    },
    /** Remove outer padding when using full-bleed content */
    flush: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    cardClass() {
      return [
        'mf-card',
        { 'mf-card--quiet': this.quiet, 'mf-card--flush': this.flush },
      ]
    },
  },
}
</script>
