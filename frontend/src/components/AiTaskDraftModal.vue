<template>
  <div v-if="visible" class="modal-overlay" @click="handleOverlayClick">
    <div class="modal-content ai-draft-modal" @click.stop>
      <div class="ai-draft-header">
        <div>
          <h3>AI Create Campaign</h3>
          <p class="ai-draft-subtitle">
            Draft one or more <code>instagram_post</code> tasks from a brief, review them, then create
            <strong>all tasks and jobs at once</strong> (nothing is saved partially). Duplicates can occur
            if you retry after an unclear network error.
          </p>
        </div>
        <button
          type="button"
          class="btn-secondary"
          :disabled="confirming"
          @click="closeModal"
        >
          Close
        </button>
      </div>

      <div v-if="error" class="error ai-draft-message">
        {{ error }}
      </div>

      <div
        class="ai-draft-layout"
        :class="{ 'ai-draft-layout-split': showTranscriptColumn }"
      >
        <div class="ai-draft-main">
      <div v-if="generating" class="ai-draft-main-overlay" aria-live="polite" aria-busy="true">
        <div class="ai-draft-overlay-card">
          <span class="ai-draft-overlay-spinner" aria-hidden="true"></span>
          <span>AI is generating draft updates...</span>
        </div>
      </div>
      <div v-if="!bundle" class="ai-draft-step">
        <div v-if="draftSessionId" class="card ai-draft-resume-card">
          <h4 class="ai-draft-resume-title">Refine existing draft</h4>
          <div class="form-group">
            <label>Iteration mode</label>
            <select v-model="iterationMode" :disabled="generating">
              <option value="regenerate">Regenerate whole campaign</option>
            </select>
          </div>
          <div class="form-group">
            <label>Follow-up instruction <span class="required">*</span></label>
            <textarea
              v-model="instructionText"
              rows="4"
              :disabled="generating"
              placeholder="Example: keep the same concept but make tone more playful."
            ></textarea>
          </div>
        </div>
        <div class="form-group">
          <label>Brief <span class="required">*</span></label>
          <textarea
            v-model="brief"
            rows="7"
            :disabled="generating"
            placeholder="Describe the campaign: themes, posts, angles, tone, and visual direction."
          ></textarea>
        </div>

        <div v-if="loadingResumeList" class="ai-draft-help">Loading saved drafts…</div>
        <div v-else-if="resumableSessions.length" class="card ai-draft-resume-card">
          <h4 class="ai-draft-resume-title">Resume a saved draft</h4>
          <p class="ai-draft-help ai-draft-resume-hint">
            Drafts are saved on the server for this account and tenant. You can close the browser and come
            back, or recover after a failed create.
          </p>
          <ul class="ai-draft-resume-list">
            <li v-for="s in resumableSessions" :key="s.id">
              <button
                type="button"
                class="btn-secondary ai-draft-resume-btn"
                :disabled="generating"
                @click="resumeSession(s.id)"
              >
                <span class="ai-draft-resume-brief">{{ resumeLabel(s) }}</span>
                <span class="ai-draft-resume-meta">{{ s.item_count }} task(s)</span>
              </button>
            </li>
          </ul>
          <button
            type="button"
            class="ai-draft-start-fresh"
            :disabled="generating"
            @click="clearDraftSessionIdForNewPreview"
          >
            Start a new draft instead (keep saved drafts in the list)
          </button>
        </div>

        <p class="ai-draft-help">
          Tenant-aware brand context is sent automatically for the selected tenant. After you generate,
          edits autosave to your draft session so refresh or a later visit can resume.
        </p>

        <div class="form-actions">
          <button
            type="button"
            class="btn-secondary"
            :disabled="confirming"
            @click="closeModal"
          >
            Cancel
          </button>
          <button
            type="button"
            class="btn-primary"
            :disabled="generating || !trimmedBrief"
            @click="generateDraft"
          >
            {{ generating ? 'Generating…' : 'Generate Draft' }}
          </button>
        </div>
      </div>

      <div v-else class="ai-draft-step">
        <div class="form-actions ai-draft-bundle-actions ai-draft-bundle-actions-top">
          <button
            type="button"
            class="btn-secondary"
            :disabled="confirming || generating || !draftSessionId"
            @click="showFollowUpForm = true"
          >
            Add follow-up instruction
          </button>
          <button
            type="button"
            class="btn-secondary"
            :disabled="confirming || generating || !undoSnapshots.length"
            @click="restoreLatestSnapshot"
          >
            Undo last AI change
          </button>
          <button
            type="button"
            class="btn-secondary"
            :disabled="confirming"
            @click="discardDraft"
          >
            Back
          </button>
          <button
            type="button"
            class="btn-danger"
            :disabled="confirming || generating || !draftSessionId"
            @click="discardSavedDraft"
          >
            Discard saved draft
          </button>
          <button
            type="button"
            class="btn-primary"
            :disabled="confirming || !canConfirm"
            @click="confirmDraft"
          >
            {{ confirming ? 'Creating…' : confirmButtonLabel }}
          </button>
        </div>

        <div v-if="showFollowUpForm && draftSessionId" class="card ai-draft-resume-card">
          <h4 class="ai-draft-resume-title">Refine existing draft</h4>
          <div class="form-group">
            <label>Iteration mode</label>
            <select v-model="iterationMode" :disabled="generating || confirming">
              <option value="regenerate">Regenerate whole campaign</option>
            </select>
          </div>
          <div class="form-group">
            <label>Follow-up instruction <span class="required">*</span></label>
            <textarea
              v-model="instructionText"
              rows="4"
              :disabled="generating || confirming"
              placeholder="Example: keep the same concept but make tone more playful."
            ></textarea>
          </div>
          <div class="form-actions">
            <button
              type="button"
              class="btn-secondary"
              :disabled="generating || confirming"
              @click="showFollowUpForm = false"
            >
              Cancel
            </button>
            <button
              type="button"
              class="btn-primary"
              :disabled="generating || confirming || !instructionText.trim()"
              @click="generateDraft"
            >
              {{ generating ? 'Generating…' : 'Run follow-up' }}
            </button>
          </div>
        </div>

        <div class="ai-draft-summary card">
          <h4>Bundle summary</h4>
          <p class="ai-draft-summary-line">
            <strong>{{ bundle.items.length }}</strong> task(s),
            <strong>{{ totalJobCount }}</strong> job(s) total — confirm creates <em>all</em> or <em>none</em>.
          </p>
          <ul class="ai-draft-summary-list">
            <li v-for="(item, idx) in bundle.items" :key="`sum-${idx}`">
              {{ item.task.name || `Task ${idx + 1}` }} — {{ item.jobs.length }} job(s)
            </li>
          </ul>
          <button
            type="button"
            class="btn-secondary btn-small"
            :disabled="confirming"
            @click="setAllExpanded(!allExpanded)"
          >
            {{ allExpanded ? 'Collapse all' : 'Expand all' }}
          </button>
        </div>

        <div
          v-for="(item, taskIndex) in bundle.items"
          :key="`task-${taskIndex}`"
          class="ai-draft-task-block"
        >
          <button
            type="button"
            class="ai-draft-task-toggle-btn"
            :disabled="confirming"
            @click="toggleExpanded(taskIndex)"
          >
            <span class="ai-draft-task-toggle-title">
              <span class="chevron" :class="{ open: expandedTasks[taskIndex] }">▸</span>
              Task {{ taskIndex + 1 }}: {{ item.task.name || 'Untitled' }}
            </span>
            <span class="ai-draft-task-toggle-meta">{{ item.jobs.length }} job(s)</span>
          </button>

          <div v-if="item.warnings?.length" class="ai-draft-warnings ai-draft-warnings-inline">
            <p class="ai-draft-warnings-title">Warnings (task {{ taskIndex + 1 }})</p>
            <ul>
              <li v-for="warning in item.warnings" :key="warning">{{ warning }}</li>
            </ul>
          </div>

          <div v-show="expandedTasks[taskIndex]" class="ai-draft-task-body">
            <div class="card ai-draft-card">
              <h4>Task {{ taskIndex + 1 }}</h4>
              <div class="form-group">
                <label>Template</label>
                <input :value="item.task.template" disabled />
              </div>
              <div class="form-group">
                <label>Name</label>
                <input v-model="item.task.name" type="text" :disabled="confirming" />
              </div>
              <div class="form-group">
                <label>Theme</label>
                <input
                  v-model="item.task.meta.theme"
                  type="text"
                  :disabled="confirming"
                  placeholder="Enter theme"
                />
              </div>
              <div class="form-group">
                <label>Caption</label>
                <textarea
                  v-model="item.task.post.caption"
                  rows="4"
                  :disabled="confirming"
                  placeholder="Enter caption"
                ></textarea>
              </div>
            </div>

            <div class="ai-draft-jobs">
              <div class="ai-draft-jobs-header">
                <h4>Jobs</h4>
                <button
                  type="button"
                  class="btn-secondary"
                  :disabled="confirming"
                  @click="addJob(taskIndex)"
                >
                  Add Job
                </button>
              </div>

              <div
                v-for="(job, index) in item.jobs"
                :key="`draft-job-${taskIndex}-${index}`"
                class="card ai-draft-job-card"
              >
                <div class="ai-draft-job-header">
                  <h5>Job {{ index + 1 }}</h5>
                  <button
                    type="button"
                    class="btn-danger btn-small"
                    :disabled="confirming || item.jobs.length === 1"
                    @click="removeJob(taskIndex, index)"
                  >
                    Remove
                  </button>
                </div>

                <div class="ai-draft-job-grid">
                  <div class="form-group">
                    <label>Order</label>
                    <input
                      v-model.number="job.order"
                      type="number"
                      min="0"
                      step="1"
                      :disabled="confirming"
                    />
                  </div>
                  <div class="form-group">
                    <label>Generator</label>
                    <select v-model="job.generator" :disabled="confirming">
                      <option value="dalle">dalle</option>
                      <option value="gptimage15">gptimage15</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label>Purpose</label>
                    <input
                      v-model="job.purpose"
                      type="text"
                      :disabled="confirming"
                      placeholder="imagecontent"
                    />
                  </div>
                </div>

                <div class="form-group">
                  <label>Prompt</label>
                  <textarea
                    v-model="job.prompt.prompt"
                    rows="5"
                    :disabled="confirming"
                    placeholder="Enter the image prompt"
                  ></textarea>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
        </div>

        <aside v-if="showTranscriptColumn" class="ai-draft-transcript" aria-label="AI transcript">
          <h4 class="ai-draft-transcript-title">AI transcript</h4>
          <p class="ai-draft-transcript-hint">
            Technical log (prompts and model output) for debugging. Not shown to end users.
          </p>
          <div v-if="!communicationEvents.length && generating" class="ai-draft-transcript-wait">
            Waiting for first events…
          </div>
          <div
            v-for="ev in transcriptEventsNewestFirst"
            :key="`ev-${ev.sequence}`"
            class="ai-draft-transcript-block"
          >
            <div class="ai-draft-transcript-meta">
              <span class="ai-draft-ev-kind">{{ ev.kind }}</span>
              <span class="ai-draft-ev-seq">#{{ ev.sequence }} · {{ formatTranscriptTime(ev.created_at) }}</span>
            </div>
            <pre class="ai-draft-ev-payload" v-html="formatTranscriptPayloadHtml(ev)"></pre>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>

<script>
import { taskService } from '../services/api'
import { formatAiDraftTranscriptPayloadHtml } from './aiDraftTranscriptFormatting.js'

function emptyDraftJob() {
  return {
    generator: 'dalle',
    purpose: 'imagecontent',
    prompt: {
      prompt: '',
    },
    order: 0,
  }
}

function cloneBundle(bundle) {
  return JSON.parse(JSON.stringify(bundle))
}

function formatDraftErrorDetail(detail) {
  if (detail == null) return 'Request failed.'
  if (typeof detail === 'string') return detail
  if (typeof detail === 'object' && detail.error === 'ai_draft_session_limit_reached') {
    return detail.message || 'Maximum open AI drafts reached. Discard old drafts to continue.'
  }
  if (typeof detail === 'object' && detail.error === 'db' && detail.message) {
    return detail.message
  }
  if (typeof detail === 'object' && detail.message) {
    let msg = detail.message
    if (detail.item_index != null && detail.item_index !== undefined) {
      msg = `Task ${Number(detail.item_index) + 1}: ${msg}`
    }
    return msg
  }
  try {
    return JSON.stringify(detail)
  } catch {
    return 'Request failed.'
  }
}

export default {
  name: 'AiTaskDraftModal',
  props: {
    visible: {
      type: Boolean,
      default: false,
    },
    tenantId: {
      type: String,
      default: null,
    },
  },
  emits: ['close', 'created', 'discarded'],
  data() {
    return {
      brief: '',
      bundle: null,
      expandedTasks: {},
      error: null,
      generating: false,
      confirming: false,
      previewAbortController: null,
      draftSessionId: null,
      resumableSessions: [],
      loadingResumeList: false,
      autosaveTimer: null,
      communicationEvents: [],
      previewPollTimer: null,
      previewPollInFlight: false,
      asyncStateVersion: 0,
      iterationMode: 'regenerate',
      instructionText: '',
      undoSnapshots: [],
      showFollowUpForm: false,
    }
  },
  computed: {
    showTranscriptColumn() {
      return (
        this.generating ||
        this.bundle != null ||
        (Array.isArray(this.communicationEvents) && this.communicationEvents.length > 0)
      )
    },
    trimmedBrief() {
      return this.brief.trim()
    },
    totalJobCount() {
      if (!this.bundle?.items?.length) return 0
      return this.bundle.items.reduce((n, item) => n + (item.jobs?.length || 0), 0)
    },
    allExpanded() {
      if (!this.bundle?.items?.length) return false
      return this.bundle.items.every((_, i) => this.expandedTasks[i])
    },
    canConfirm() {
      if (!this.bundle?.items?.length) return false
      return this.bundle.items.every((item) => {
        if (!item.task?.name?.trim()) return false
        if (!Array.isArray(item.jobs) || item.jobs.length === 0) return false
        return item.jobs.every((job) => {
          const promptText = job?.prompt?.prompt
          return Boolean(job.generator && typeof promptText === 'string' && promptText.trim())
        })
      })
    },
    confirmButtonLabel() {
      const n = this.bundle?.items?.length || 0
      if (n <= 1) return 'Create task'
      return `Create ${n} tasks`
    },
    transcriptEventsNewestFirst() {
      if (!Array.isArray(this.communicationEvents)) return []
      return [...this.communicationEvents].sort((a, b) => b.sequence - a.sequence)
    },
  },
  watch: {
    visible(newValue) {
      if (!newValue) {
        this.abortPreviewRequest()
        this.clearAutosaveTimer()
        this.resetState()
      } else {
        this.loadResumableSessions()
      }
    },
    brief() {
      this.scheduleAutosave()
    },
    bundle: {
      deep: true,
      handler() {
        this.scheduleAutosave()
      },
    },
    tenantId(newTenantId, oldTenantId) {
      if (!this.visible || !oldTenantId || newTenantId === oldTenantId) return
      const hadDraftWork = Boolean(this.bundle) || Boolean(this.trimmedBrief)
      this.abortPreviewRequest()
      this.stopPreviewPolling()
      this.clearAutosaveTimer()
      this.resetState()
      this.$emit('close')
      if (hadDraftWork) {
        this.$emit('discarded', 'Tenant changed. AI draft bundle was discarded.')
      }
    },
  },
  beforeUnmount() {
    this.stopPreviewPolling()
  },
  methods: {
    handleOverlayClick() {
      if (this.confirming) return
      this.closeModal()
    },
    closeModal() {
      if (this.confirming) return
      this.abortPreviewRequest()
      this.stopPreviewPolling()
      this.clearAutosaveTimer()
      this.resetState()
      this.$emit('close')
    },
    discardDraft() {
      if (this.confirming) return
      this.bundle = null
      this.expandedTasks = {}
      this.error = null
      this.communicationEvents = []
      this.showFollowUpForm = false
    },
    clearDraftSessionIdForNewPreview() {
      this.draftSessionId = null
    },
    clearAutosaveTimer() {
      if (this.autosaveTimer) {
        clearTimeout(this.autosaveTimer)
        this.autosaveTimer = null
      }
    },
    scheduleAutosave() {
      if (!this.draftSessionId || !this.bundle?.items?.length || this.confirming || this.generating) {
        return
      }
      this.clearAutosaveTimer()
      this.autosaveTimer = setTimeout(() => {
        this.autosaveTimer = null
        this.flushAutosave()
      }, 750)
    },
    async flushAutosave(options = {}) {
      const { force = false } = options
      if (!this.draftSessionId || !this.bundle?.items?.length || this.confirming) {
        return
      }
      if (!force && this.generating) {
        return
      }
      try {
        const body = {
          brief: this.brief,
          items: this.sanitizeBundleForConfirm().items,
        }
        await taskService.patchAiDraftSession(this.draftSessionId, body)
      } catch {
        /* Autosave is best-effort; avoid noisy toasts */
      }
    },
    async loadResumableSessions() {
      if (!this.tenantId) {
        this.resumableSessions = []
        return
      }
      this.loadingResumeList = true
      try {
        this.resumableSessions = (await taskService.listAiDraftSessions()) || []
      } catch {
        this.resumableSessions = []
      } finally {
        this.loadingResumeList = false
      }
    },
    resumeLabel(sessionRow) {
      const t = (sessionRow.brief || '').trim().replace(/\s+/g, ' ')
      if (!t) return '(No brief text)'
      return t.length > 72 ? `${t.slice(0, 72)}…` : t
    },
    async resumeSession(sessionId) {
      if (!this.tenantId || this.generating) return
      this.error = null
      this.generating = true
      let leaveGeneratingForPoll = false
      const stateVersion = this.asyncStateVersion
      try {
        const data = await taskService.getAiDraftSession(sessionId)
        if (stateVersion !== this.asyncStateVersion) return
        this.draftSessionId = data.id
        this.brief = data.brief || ''
        this.setCommunicationEventsFromApi(data.communication_events)
        this.undoSnapshots = Array.isArray(data.undo_snapshots) ? data.undo_snapshots : []
        if (data.preview_status === 'running') {
          this.bundle = null
          this.error = null
          this.startPreviewPolling()
          leaveGeneratingForPoll = true
          await this.loadResumableSessions()
          return
        }
        const items = (data.items || []).map((item, i) => this.normalizeItem(item, i))
        this.bundle = { items }
        this.expandedTasks = {}
        this.showFollowUpForm = false
        if (data.last_error) {
          this.error = formatDraftErrorDetail(data.last_error)
        }
        await this.loadResumableSessions()
      } catch (error) {
        if (error?.response?.status === 401) {
          this.handleAuthLoss()
          return
        }
        this.error =
          formatDraftErrorDetail(error?.response?.data?.detail) ||
          error?.message ||
          'Could not load saved draft.'
      } finally {
        if (!leaveGeneratingForPoll) {
          this.generating = false
        }
      }
    },
    async discardSavedDraft() {
      if (!this.draftSessionId || this.confirming || this.generating) return
      const confirmed = window.confirm(
        'Discard this saved draft? This action cannot be undone.'
      )
      if (!confirmed) return
      const id = this.draftSessionId
      this.asyncStateVersion += 1
      this.abortPreviewRequest()
      this.stopPreviewPolling()
      try {
        await taskService.deleteAiDraftSession(id)
      } catch (error) {
        if (error?.response?.status === 401) {
          this.handleAuthLoss()
          return
        }
        this.error =
          formatDraftErrorDetail(error?.response?.data?.detail) ||
          error?.message ||
          'Could not discard draft.'
        return
      }
      this.draftSessionId = null
      this.bundle = null
      this.expandedTasks = {}
      this.error = null
      this.communicationEvents = []
      this.undoSnapshots = []
      this.showFollowUpForm = false
      this.instructionText = ''
      this.iterationMode = 'regenerate'
      await this.loadResumableSessions()
    },
    toggleExpanded(taskIndex) {
      this.expandedTasks = {
        ...this.expandedTasks,
        [taskIndex]: !this.expandedTasks[taskIndex],
      }
    },
    setAllExpanded(value) {
      const next = {}
      if (this.bundle?.items) {
        this.bundle.items.forEach((_, i) => {
          next[i] = value
        })
      }
      this.expandedTasks = next
    },
    abortPreviewRequest() {
      if (this.previewAbortController) {
        this.previewAbortController.abort()
        this.previewAbortController = null
      }
    },
    stopPreviewPolling() {
      if (this.previewPollTimer) {
        clearTimeout(this.previewPollTimer)
        this.previewPollTimer = null
      }
      this.previewPollInFlight = false
    },
    scheduleNextPreviewPoll(delayMs = 900) {
      if (this.previewPollTimer || !this.draftSessionId || !this.generating) {
        return
      }
      this.previewPollTimer = setTimeout(async () => {
        this.previewPollTimer = null
        await this.pollDraftSession()
        if (this.generating && this.draftSessionId) {
          this.scheduleNextPreviewPoll()
        }
      }, delayMs)
    },
    startPreviewPolling() {
      this.stopPreviewPolling()
      this.scheduleNextPreviewPoll(0)
    },
    setCommunicationEventsFromApi(events) {
      if (!Array.isArray(events)) {
        this.communicationEvents = []
        return
      }
      this.communicationEvents = [...events].sort((a, b) => a.sequence - b.sequence)
    },
    formatTranscriptPayloadHtml(ev) {
      return formatAiDraftTranscriptPayloadHtml(ev?.payload)
    },
    formatTranscriptTime(value) {
      if (!value) return '-'
      const d = new Date(value)
      if (Number.isNaN(d.getTime())) return '-'
      return d.toLocaleString()
    },
    async pollDraftSession() {
      if (!this.draftSessionId || !this.tenantId || this.previewPollInFlight) return
      this.previewPollInFlight = true
      const sessionId = this.draftSessionId
      const stateVersion = this.asyncStateVersion
      try {
        const data = await taskService.getAiDraftSession(sessionId)
        if (stateVersion !== this.asyncStateVersion || sessionId !== this.draftSessionId) {
          return
        }
        this.setCommunicationEventsFromApi(data.communication_events)
        if (data.preview_status === 'running') {
          return
        }
        this.stopPreviewPolling()
        this.generating = false
        this.previewAbortController = null
        if (data.preview_status === 'failed') {
          if (!this.bundle?.items?.length) {
            this.bundle = null
          }
          this.error =
            formatDraftErrorDetail(data.last_error) || 'AI preview failed.'
          this.undoSnapshots = Array.isArray(data.undo_snapshots) ? data.undo_snapshots : []
          this.showFollowUpForm = false
          await this.loadResumableSessions()
          return
        }
        this.error = null
        const items = (data.items || []).map((item, i) => this.normalizeItem(item, i))
        this.bundle = { items }
        this.undoSnapshots = Array.isArray(data.undo_snapshots) ? data.undo_snapshots : []
        this.expandedTasks = {}
        this.showFollowUpForm = false
        await this.loadResumableSessions()
      } catch (error) {
        if (error?.response?.status === 401) {
          this.stopPreviewPolling()
          this.generating = false
          this.handleAuthLoss()
          return
        }
        /* Keep polling on transient errors */
      } finally {
        this.previewPollInFlight = false
      }
    },
    normalizeItem(rawItem, index) {
      const item = cloneBundle(rawItem)
      item.task = item.task || {}
      item.task.meta = item.task.meta || {}
      if (item.task.meta.theme === undefined) {
        item.task.meta.theme = ''
      }
      item.task.post = item.task.post || {}
      if (item.task.post.caption === undefined || item.task.post.caption === null) {
        item.task.post.caption = ''
      }
      item.jobs = (item.jobs || []).map((job, j) => ({
        ...emptyDraftJob(),
        ...job,
        order: job.order ?? j,
        prompt: {
          ...(job && typeof job.prompt === 'object' ? job.prompt : {}),
          prompt: job?.prompt?.prompt || '',
        },
      }))
      item.warnings = item.warnings || []
      return item
    },
    sanitizeBundleForConfirm() {
      const next = cloneBundle(this.bundle)
      next.items = next.items.map((item, taskIndex) => {
        const jobs = (item.jobs || []).map((job, index) => {
          const normalizedOrder = Number.isFinite(job.order)
            ? Math.max(0, Math.floor(job.order))
            : index
          return {
            ...job,
            order: normalizedOrder,
            prompt: {
              ...(job && typeof job.prompt === 'object' ? job.prompt : {}),
              prompt: job?.prompt?.prompt || '',
            },
          }
        })
        return { ...item, jobs }
      })
      return next
    },
    isRequestCanceled(error) {
      return error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError'
    },
    handleAuthLoss() {
      this.stopPreviewPolling()
      this.clearAutosaveTimer()
      this.resetState()
      this.$emit('close')
      this.$emit('discarded', 'Session expired. AI draft was closed.')
    },
    async generateDraft() {
      if (!this.trimmedBrief) {
        this.error = 'Enter a brief first.'
        return
      }
      if (!this.tenantId) {
        this.error = 'Select a tenant first.'
        return
      }

      this.error = null
      this.communicationEvents = []
      let keepGenerating = false
      let controller = null
      const stateVersion = this.asyncStateVersion

      try {
        const payload = { brief: this.trimmedBrief }
        if (this.draftSessionId) {
          const followUpInstruction = this.instructionText.trim()
          if (!followUpInstruction) {
            this.error = 'Enter a follow-up instruction first.'
            return
          }
          payload.draft_session_id = this.draftSessionId
          payload.iteration_mode = this.iterationMode
          payload.instruction_text = followUpInstruction
          payload.target_scope = 'campaign'

          // Prevent lost updates: flush any pending local edits before iteration snapshotting.
          this.clearAutosaveTimer()
          await this.flushAutosave({ force: true })
        }
        this.generating = true
        controller = new AbortController()
        this.previewAbortController = controller
        const data = await taskService.previewAiTaskDraft(payload, {
          signal: controller.signal,
        })
        if (stateVersion !== this.asyncStateVersion) return
        if (data.draft_session_id) {
          this.draftSessionId = data.draft_session_id
        }
        this.setCommunicationEventsFromApi(data.communication_events)
        this.undoSnapshots = Array.isArray(data.undo_snapshots) ? data.undo_snapshots : this.undoSnapshots

        if (data.preview_status === 'running') {
          keepGenerating = true
          this.startPreviewPolling()
          this.showFollowUpForm = false
          await this.loadResumableSessions()
          return
        }

        if (data.preview_status === 'failed') {
          if (!this.bundle?.items?.length) {
            this.bundle = null
          }
          this.error =
            formatDraftErrorDetail(data.last_error) || 'AI preview failed.'
          this.showFollowUpForm = false
          await this.loadResumableSessions()
          return
        }

        const items = (data.items || []).map((item, i) => this.normalizeItem(item, i))
        this.bundle = { items }
        this.undoSnapshots = Array.isArray(data.undo_snapshots) ? data.undo_snapshots : this.undoSnapshots
        this.expandedTasks = {}
        this.showFollowUpForm = false
        await this.loadResumableSessions()
      } catch (error) {
        if (this.isRequestCanceled(error)) return
        if (error?.response?.status === 401) {
          this.handleAuthLoss()
          return
        }
        this.error =
          formatDraftErrorDetail(error?.response?.data?.detail) ||
          error?.message ||
          'Failed to generate AI draft.'
      } finally {
        if (controller && this.previewAbortController === controller) {
          this.previewAbortController = null
        }
        if (!keepGenerating) {
          this.generating = false
        }
      }
    },
    addJob(taskIndex) {
      if (!this.bundle?.items?.[taskIndex] || this.confirming) return
      const item = this.bundle.items[taskIndex]
      item.jobs.push({
        ...emptyDraftJob(),
        order: item.jobs.length,
      })
    },
    removeJob(taskIndex, jobIndex) {
      const item = this.bundle?.items?.[taskIndex]
      if (!item || this.confirming || item.jobs.length === 1) return
      item.jobs.splice(jobIndex, 1)
    },
    async confirmDraft() {
      if (!this.bundle || !this.canConfirm || this.confirming) return

      this.error = null
      this.confirming = true
      try {
        const body = this.sanitizeBundleForConfirm()
        if (this.draftSessionId) {
          body.draft_session_id = this.draftSessionId
        }
        const result = await taskService.confirmAiTaskDraft(body)
        this.$emit('created', result)
        this.resetState()
        this.$emit('close')
      } catch (error) {
        if (error?.response?.status === 401) {
          this.handleAuthLoss()
          return
        }
        this.error =
          formatDraftErrorDetail(error?.response?.data?.detail) ||
          error?.message ||
          'Failed to create tasks from AI draft.'
      } finally {
        this.confirming = false
      }
    },
    async restoreLatestSnapshot() {
      if (!this.draftSessionId || !this.undoSnapshots.length || this.confirming || this.generating) return
      const latest = this.undoSnapshots[0]
      try {
        const data = await taskService.restoreAiDraftSessionSnapshot(this.draftSessionId, latest.id)
        this.error = null
        this.setCommunicationEventsFromApi(data.communication_events)
        this.undoSnapshots = Array.isArray(data.undo_snapshots) ? data.undo_snapshots : []
        const items = (data.items || []).map((item, i) => this.normalizeItem(item, i))
        this.bundle = { items }
      } catch (error) {
        this.error =
          formatDraftErrorDetail(error?.response?.data?.detail) ||
          error?.message ||
          'Failed to restore previous revision.'
      }
    },
    resetState() {
      this.asyncStateVersion += 1
      this.stopPreviewPolling()
      this.brief = ''
      this.bundle = null
      this.expandedTasks = {}
      this.error = null
      this.generating = false
      this.confirming = false
      this.previewAbortController = null
      this.previewPollInFlight = false
      this.draftSessionId = null
      this.resumableSessions = []
      this.communicationEvents = []
      this.iterationMode = 'regenerate'
      this.instructionText = ''
      this.undoSnapshots = []
      this.showFollowUpForm = false
    },
  },
}
</script>

<style scoped>
.ai-draft-modal {
  width: min(96vw, 96rem);
  max-width: 96rem;
}

.ai-draft-layout {
  display: block;
}

.ai-draft-main {
  position: relative;
}

.ai-draft-layout-split {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(22rem, 34rem);
  gap: 1.25rem;
  align-items: start;
}

.ai-draft-main-overlay {
  position: absolute;
  inset: 0;
  z-index: 20;
  background: rgba(15, 23, 42, 0.18);
  backdrop-filter: blur(1px);
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: all;
}

.ai-draft-overlay-card {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.7rem 1rem;
  border-radius: 0.6rem;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #0f172a;
  font-weight: 600;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
}

.ai-draft-overlay-spinner {
  width: 0.95rem;
  height: 0.95rem;
  border: 2px solid #bfdbfe;
  border-top-color: #2563eb;
  border-radius: 9999px;
  animation: ai-draft-spin 0.8s linear infinite;
}

@keyframes ai-draft-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 960px) {
  .ai-draft-layout-split {
    grid-template-columns: 1fr;
  }
}

.ai-draft-transcript {
  border: 1px solid var(--color-border, #d4d4d8);
  border-radius: 8px;
  padding: 0.75rem 0.9rem;
  background: var(--color-surface-muted, #f4f4f5);
  max-height: min(70vh, 36rem);
  overflow: auto;
  font-size: var(--text-sm, 0.875rem);
}

.ai-draft-transcript-title {
  margin: 0 0 0.35rem;
  font-size: var(--text-base);
}

.ai-draft-transcript-hint {
  margin: 0 0 0.75rem;
  color: var(--color-text-muted);
  font-size: 0.75rem;
}

.ai-draft-transcript-wait {
  color: var(--color-text-muted);
  font-size: 0.8rem;
}

.ai-draft-transcript-block {
  margin-bottom: 0.75rem;
}

.ai-draft-transcript-meta {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.ai-draft-ev-kind {
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.ai-draft-ev-seq {
  font-size: 0.65rem;
  color: var(--color-text-muted);
}

.ai-draft-ev-payload {
  margin: 0;
  padding: 0.5rem;
  background: #1e1e1e;
  color: #e4e4e7;
  border-radius: 4px;
  font-size: 0.7rem;
  line-height: 1.35;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 12rem;
  overflow: auto;
}

/* Decoded JSON (was a JSON string before formatting) — highlight only that subtree */
.ai-draft-ev-payload :deep(.ai-draft-ev-payload-json-expanded) {
  color: var(--color-warning, #f59e0b);
}

.ai-draft-resume-card {
  padding: 1rem 1.25rem;
  margin-bottom: 0.5rem;
}

.ai-draft-resume-title {
  margin: 0 0 0.35rem;
  font-size: var(--text-base);
}

.ai-draft-resume-hint {
  margin-top: 0;
}

.ai-draft-resume-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.ai-draft-resume-btn {
  width: 100%;
  text-align: left;
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0.5rem;
}

.ai-draft-resume-brief {
  flex: 1 1 12rem;
}

.ai-draft-resume-meta {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.ai-draft-start-fresh {
  margin-top: 0.75rem;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  color: var(--color-primary, #2563eb);
  text-decoration: underline;
  font: inherit;
}

.ai-draft-start-fresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ai-draft-bundle-actions {
  flex-wrap: wrap;
  gap: 0.5rem;
}

.ai-draft-bundle-actions-top {
  margin-bottom: 0.5rem;
}

.ai-draft-bundle-actions .btn-secondary {
  background: #eef2ff;
  border-color: #c7d2fe;
  color: #3730a3;
}

.ai-draft-bundle-actions .btn-secondary:hover:not(:disabled) {
  background: #e0e7ff;
}

.ai-draft-bundle-actions .btn-danger {
  background: #fef2f2;
  border-color: #fecaca;
  color: #b91c1c;
}

.ai-draft-bundle-actions .btn-danger:hover:not(:disabled) {
  background: #fee2e2;
}

.ai-draft-bundle-actions .btn-primary {
  background: #2563eb;
  border-color: #1d4ed8;
  color: #ffffff;
}

.ai-draft-bundle-actions .btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
}

.ai-draft-bundle-actions .btn-secondary:disabled,
.ai-draft-bundle-actions .btn-danger:disabled,
.ai-draft-bundle-actions .btn-primary:disabled {
  background: #e5e7eb;
  border-color: #d1d5db;
  color: #9ca3af;
  cursor: not-allowed;
}

.ai-draft-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

.ai-draft-subtitle {
  margin: 0.35rem 0 0;
  color: var(--color-text-muted);
  font-size: var(--text-sm);
}

.ai-draft-subtitle code {
  font-size: 0.9em;
}

.ai-draft-step {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.ai-draft-help {
  margin: 0;
  color: var(--color-text-muted);
  font-size: var(--text-sm);
}

.ai-draft-summary {
  padding: 1.25rem;
}

.ai-draft-summary-line {
  margin: 0 0 0.75rem;
}

.ai-draft-summary-list {
  margin: 0 0 1rem;
  padding-left: 1.25rem;
}

.ai-draft-task-block {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.ai-draft-task-toggle-btn {
  width: 100%;
  text-align: left;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  background: var(--color-bg-muted, rgba(0, 0, 0, 0.04));
  border: 1px solid var(--color-border, rgba(0, 0, 0, 0.08));
  border-radius: var(--radius-md);
  font: inherit;
  color: inherit;
}

.ai-draft-task-toggle-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.ai-draft-task-toggle-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: var(--font-semibold);
}

.ai-draft-task-toggle-meta {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.chevron {
  display: inline-block;
  transition: transform 0.15s ease;
}

.chevron.open {
  transform: rotate(90deg);
}

.ai-draft-task-body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.ai-draft-card,
.ai-draft-job-card {
  padding: 1.25rem;
}

.ai-draft-jobs {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.ai-draft-jobs-header,
.ai-draft-job-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}

.ai-draft-job-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.ai-draft-message {
  margin-bottom: 1rem;
}

.ai-draft-warnings {
  border: 1px solid rgba(245, 158, 11, 0.22);
  background: var(--color-warning-muted);
  color: var(--color-warning-text);
  border-radius: var(--radius-md);
  padding: 1rem 1.25rem;
}

.ai-draft-warnings-inline {
  margin-top: 0.25rem;
}

.ai-draft-warnings-title {
  margin: 0 0 0.5rem;
  font-weight: var(--font-semibold);
}

.ai-draft-warnings ul {
  margin: 0;
  padding-left: 1.25rem;
}

@media (max-width: 768px) {
  .ai-draft-header,
  .ai-draft-jobs-header,
  .ai-draft-job-header {
    flex-direction: column;
    align-items: stretch;
  }

  .ai-draft-job-grid {
    grid-template-columns: 1fr;
  }
}
</style>
