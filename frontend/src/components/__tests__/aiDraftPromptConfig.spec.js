import { describe, expect, it } from 'vitest'
import {
  PROMPT_TYPE_CREATION,
  PROMPT_TYPE_MASTER,
  AI_DRAFT_LIMIT_OPTIONS,
  DEFAULT_AI_DRAFT_MAX_JOBS,
  DEFAULT_AI_DRAFT_MAX_TASKS,
  applyPromptSelection,
  buildPreviewBriefShim,
  canGenerateFromPrompts,
  filterPromptsByType,
  bodyForPromptId,
  limitsFromFirstUserInputEvent,
  parseDraftLimit,
  resumeSessionLabel,
} from '../aiDraftPromptConfig.js'

describe('filterPromptsByType', () => {
  it('returns only rows matching type', () => {
    const prompts = [
      { id: '1', type: PROMPT_TYPE_MASTER, name: 'M' },
      { id: '2', type: PROMPT_TYPE_CREATION, name: 'C' },
    ]
    expect(filterPromptsByType(prompts, PROMPT_TYPE_MASTER)).toEqual([prompts[0]])
  })

  it('returns empty array for non-array input', () => {
    expect(filterPromptsByType(null, PROMPT_TYPE_MASTER)).toEqual([])
  })
})

describe('bodyForPromptId', () => {
  it('returns body when id matches', () => {
    const prompts = [{ id: 'a', body: 'Full text' }]
    expect(bodyForPromptId(prompts, 'a')).toBe('Full text')
  })

  it('returns null for unknown id', () => {
    expect(bodyForPromptId([{ id: 'a', body: 'x' }], 'b')).toBeNull()
  })
})

describe('buildPreviewBriefShim', () => {
  it('prefers trimmed creation text', () => {
    expect(
      buildPreviewBriefShim({ masterText: 'master', creationText: '  create  ' })
    ).toBe('create')
  })

  it('falls back to master when creation empty', () => {
    expect(buildPreviewBriefShim({ masterText: '  only master ', creationText: '' })).toBe(
      'only master'
    )
  })
})

describe('canGenerateFromPrompts', () => {
  it('requires both master and creation non-empty', () => {
    expect(canGenerateFromPrompts({ masterText: 'm', creationText: 'c' })).toBe(true)
    expect(canGenerateFromPrompts({ masterText: '', creationText: 'c' })).toBe(false)
    expect(canGenerateFromPrompts({ masterText: 'm', creationText: '  ' })).toBe(false)
  })
})

describe('resumeSessionLabel', () => {
  it('truncates long brief', () => {
    const brief = 'a'.repeat(80)
    expect(resumeSessionLabel({ brief })).toMatch(/…$/)
  })

  it('shows placeholder when empty', () => {
    expect(resumeSessionLabel({ brief: '' })).toBe('(No prompt text)')
  })

  it('prefers creation_prompt_text over brief', () => {
    expect(
      resumeSessionLabel({
        brief: 'legacy',
        creation_prompt_text: 'From creation column',
      })
    ).toBe('From creation column')
  })
})

describe('parseDraftLimit', () => {
  it('defaults are 2 tasks and 4 jobs', () => {
    expect(DEFAULT_AI_DRAFT_MAX_TASKS).toBe(2)
    expect(DEFAULT_AI_DRAFT_MAX_JOBS).toBe(4)
  })

  it('returns fallback for invalid values', () => {
    expect(parseDraftLimit('0', 2)).toBe(2)
    expect(parseDraftLimit('abc', 4)).toBe(4)
  })

  it('parses integers in range', () => {
    expect(parseDraftLimit('10', 2)).toBe(10)
  })
})

describe('AI_DRAFT_LIMIT_OPTIONS', () => {
  it('has ten options from 1 to 10', () => {
    expect(AI_DRAFT_LIMIT_OPTIONS).toHaveLength(10)
    expect(AI_DRAFT_LIMIT_OPTIONS[0].value).toBe('1')
    expect(AI_DRAFT_LIMIT_OPTIONS[9].value).toBe('10')
  })
})

describe('limitsFromFirstUserInputEvent', () => {
  it('reads max_tasks and max_jobs from earliest user_input', () => {
    expect(
      limitsFromFirstUserInputEvent([
        { kind: 'user_input', sequence: 2, payload: { max_tasks: 5, max_jobs: 3 } },
        { kind: 'user_input', sequence: 1, payload: { max_tasks: 2, max_jobs: 4 } },
      ])
    ).toEqual({ maxTasks: 2, maxJobs: 4 })
  })
})

describe('applyPromptSelection', () => {
  it('prefills body when id set', () => {
    const prompts = [{ id: '1', body: 'Saved body' }]
    expect(applyPromptSelection({ prompts, selectedId: '1', currentText: 'old' })).toEqual({
      text: 'Saved body',
      selectedId: '1',
    })
  })

  it('keeps text when id empty', () => {
    expect(
      applyPromptSelection({ prompts: [], selectedId: '', currentText: 'custom' })
    ).toEqual({ text: 'custom', selectedId: '' })
  })
})
