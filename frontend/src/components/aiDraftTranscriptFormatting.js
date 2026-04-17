/**
 * Pretty-print AI draft transcript payloads with selective JSON-string expansion.
 * Rendering-only: callers pass payloads by reference; this module never mutates inputs.
 */

/** @typedef {{ target: 'top' | 'messagesItem', field: string }} AiDraftTranscriptJsonExpansionRule */

/** @type {readonly AiDraftTranscriptJsonExpansionRule[]} */
export const AI_DRAFT_TRANSCRIPT_JSON_EXPANSION_RULES = Object.freeze([
  { target: 'top', field: 'content' },
  { target: 'top', field: 'brief' },
  { target: 'messagesItem', field: 'content' },
])

/**
 * @param {string} s
 * @returns {string}
 */
function escapeHtml(s) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * @param {unknown} value
 * @returns {{ ok: true, value: unknown } | { ok: false }}
 */
function safeClonePayload(value) {
  if (value === null || value === undefined) {
    return { ok: true, value }
  }
  if (typeof value !== 'object') {
    return { ok: true, value }
  }
  try {
    if (typeof structuredClone === 'function') {
      return { ok: true, value: structuredClone(value) }
    }
  } catch {
    /* fall through */
  }
  try {
    return { ok: true, value: JSON.parse(JSON.stringify(value)) }
  } catch {
    return { ok: false }
  }
}

/**
 * @param {string} key
 * @param {Record<string, unknown>} obj
 * @param {Set<string>} expandedPaths
 * @param {string} pathPrefix
 */
function expandTopField(key, obj, expandedPaths, pathPrefix) {
  if (!Object.prototype.hasOwnProperty.call(obj, key)) {
    return
  }
  const v = obj[key]
  if (typeof v !== 'string') {
    return
  }
  try {
    obj[key] = JSON.parse(v)
    const p = pathPrefix === '' ? key : `${pathPrefix}.${key}`
    expandedPaths.add(p)
  } catch {
    /* keep original string */
  }
}

/**
 * @param {string} field
 * @param {unknown} messagesVal
 * @param {Set<string>} expandedPaths
 */
function expandMessagesItemField(field, messagesVal, expandedPaths) {
  if (!Array.isArray(messagesVal)) {
    return
  }
  messagesVal.forEach((item, i) => {
    if (item === null || typeof item !== 'object' || Array.isArray(item)) {
      return
    }
    const rec = /** @type {Record<string, unknown>} */ (item)
    if (!Object.prototype.hasOwnProperty.call(rec, field)) {
      return
    }
    const v = rec[field]
    if (typeof v !== 'string') {
      return
    }
    try {
      rec[field] = JSON.parse(v)
      expandedPaths.add(`messages.${i}.${field}`)
    } catch {
      /* keep original string */
    }
  })
}

/**
 * @param {Record<string, unknown>} payload
 * @param {Set<string>} expandedPaths
 */
function applyJsonStringExpansionRules(payload, expandedPaths) {
  for (const rule of AI_DRAFT_TRANSCRIPT_JSON_EXPANSION_RULES) {
    if (rule.target === 'top') {
      expandTopField(rule.field, payload, expandedPaths, '')
    } else if (rule.target === 'messagesItem') {
      if (!Object.prototype.hasOwnProperty.call(payload, 'messages')) {
        continue
      }
      expandMessagesItemField(rule.field, payload.messages, expandedPaths)
    }
  }
}

/**
 * @param {unknown} value
 * @param {string} path
 * @param {number} indent
 * @param {Set<string>} expandedPaths
 * @returns {string}
 */
function prettyValueToHtml(value, path, indent, expandedPaths) {
  const pad = '  '.repeat(indent)
  if (value === null) {
    return 'null'
  }
  if (typeof value === 'string') {
    return escapeHtml(JSON.stringify(value))
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return '[]'
    }
    const nextIndent = indent + 1
    const innerPad = '  '.repeat(nextIndent)
    const lines = value.map((item, i) => {
      const p = path === '' ? String(i) : `${path}.${i}`
      let part = prettyValueToHtml(item, p, nextIndent, expandedPaths)
      if (expandedPaths.has(p)) {
        part = `<span class="ai-draft-ev-payload-json-expanded">${part}</span>`
      }
      return `${innerPad}${part}`
    })
    return `[\n${lines.join(',\n')}\n${pad}]`
  }
  if (typeof value === 'object') {
    const rec = /** @type {Record<string, unknown>} */ (value)
    const keys = Object.keys(rec)
    if (keys.length === 0) {
      return '{}'
    }
    const nextIndent = indent + 1
    const innerPad = '  '.repeat(nextIndent)
    const lines = keys.map((k) => {
      const childPath = path === '' ? k : `${path}.${k}`
      const v = rec[k]
      let inner = prettyValueToHtml(v, childPath, nextIndent, expandedPaths)
      if (expandedPaths.has(childPath)) {
        inner = `<span class="ai-draft-ev-payload-json-expanded">${inner}</span>`
      }
      return `${innerPad}${escapeHtml(JSON.stringify(k))}: ${inner}`
    })
    return `{\n${lines.join(',\n')}\n${pad}}`
  }
  return escapeHtml(JSON.stringify(String(value)))
}

/**
 * @param {unknown} value
 * @returns {string}
 */
function safeStringifyForDisplay(value) {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    try {
      return String(value)
    } catch {
      return '[unprintable]'
    }
  }
}

/**
 * @param {unknown} payload
 * @returns
 *   | { ok: true, working: unknown, expandedPaths: Set<string> }
 *   | { ok: false }
 */
function prepareExpandedTranscriptPayload(payload) {
  const expandedPaths = new Set()
  const cloned = safeClonePayload(payload)
  if (!cloned.ok) {
    return { ok: false }
  }
  const { value: working } = cloned
  if (working !== null && typeof working === 'object' && !Array.isArray(working)) {
    applyJsonStringExpansionRules(/** @type {Record<string, unknown>} */ (working), expandedPaths)
  }
  return { ok: true, working, expandedPaths }
}

/**
 * Format a transcript event payload for display (pretty JSON, expanded JSON-in-string fields).
 * Does not mutate the input `payload`.
 * @param {unknown} payload
 * @returns {string}
 */
export function formatAiDraftTranscriptPayload(payload) {
  const prep = prepareExpandedTranscriptPayload(payload)
  if (!prep.ok) {
    return safeStringifyForDisplay(payload)
  }
  return safeStringifyForDisplay(prep.working)
}

/**
 * Same expansion rules as {@link formatAiDraftTranscriptPayload}, but returns HTML safe for `v-html`.
 * JSON that was decoded from an encoded string at a target path is wrapped in
 * `span.ai-draft-ev-payload-json-expanded` for styling.
 * @param {unknown} payload
 * @returns {string}
 */
export function formatAiDraftTranscriptPayloadHtml(payload) {
  const prep = prepareExpandedTranscriptPayload(payload)
  if (!prep.ok) {
    return escapeHtml(safeStringifyForDisplay(payload))
  }
  const { working, expandedPaths } = prep
  try {
    return prettyValueToHtml(working, '', 0, expandedPaths)
  } catch {
    return escapeHtml(safeStringifyForDisplay(working))
  }
}
