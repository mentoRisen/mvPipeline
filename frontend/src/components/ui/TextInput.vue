<template>
  <div class="mf-field" :class="{ 'mf-field--error': Boolean(error) }">
    <label v-if="label" :for="resolvedId" class="mf-label">{{ label }}</label>
    <input
      :id="resolvedId"
      :class="['mf-input', $attrs.class]"
      :value="modelValue"
      :type="type"
      :autocomplete="autocomplete"
      :placeholder="placeholder"
      :disabled="disabled"
      :required="required"
      v-bind="attrsWithoutClass"
      @input="$emit('update:modelValue', $event.target.value)"
    />
    <p v-if="error" class="mf-field-error">{{ error }}</p>
    <p v-else-if="hint" class="mf-field-hint">{{ hint }}</p>
  </div>
</template>

<script>
let idSeq = 0

export default {
  name: 'TextInput',
  inheritAttrs: false,
  data() {
    return {
      autoId: `mf-input-${++idSeq}`,
    }
  },
  props: {
    modelValue: {
      type: [String, Number],
      default: '',
    },
    label: {
      type: String,
      default: '',
    },
    hint: {
      type: String,
      default: '',
    },
    error: {
      type: String,
      default: '',
    },
    type: {
      type: String,
      default: 'text',
    },
    autocomplete: {
      type: String,
      default: undefined,
    },
    placeholder: {
      type: String,
      default: '',
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    required: {
      type: Boolean,
      default: false,
    },
    id: {
      type: String,
      default: '',
    },
  },
  emits: ['update:modelValue'],
  computed: {
    resolvedId() {
      return this.id || this.autoId
    },
    attrsWithoutClass() {
      const { class: _c, ...rest } = this.$attrs
      return rest
    },
  },
}
</script>
