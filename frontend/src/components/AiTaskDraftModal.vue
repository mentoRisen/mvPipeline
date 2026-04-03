<template>
  <div v-if="visible" class="modal-overlay" @click="handleOverlayClick">
    <div class="modal-content ai-draft-modal" @click.stop>
      <div class="ai-draft-header">
        <div>
          <h3>AI Create Task</h3>
          <p class="ai-draft-subtitle">
            Draft one `instagram_post` task, review it, then create it as normal task and job records.
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

      <div v-if="!draft" class="ai-draft-step">
        <div class="form-group">
          <label>Brief <span class="required">*</span></label>
          <textarea
            v-model="brief"
            rows="7"
            :disabled="generating"
            placeholder="Describe the post you want to draft, the theme, tone, and visual direction."
          ></textarea>
        </div>

        <p class="ai-draft-help">
          Tenant-aware brand context is included automatically from the selected tenant. No draft is saved until you confirm.
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
        <div v-if="draft.warnings?.length" class="ai-draft-warnings">
          <p class="ai-draft-warnings-title">Warnings</p>
          <ul>
            <li v-for="warning in draft.warnings" :key="warning">{{ warning }}</li>
          </ul>
        </div>

        <div class="card ai-draft-card">
          <h4>Task</h4>
          <div class="form-group">
            <label>Template</label>
            <input :value="draft.task.template" disabled />
          </div>
          <div class="form-group">
            <label>Name</label>
            <input v-model="draft.task.name" type="text" :disabled="confirming" />
          </div>
          <div class="form-group">
            <label>Theme</label>
            <input
              v-model="draft.task.meta.theme"
              type="text"
              :disabled="confirming"
              placeholder="Enter theme"
            />
          </div>
          <div class="form-group">
            <label>Caption</label>
            <textarea
              v-model="draft.task.post.caption"
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
              @click="addJob"
            >
              Add Job
            </button>
          </div>

          <div
            v-for="(job, index) in draft.jobs"
            :key="`draft-job-${index}`"
            class="card ai-draft-job-card"
          >
            <div class="ai-draft-job-header">
              <h5>Job {{ index + 1 }}</h5>
              <button
                type="button"
                class="btn-danger btn-small"
                :disabled="confirming || draft.jobs.length === 1"
                @click="removeJob(index)"
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
            {{ confirming ? 'Creating…' : 'Create Task' }}
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

function cloneDraft(draft) {
  return JSON.parse(JSON.stringify(draft))
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
      draft: null,
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
    canConfirm() {
      if (!this.draft?.task?.name?.trim()) return false
      if (!Array.isArray(this.draft.jobs) || this.draft.jobs.length === 0) return false
      return this.draft.jobs.every((job) => {
        const promptText = job?.prompt?.prompt
        return Boolean(job.generator && typeof promptText === 'string' && promptText.trim())
      })
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
      const hadDraftWork = Boolean(this.draft) || Boolean(this.trimmedBrief)
      this.abortPreviewRequest()
      this.resetState()
      this.$emit('close')
      if (hadDraftWork) {
        this.$emit('discarded', 'Tenant changed. AI draft was discarded.')
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
      this.draft = null
      this.error = null
    },
    abortPreviewRequest() {
      if (this.previewAbortController) {
        this.previewAbortController.abort()
        this.previewAbortController = null
      }
    },
    normalizeDraft(draft) {
      const nextDraft = cloneDraft(draft)
      nextDraft.task.meta = nextDraft.task.meta || {}
      if (nextDraft.task.meta.theme === undefined) {
        nextDraft.task.meta.theme = ''
      }
      nextDraft.task.post = nextDraft.task.post || {}
      if (nextDraft.task.post.caption === undefined || nextDraft.task.post.caption === null) {
        nextDraft.task.post.caption = ''
      }
      nextDraft.jobs = (nextDraft.jobs || []).map((job, index) => ({
        ...emptyDraftJob(),
        ...job,
        order: job.order ?? index,
        prompt: {
          ...(job && typeof job.prompt === 'object' ? job.prompt : {}),
          prompt: job?.prompt?.prompt || '',
        },
      }))
      nextDraft.warnings = nextDraft.warnings || []
      return nextDraft
    },
    sanitizeDraftForConfirm() {
      const nextDraft = cloneDraft(this.draft)
      nextDraft.jobs = nextDraft.jobs.map((job, index) => {
        const normalizedOrder = Number.isFinite(job.order) ? Math.max(0, Math.floor(job.order)) : index
        return {
          ...job,
          order: normalizedOrder,
          prompt: {
            ...(job && typeof job.prompt === 'object' ? job.prompt : {}),
            prompt: job?.prompt?.prompt || '',
          },
        }
      })
      return nextDraft
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
        const draft = await taskService.previewAiTaskDraft(
          { brief: this.trimmedBrief },
          { signal: controller.signal }
        )
        this.draft = this.normalizeDraft(draft)
      } catch (error) {
        if (this.isRequestCanceled(error)) return
        if (error?.response?.status === 401) {
          this.handleAuthLoss()
          return
        }
        this.error = error?.response?.data?.detail || error?.message || 'Failed to generate AI draft.'
      } finally {
        if (this.previewAbortController === controller) {
          this.previewAbortController = null
        }
        this.generating = false
      }
    },
    addJob() {
      if (!this.draft || this.confirming) return
      this.draft.jobs.push({
        ...emptyDraftJob(),
        order: this.draft.jobs.length,
      })
    },
    removeJob(index) {
      if (!this.draft || this.confirming || this.draft.jobs.length === 1) return
      this.draft.jobs.splice(index, 1)
    },
    async confirmDraft() {
      if (!this.draft || !this.canConfirm || this.confirming) return

      this.error = null
      this.confirming = true
      try {
        const createdTask = await taskService.confirmAiTaskDraft(this.sanitizeDraftForConfirm())
        this.$emit('created', createdTask)
        this.resetState()
        this.$emit('close')
      } catch (error) {
        if (error?.response?.status === 401) {
          this.handleAuthLoss()
          return
        }
        this.error = error?.response?.data?.detail || error?.message || 'Failed to create task from AI draft.'
      } finally {
        this.confirming = false
      }
    },
    resetState() {
      this.brief = ''
      this.draft = null
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
