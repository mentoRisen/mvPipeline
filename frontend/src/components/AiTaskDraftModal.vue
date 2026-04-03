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

      <div v-if="!bundle" class="ai-draft-step">
        <div class="form-group">
          <label>Brief <span class="required">*</span></label>
          <textarea
            v-model="brief"
            rows="7"
            :disabled="generating"
            placeholder="Describe the campaign: themes, posts, angles, tone, and visual direction."
          ></textarea>
        </div>

        <p class="ai-draft-help">
          Tenant-aware brand context is sent automatically for the selected tenant. Drafts stay in this
          browser session only—refresh or tenant change discards them.
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

        <div class="form-actions">
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
            class="btn-primary"
            :disabled="confirming || !canConfirm"
            @click="confirmDraft"
          >
            {{ confirming ? 'Creating…' : confirmButtonLabel }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { taskService } from '../services/api'

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
    }
  },
  computed: {
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
  },
  watch: {
    visible(newValue) {
      if (!newValue) {
        this.abortPreviewRequest()
        this.resetState()
      }
    },
    tenantId(newTenantId, oldTenantId) {
      if (!this.visible || !oldTenantId || newTenantId === oldTenantId) return
      const hadDraftWork = Boolean(this.bundle) || Boolean(this.trimmedBrief)
      this.abortPreviewRequest()
      this.resetState()
      this.$emit('close')
      if (hadDraftWork) {
        this.$emit('discarded', 'Tenant changed. AI draft bundle was discarded.')
      }
    },
  },
  methods: {
    handleOverlayClick() {
      if (this.confirming) return
      this.closeModal()
    },
    closeModal() {
      if (this.confirming) return
      this.abortPreviewRequest()
      this.resetState()
      this.$emit('close')
    },
    discardDraft() {
      if (this.confirming) return
      this.bundle = null
      this.expandedTasks = {}
      this.error = null
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
      this.generating = true
      const controller = new AbortController()
      this.previewAbortController = controller

      try {
        const data = await taskService.previewAiTaskDraft(
          { brief: this.trimmedBrief },
          { signal: controller.signal }
        )
        const items = (data.items || []).map((item, i) => this.normalizeItem(item, i))
        this.bundle = { items }
        this.expandedTasks = {}
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
        if (this.previewAbortController === controller) {
          this.previewAbortController = null
        }
        this.generating = false
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
        const result = await taskService.confirmAiTaskDraft(this.sanitizeBundleForConfirm())
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
    resetState() {
      this.brief = ''
      this.bundle = null
      this.expandedTasks = {}
      this.error = null
      this.generating = false
      this.confirming = false
      this.previewAbortController = null
    },
  },
}
</script>

<style scoped>
.ai-draft-modal {
  max-width: 56rem;
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
