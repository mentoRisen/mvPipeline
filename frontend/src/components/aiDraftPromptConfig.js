/** Shared AI draft modal prompt/model configuration (GUI + tests). */

export const PROMPT_TYPE_MASTER = 'master-prompt'
export const PROMPT_TYPE_CREATION = 'task-creation'

export const AI_DRAFT_MODEL_OPTIONS = [
  { value: '5.1', label: 'GPT 5.1' },
  { value: '5.4', label: 'GPT 5.4' },
  { value: '5.5', label: 'GPT 5.5' },
]

export const AI_DRAFT_REASONING_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
]

export const DEFAULT_AI_DRAFT_MODEL = '5.1'
export const DEFAULT_AI_DRAFT_REASONING = 'none'

export const DEFAULT_AI_DRAFT_MAX_TASKS = 2
export const DEFAULT_AI_DRAFT_MAX_JOBS = 4

/** Select options for Max Tasks / Max Jobs (integers 1–10). */
export const AI_DRAFT_LIMIT_OPTIONS = Array.from({ length: 10 }, (_, i) => {
  const value = String(i + 1)
  return { value, label: value }
})

/**
 * @param {unknown} value
 * @param {number} fallback
 * @returns {number}
 */
export function parseDraftLimit(value, fallback) {
  const n = parseInt(String(value), 10)
  if (!Number.isFinite(n) || n < 1 || n > 10) return fallback
  return n
}

/**
 * @param {Array<{ kind?: string, sequence?: number, payload?: object }>} events
 * @returns {{ maxTasks: number, maxJobs: number } | null}
 */
export function limitsFromFirstUserInputEvent(events) {
  if (!Array.isArray(events)) return null
  const ordered = [...events].sort(
    (a, b) => Number(a?.sequence ?? 0) - Number(b?.sequence ?? 0)
  )
  const first = ordered.find((e) => e && e.kind === 'user_input')
  if (!first?.payload || typeof first.payload !== 'object') return null
  const p = first.payload
  return {
    maxTasks: parseDraftLimit(p.max_tasks, DEFAULT_AI_DRAFT_MAX_TASKS),
    maxJobs: parseDraftLimit(p.max_jobs, DEFAULT_AI_DRAFT_MAX_JOBS),
  }
}

export const CUSTOM_PROMPT_SELECT_VALUE = ''

/**
 * @param {Array<{ type?: string }>} prompts
 * @param {string} type
 */
export function filterPromptsByType(prompts, type) {
  if (!Array.isArray(prompts)) return []
  return prompts.filter((p) => p && p.type === type)
}

/**
 * @param {Array<{ id?: string, body?: string }>} prompts
 * @param {string} id
 */
export function bodyForPromptId(prompts, id) {
  if (!id || !Array.isArray(prompts)) return null
  const row = prompts.find((p) => p && String(p.id) === String(id))
  if (!row) return null
  return typeof row.body === 'string' ? row.body : null
}

/**
 * @param {{ prompts: Array<{ id?: string, body?: string }>, selectedId: string, currentText: string }} params
 */
export function applyPromptSelection({ prompts, selectedId, currentText }) {
  if (!selectedId) return { text: currentText, selectedId: '' }
  const body = bodyForPromptId(prompts, selectedId)
  if (body == null) return { text: currentText, selectedId }
  return { text: body, selectedId }
}

/**
 * Until the preview API accepts split prompt fields, send creation text as `brief`.
 * @param {{ masterText?: string, creationText?: string }} params
 * @returns {string}
 */
export function buildPreviewBriefShim({ masterText = '', creationText = '' } = {}) {
  const creation = String(creationText).trim()
  if (creation) return creation
  return String(masterText).trim()
}

/**
 * @param {{ masterText?: string, creationText?: string }} params
 */
export function canGenerateFromPrompts({ masterText = '', creationText = '' } = {}) {
  return Boolean(String(creationText).trim()) && Boolean(String(masterText).trim())
}

/**
 * Label for resume list from stored session brief (legacy) or creation excerpt.
 * @param {{ brief?: string }} sessionRow
 */
export function resumeSessionLabel(sessionRow) {
  const t = String(
    sessionRow?.creation_prompt_text || sessionRow?.brief || ''
  )
    .trim()
    .replace(/\s+/g, ' ')
  if (!t) return '(No prompt text)'
  return t.length > 72 ? `${t.slice(0, 72)}…` : t
}
