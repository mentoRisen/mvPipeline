import { describe, expect, it } from 'vitest'
import {
  AI_DRAFT_TRANSCRIPT_JSON_EXPANSION_RULES,
  formatAiDraftTranscriptPayload,
  formatAiDraftTranscriptPayloadHtml,
} from '../aiDraftTranscriptFormatting.js'

describe('formatAiDraftTranscriptPayload', () => {
  it('exports a stable expansion rule list', () => {
    expect(AI_DRAFT_TRANSCRIPT_JSON_EXPANSION_RULES.length).toBe(3)
    expect(AI_DRAFT_TRANSCRIPT_JSON_EXPANSION_RULES.map((r) => `${r.target}:${r.field}`)).toEqual([
      'top:content',
      'top:brief',
      'messagesItem:content',
    ])
  })

  it('expands top-level content JSON string (happy path)', () => {
    const payload = {
      content: '{"a":1,"b":{"c":2}}',
      other: 'keep',
    }
    const out = formatAiDraftTranscriptPayload(payload)
    expect(out).toContain('"a": 1')
    expect(out).toContain('"c": 2')
    expect(out).toContain('"other": "keep"')
  })

  it('expands top-level brief JSON string', () => {
    const payload = { brief: '["x","y"]' }
    const out = formatAiDraftTranscriptPayload(payload)
    const parsed = JSON.parse(out)
    expect(parsed.brief).toEqual(['x', 'y'])
  })

  it('expands messages[].content for each object entry', () => {
    const payload = {
      messages: [
        { role: 'user', content: '{"text":"hi"}' },
        { role: 'assistant', content: '[1,2,3]' },
      ],
    }
    const out = formatAiDraftTranscriptPayload(payload)
    const parsed = JSON.parse(out)
    expect(parsed.messages[0].content).toEqual({ text: 'hi' })
    expect(parsed.messages[1].content).toEqual([1, 2, 3])
  })

  it('leaves mixed non-object messages elements unchanged', () => {
    const payload = {
      messages: ['plain', null, { content: '{"k":true}' }, 42],
    }
    const out = formatAiDraftTranscriptPayload(payload)
    const parsed = JSON.parse(out)
    expect(parsed.messages[0]).toBe('plain')
    expect(parsed.messages[1]).toBeNull()
    expect(parsed.messages[2].content).toEqual({ k: true })
    expect(parsed.messages[3]).toBe(42)
  })

  it('no-ops when messages is missing, wrong type, or empty', () => {
    expect(() => formatAiDraftTranscriptPayload({ a: 1 })).not.toThrow()
    expect(JSON.parse(formatAiDraftTranscriptPayload({ a: 1 }))).toEqual({ a: 1 })

    const wrongType = { messages: 'not-array', x: 1 }
    expect(JSON.parse(formatAiDraftTranscriptPayload(wrongType))).toEqual(wrongType)

    const empty = { messages: [] }
    expect(JSON.parse(formatAiDraftTranscriptPayload(empty))).toEqual(empty)
  })

  it('parses JSON scalar strings at target fields', () => {
    const payload = { content: '"hello"', brief: '42' }
    const parsed = JSON.parse(formatAiDraftTranscriptPayload(payload))
    expect(parsed.content).toBe('hello')
    expect(parsed.brief).toBe(42)
  })

  it('retains invalid JSON strings without throwing', () => {
    const payload = { content: '{not json', brief: 'also { bad' }
    const out = formatAiDraftTranscriptPayload(payload)
    expect(out).toContain('{not json')
    expect(out).toContain('also { bad')
  })

  it('does not mutate the original payload', () => {
    const payload = {
      content: '{"nested":true}',
      messages: [{ content: '{"m":1}' }],
    }
    const snapshot = JSON.stringify(payload)
    formatAiDraftTranscriptPayload(payload)
    expect(JSON.stringify(payload)).toBe(snapshot)
  })

  it('handles null, primitives, and arrays; top-level arrays skip object expansion rules', () => {
    expect(formatAiDraftTranscriptPayload(null)).toBe(JSON.stringify(null, null, 2))
    expect(formatAiDraftTranscriptPayload(3)).toBe(JSON.stringify(3, null, 2))
    expect(formatAiDraftTranscriptPayload('x')).toBe(JSON.stringify('x', null, 2))
    const arr = [1, { content: '{"a":1}' }]
    const parsed = JSON.parse(formatAiDraftTranscriptPayload(arr))
    expect(parsed[1].content).toBe('{"a":1}')
  })

  it('falls back when clone fails (e.g. circular reference)', () => {
    const a = { x: 1 }
    a.self = a
    const out = formatAiDraftTranscriptPayload(a)
    expect(typeof out).toBe('string')
    expect(out.length).toBeGreaterThan(0)
  })
})

describe('formatAiDraftTranscriptPayloadHtml', () => {
  it('wraps only successfully decoded JSON-string fields in the expanded span', () => {
    const payload = {
      content: '{"a":1}',
      brief: 'not valid json {',
      other: 1,
    }
    const html = formatAiDraftTranscriptPayloadHtml(payload)
    expect(html).toContain('ai-draft-ev-payload-json-expanded')
    expect(html).toContain('&quot;a&quot;: 1')
    expect(html).toContain('&quot;brief&quot;: &quot;not valid json {&quot;')
  })

  it('marks each expanded messages[].content', () => {
    const payload = {
      messages: [{ content: 'true' }, { content: 'no' }],
    }
    const html = formatAiDraftTranscriptPayloadHtml(payload)
    const spans = html.split('ai-draft-ev-payload-json-expanded').length - 1
    expect(spans).toBe(1)
    expect(html).toContain('true')
    expect(html).toContain('&quot;no&quot;')
  })

  it('escapes HTML in string values', () => {
    const payload = { plain: '<script>x</script>' }
    const html = formatAiDraftTranscriptPayloadHtml(payload)
    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;script&gt;')
  })
})
