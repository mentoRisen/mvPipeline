<template>
  <div class="task-detail">
    <div class="detail-header">
      <h2>Task Detail</h2>
      <div class="header-actions" v-if="task">
        <span :class="['badge', `badge-${task?.status}`]">{{ task?.status }}</span>
        <button
          v-if="task.status === 'processing'"
          @click="overrideProcessing"
          class="btn-secondary"
          type="button"
        >
          Override processing
        </button>
        <button
          type="button"
          class="btn-primary"
          @click="updateTask"
        >
          Update Task
        </button>
        <button
          v-if="task.status === 'ready' || task.status === 'publishing' || task.status === 'failed'"
          @click="openPublishPreview"
          class="btn-secondary"
        >
          Publish
        </button>
        <button
          v-if="task.status === 'draft'"
          @click="submitTask"
          class="btn-primary"
        >
          Submit for Approval
        </button>
        <button
          v-if="task.status === 'pending_approval'"
          @click="approveProcessing"
          class="btn-success"
        >
          Approve for Processing
        </button>
        <button
          v-if="task.status === 'pending_approval'"
          @click="disapproveTask"
          class="btn-danger"
        >
          Disapprove
        </button>
        <button
          v-if="task.status === 'pending_confirmation'"
          @click="approvePublication"
          class="btn-success"
        >
          Approve for Publication
        </button>
        <button
          v-if="task.status === 'pending_confirmation'"
          @click="rejectTask"
          class="btn-danger"
        >
          Reject
        </button>
        <button @click="deleteTask" class="btn-danger">Delete</button>
        <button
          type="button"
          class="btn-secondary"
          @click="openJsonModal"
        >
          Json
        </button>
        <button
          type="button"
          class="btn-pink"
          @click="loadTask"
        >
          Refresh
        </button>
      </div>
    </div>

    <div v-if="task" class="task-detail-content">
      <form @submit.prevent="updateTask" class="card">
        <h3>Task Information</h3>
        <div class="form-group">
          <label>Template</label>
          <input :value="task.template || 'Not set'" disabled />
        </div>
        <div class="form-group">
          <label>Name</label>
          <input v-model="editTask.name" type="text" />
        </div>
        <div class="form-group">
          <label>Theme</label>
          <input v-model="editTask.theme" type="text" placeholder="Enter theme" />
        </div>
        <div class="form-group">
          <label>Caption</label>
          <textarea
            v-model="editTask.caption"
            rows="4"
            placeholder="Enter caption text"
          ></textarea>
        </div>

        <!-- Jobs table -->
        <div class="form-group jobs-section">
          <div class="jobs-header">
            <label>Jobs</label>
            <button
              type="button"
              class="btn-secondary btn-small"
              @click="createJob"
            >
              Create Job
            </button>
          </div>
          <div class="jobs-table-wrapper">
            <table class="jobs-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>ID</th>
                  <th>Status</th>
                  <th>Generator</th>
                  <th>Purpose</th>
                  <th>Prompt</th>
                  <th>Image</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <template v-if="task.jobs && task.jobs.length">
                  <tr v-for="job in task.jobs" :key="job.id">
                    <td class="mono">
                      {{ job.order ?? 0 }}
                    </td>
                    <td class="mono job-id-clickable" @click="copyJobId(job.id)" :title="`Click to copy full ID: ${job.id}`">
                      {{ job.id?.slice(0, 8) }}
                    </td>
                    <td>
                      <span :class="['badge', `badge-${job.status}`]">
                        {{ job.status }}
                      </span>
                    </td>
                    <td>{{ job.generator || '—' }}</td>
                    <td class="jobs-purpose">
                      {{ job.purpose || '—' }}
                    </td>
                    <td class="jobs-prompt">
                      <span v-if="!job.prompt?.prompt">—</span>
                      <span v-else>
                        <span v-if="expandedPrompts[job.id]">
                          {{ job.prompt.prompt }}
                        </span>
                        <span v-else>
                          {{ truncatePrompt(job.prompt.prompt) }}
                          <button
                            type="button"
                            class="link-button"
                            @click="togglePrompt(job.id)"
                          >
                            ... more
                          </button>
                        </span>
                      </span>
                    </td>
                    <td class="jobs-image">
                      <button
                        v-if="job.result && getJobImageUrl(job.result)"
                        type="button"
                        class="image-thumb-button"
                        @click.stop="openJobImageModal(job)"
                        :title="'Open image for job ' + job.id"
                      >
                        <img
                          :src="getJobImageUrl(job.result)"
                          alt="Job image thumbnail"
                          class="jobs-image-thumb"
                        />
                      </button>
                      <span v-else class="muted">—</span>
                    </td>
                    <td>{{ formatDate(job.created_at) }}</td>
                    <td class="jobs-actions">
                      <button
                        v-if="job.status === 'new' || job.status === 'error'"
                        type="button"
                        class="btn-small btn-success"
                        @click="setJobReady(job)"
                      >
                        Ready
                      </button>
                      <button
                        v-if="job.status === 'ready'"
                        type="button"
                        class="btn-small btn-primary"
                        :disabled="processingJobs[job.id]"
                        @click="processJob(job)"
                      >
                        {{ processingJobs[job.id] ? 'Processing…' : 'Process' }}
                      </button>
                      <button
                        v-if="job.status === 'processing' || job.status === 'error' || job.status === 'processed'"
                        type="button"
                        class="btn-small btn-pink"
                        :disabled="processingJobs[job.id]"
                        @click="retryJob(job)"
                      >
                        {{ processingJobs[job.id] ? 'Retrying…' : 'Retry' }}
                      </button>
                      <button
                        type="button"
                        class="btn-small btn-secondary"
                        @click="editJob(job)"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        class="btn-small btn-danger"
                        @click="deleteJob(job)"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                </template>
                <tr v-else>
                  <td class="jobs-empty" colspan="8">No jobs yet</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

      </form>

      <div class="card" v-if="task.meta">
        <h3>Meta</h3>
        <div class="json-display">
          <pre>{{ formatJson(task.meta) }}</pre>
        </div>
      </div>

      <div class="card" v-if="task.post">
        <h3>Post</h3>
        <div class="json-display">
          <pre>{{ formatJson(task.post) }}</pre>
        </div>
      </div>
    </div>

    <!-- Create/Edit Job Modal -->
    <div v-if="showJobModal" class="modal-overlay" @click="cancelJob">
      <div class="modal-content" @click.stop>
        <h3>{{ editingJobId ? 'Edit Job' : 'Create Job' }}</h3>
        <form @submit.prevent="submitJob">
          <div class="form-group">
            <label>Status</label>
            <input type="text" :value="currentJobStatus || 'new'" disabled />
          </div>
          <div class="form-group">
            <label>Order</label>
            <input
              v-model.number="newJob.order"
              type="number"
              min="0"
              step="1"
            />
          </div>
          <div class="form-group">
            <label>Generator</label>
            <select v-model="newJob.generator">
              <option value="dalle">dalle</option>
              <option value="gptimage15">gptimage15</option>
            </select>
          </div>
          <div class="form-group">
            <label>Purpose</label>
            <select v-model="newJob.purpose">
              <option value="imagecontent">imagecontent</option>
            </select>
          </div>
          <div class="form-group">
            <label>Prompt</label>
            <textarea
              v-model="newJob.promptText"
              rows="3"
              placeholder="Enter prompt"
            ></textarea>
          </div>
          <div class="form-group" v-if="editingJobId">
            <label>Result</label>
            <div class="json-display">
              <textarea
                v-model="currentJobResultText"
                rows="6"
                class="json-textarea"
                placeholder="Edit job result JSON"
              ></textarea>
              <div
                v-if="currentJobResult && getJobImageUrl(currentJobResult)"
                class="image-preview"
              >
                <label>
                  Generated Image
                  <a
                    v-if="getJobPublicImageUrl(currentJobResult)"
                    :href="getJobPublicImageUrl(currentJobResult)"
                    target="_blank"
                    rel="noopener"
                    class="image-link-inline"
                  >
                    public image
                  </a>
                </label>
                <a
                  :href="getJobImageUrl(currentJobResult)"
                  target="_blank"
                  rel="noopener"
                  class="image-link"
                >
                  <img
                    :src="getJobImageUrl(currentJobResult)"
                    alt="Generated image"
                    class="image-preview-img"
                  />
                </a>
              </div>
            </div>
          </div>
          <div class="form-actions modal-actions">
            <button
              type="button"
              class="btn-secondary"
              @click="cancelJob"
            >
              Cancel
            </button>
            <button type="submit" class="btn-primary">
              {{ editingJobId ? 'Update' : 'Create' }}
            </button>
          </div>
        </form>
      </div>
    </div>
    <!-- Publish Preview Modal -->
    <div
      v-if="showPublishModal"
      class="modal-overlay"
      @click="closePublishPreview"
    >
      <div class="modal-content publish-modal" @click.stop>
        <h3>Publish Preview</h3>
        <div class="form-group">
          <label>Where to publish</label>
          <select v-model="selectedPublishDestination">
            <option value="instagram_post">Instagram post</option>
          </select>
        </div>

        <div
          v-if="selectedPublishDestination === 'instagram_post'"
          class="instagram-preview-wrapper"
        >
          <h4>Instagram Post Preview</h4>
          <div class="instagram-preview-card">
            <div class="instagram-image-area" v-if="instagramImageJobs.length">
              <div class="carousel-controls" v-if="instagramImageJobs.length > 1">
                <button
                  type="button"
                  class="btn-small btn-secondary"
                  @click.stop="prevCarouselImage"
                >
                  ‹
                </button>
                <span class="carousel-indicator">
                  {{ currentCarouselIndex + 1 }} / {{ instagramImageJobs.length }}
                </span>
                <button
                  type="button"
                  class="btn-small btn-secondary"
                  @click.stop="nextCarouselImage"
                >
                  ›
                </button>
              </div>
              <div class="instagram-image-container">
                <img
                  :src="getJobImageUrl(instagramImageJobs[currentCarouselIndex].result)"
                  alt="Instagram preview"
                />
              </div>
            </div>
            <div
              v-else
              class="instagram-image-area instagram-image-area-empty"
            >
              <span>No imagecontent jobs with images to show.</span>
            </div>
            <div class="instagram-caption-area">
              <p v-if="captionPreview">{{ captionPreview }}</p>
              <p v-else class="caption-placeholder">
                Caption is empty. It will appear here.
              </p>
            </div>
          </div>
        </div>

        <div class="form-actions modal-actions">
          <button
            type="button"
            class="btn-secondary"
            @click="closePublishPreview"
          >
            Cancel
          </button>
          <button
            type="button"
            class="btn-success"
            @click="confirmPublishPreview"
          >
            Publish
          </button>
        </div>
      </div>
    </div>

    <!-- Task JSON Modal -->
    <div
      v-if="showJsonModal"
      class="modal-overlay"
      @click="closeJsonModal"
    >
      <div class="modal-content json-modal" @click.stop>
        <h3>Task JSON</h3>
        <p class="json-modal-help">
          This is a read-only JSON view of the current task object, including its jobs.
          You can edit or copy it here, but changes are not saved back to the server.
        </p>
        <textarea
          v-model="jsonEditorText"
          class="json-textarea json-textarea-large"
          spellcheck="false"
        ></textarea>
        <div class="form-actions modal-actions">
          <button
            type="button"
            class="btn-secondary"
            @click="closeJsonModal"
          >
            Close
          </button>
        </div>
      </div>
    </div>

    <!-- Job Image Preview Modal -->
    <div
      v-if="showJobImageModal"
      class="modal-overlay"
      @click="closeJobImageModal"
    >
      <div class="modal-content image-modal" @click.stop>
        <img
          v-if="jobImageModalUrl"
          :src="jobImageModalUrl"
          alt="Job image preview"
          class="image-modal-img"
        />
      </div>
    </div>
  </div>

  <!-- Compact top-of-screen toast for error/success messages -->
  <transition name="toast-fade">
    <div v-if="error || success" class="toast-container">
      <div :class="['toast', error ? 'toast-error' : 'toast-success']">
        {{ error || success }}
      </div>
    </div>
  </transition>
</template>

<script>
import { taskService } from '../services/api'

export default {
  name: 'TaskDetail',
  props: {
    id: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      task: null,
      editTask: {
        name: '',
        theme: '',
        caption: '',
      },
      showPublishModal: false,
      selectedPublishDestination: 'instagram_post',
      currentCarouselIndex: 0,
      loading: false,
      error: null,
      success: null,
      showJobModal: false,
      editingJobId: null,
      expandedPrompts: {},
      currentJobResult: null,
      currentJobStatus: null,
      currentJobResultText: '',
      newJob: {
        order: 0,
        generator: 'dalle',
        purpose: 'imagecontent',
        promptText: '',
      },
      // Per-job processing state for showing a loading indicator on the Process button
      processingJobs: {},
      // JSON modal state
      showJsonModal: false,
      jsonEditorText: '',
      // Job image preview modal
      showJobImageModal: false,
      jobImageModalUrl: null,
    }
  },
  mounted() {
    this.loadTask()
  },
  computed: {
    instagramImageJobs() {
      if (!this.task || !this.task.jobs) return []
      return this.task.jobs.filter((job) => {
        return (
          job.purpose === 'imagecontent' &&
          job.result &&
          this.getJobImageUrl(job.result)
        )
      })
    },
    captionPreview() {
      if (this.editTask.caption) return this.editTask.caption
      if (this.task && this.task.post && this.task.post.caption) {
        return this.task.post.caption
      }
      return ''
    },
  },
  watch: {
    // Watch for id changes to reload task data
    id(newId, oldId) {
      if (newId && newId !== oldId) {
        this.loadTask()
      }
    },
  },
  methods: {
    async loadTask() {
      this.loading = true
      this.error = null
      try {
        this.task = await taskService.getTask(this.id)
        this.editTask = {
          name: this.task.name || '',
          theme: (this.task.meta && this.task.meta.theme) || '',
          caption: (this.task.post && this.task.post.caption) || '',
        }
      } catch (err) {
        this.error = err.response?.data?.detail || err.message || 'Failed to load task'
      } finally {
        this.loading = false
      }
    },
    async updateTask() {
      try {
        // Get current meta or create empty object
        const currentMeta = this.task.meta || {}
        
        // Update meta with new theme value
        const updatedMeta = {
          ...currentMeta,
          theme: this.editTask.theme || null,
        }
        
        // Get current post or create empty object
        const currentPost = this.task.post || {}
        
        // Update post with new caption value
        const updatedPost = {
          ...currentPost,
          caption: this.editTask.caption || null,
        }
        
        const updateData = {
          name: this.editTask.name || null,
          meta: updatedMeta,
          post: updatedPost,
        }
        
        this.task = await taskService.updateTask(this.id, updateData)
        this.showSuccess('Task updated successfully')
        // Reload to get updated data
        this.loadTask()
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to update task')
      }
    },
    async deleteTask() {
      if (!confirm('Are you sure you want to delete this task?')) {
        return
      }
      try {
        await taskService.deleteTask(this.id)
        // Emit event to parent to refresh list and clear selection
        this.$emit('task-deleted', this.id)
        // Navigate to home
        this.$router.push('/')
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to delete task')
      }
    },
    async submitTask() {
      try {
        this.task = await taskService.submitTask(this.id)
        this.showSuccess('Task submitted for approval')
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to submit task')
      }
    },
    async approveProcessing() {
      try {
        this.task = await taskService.approveProcessing(this.id)
        this.showSuccess('Task approved for processing')
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to approve task')
      }
    },
    async disapproveTask() {
      try {
        this.task = await taskService.disapproveTask(this.id)
        this.showSuccess('Task disapproved')
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to disapprove task')
      }
    },
    async approvePublication() {
      try {
        this.task = await taskService.approvePublication(this.id)
        this.showSuccess('Task approved for publication')
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to approve publication')
      }
    },
    async publishTask() {
      try {
        this.task = await taskService.publishTask(this.id)
        this.showSuccess('Task published')
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to publish task')
      }
    },
    async rejectTask() {
      try {
        this.task = await taskService.rejectTask(this.id)
        this.showSuccess('Task rejected')
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to reject task')
      }
    },
    async overrideProcessing() {
      try {
        this.task = await taskService.overrideProcessing(this.id)
        this.showSuccess('Task moved to pending confirmation')
      } catch (err) {
        this.showError(
          err.response?.data?.detail || 'Failed to override processing'
        )
      }
    },
    openPublishPreview() {
      this.showPublishModal = true
      this.currentCarouselIndex = 0
    },
    closePublishPreview() {
      this.showPublishModal = false
    },
    confirmPublishPreview() {
      // For now this only confirms and closes the modal without calling backend.
      if (confirm('Are you sure you want to publish this post?')) {
        this.showPublishModal = false
      }
    },
    nextCarouselImage() {
      if (!this.instagramImageJobs.length) return
      this.currentCarouselIndex =
        (this.currentCarouselIndex + 1) % this.instagramImageJobs.length
    },
    prevCarouselImage() {
      if (!this.instagramImageJobs.length) return
      this.currentCarouselIndex =
        (this.currentCarouselIndex - 1 + this.instagramImageJobs.length) %
        this.instagramImageJobs.length
    },
    formatDate(dateString) {
      return new Date(dateString).toLocaleString()
    },
    formatJson(obj) {
      if (!obj) return ''
      return JSON.stringify(obj, null, 2)
    },
    getJobImageUrl(result) {
      const rel = result?.image_path || result?.image_path_relative
      if (!rel) return null
      // Same base as API, but strip /api/v1 if present
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
      const root = apiBase.replace(/\/api\/v1\/?$/, '')
      return root + rel
    },
    getJobPublicImageUrl(result) {
      const rel = result?.image_path || result?.image_path_relative
      if (!rel) return null

      // Prefer explicit PUBLIC_URL from frontend env, fallback to API root
      const publicUrl = import.meta.env.VITE_PUBLIC_URL

      const base = String(publicUrl).replace(/\/+$/, '')
      const path = String(rel).replace(/^\/+/, '')
      return `${base}/${path}`
    },
    openJobImageModal(job) {
      const url = job.result && this.getJobImageUrl(job.result)
      if (!url) return
      this.jobImageModalUrl = url
      this.showJobImageModal = true
    },
    closeJobImageModal() {
      this.showJobImageModal = false
      this.jobImageModalUrl = null
    },
    truncatePrompt(text) {
      if (!text) return ''
      const words = text.split(/\s+/)
      if (words.length <= 5) return text
      return words.slice(0, 5).join(' ')
    },
    togglePrompt(jobId) {
      if (this.expandedPrompts[jobId]) {
        delete this.expandedPrompts[jobId]
      } else {
        this.expandedPrompts[jobId] = true
      }
    },
    async setJobReady(job) {
      try {
        await taskService.updateJob(this.id, job.id, { status: 'ready' })
        this.showSuccess('Job status updated to ready')
        // Reload task to show updated job status
        this.loadTask()
      } catch (err) {
        this.showError(
          err.response?.data?.detail || err.message || 'Failed to update job status'
        )
      }
    },
    async processJob(job) {
      try {
        // Mark this job as processing to update the UI
        this.$set
          ? this.$set(this.processingJobs, job.id, true)
          : (this.processingJobs = { ...this.processingJobs, [job.id]: true })

        await taskService.processJob(this.id, job.id)
        this.showSuccess('Job processed')
      } catch (err) {
        this.showError(
          err.response?.data?.detail || err.message || 'Failed to process job'
        )
      } finally {
        // Clear processing state for this job
        if (this.$delete) {
          this.$delete(this.processingJobs, job.id)
        } else {
          const { [job.id]: _, ...rest } = this.processingJobs
          this.processingJobs = rest
        }
        // Always reload task to reflect updated job status/result,
        // even when processing fails and job moves to ERROR.
        this.loadTask()
      }
    },
    async retryJob(job) {
      try {
        // Mark this job as processing/retrying in the UI
        this.$set
          ? this.$set(this.processingJobs, job.id, true)
          : (this.processingJobs = { ...this.processingJobs, [job.id]: true })

        // First reset status back to 'ready'
        await taskService.updateJob(this.id, job.id, { status: 'ready' })

        // Then process the job again
        await taskService.processJob(this.id, job.id)
        this.showSuccess('Job retried')
      } catch (err) {
        this.showError(
          err.response?.data?.detail || err.message || 'Failed to retry job'
        )
      } finally {
        // Clear processing state for this job
        if (this.$delete) {
          this.$delete(this.processingJobs, job.id)
        } else {
          const { [job.id]: _, ...rest } = this.processingJobs
          this.processingJobs = rest
        }
        // Reload task to reflect updated job status/result
        this.loadTask()
      }
    },
    async deleteJob(job) {
      if (!confirm(`Are you sure you want to delete this job?`)) {
        return
      }
      try {
        await taskService.deleteJob(this.id, job.id)
        this.showSuccess('Job deleted successfully')
        // Reload task to show updated job list
        this.loadTask()
      } catch (err) {
        this.showError(
          err.response?.data?.detail || err.message || 'Failed to delete job'
        )
      }
    },
    createJob() {
      // Open job creation modal
      this.editingJobId = null
      this.showJobModal = true
      this.newJob = {
        order: 0,
        generator: 'dalle',
        purpose: 'imagecontent',
        promptText: '',
      }
    },
    editJob(job) {
      // Open job edit modal with job data
      this.editingJobId = job.id
      this.currentJobResult = job.result || null
      this.currentJobStatus = job.status || 'new'
      this.currentJobResultText = this.currentJobResult
        ? this.formatJson(this.currentJobResult)
        : ''
      this.showJobModal = true
      this.newJob = {
        order: job.order ?? 0,
        generator: job.generator || 'dalle',
        purpose: job.purpose || 'imagecontent',
        promptText: job.prompt?.prompt || '',
      }
    },
    cancelJob() {
      this.showJobModal = false
      this.editingJobId = null
      this.currentJobResult = null
      this.currentJobStatus = null
      this.currentJobResultText = ''
      this.newJob = {
        order: 0,
        generator: 'dalle',
        purpose: 'imagecontent',
        promptText: '',
      }
    },
    async submitJob() {
      if (!this.newJob.generator) {
        this.showError('Generator is required')
        return
      }

      try {
        // Build payload (status is set automatically on backend for new jobs)
        const payload = {
          order:
            this.newJob.order !== null && this.newJob.order !== undefined
              ? Number(this.newJob.order)
              : 0,
          generator: this.newJob.generator,
          purpose: this.newJob.purpose || null,
          prompt: this.newJob.promptText
            ? { prompt: this.newJob.promptText }
            : null,
        }

        // When editing an existing job, allow updating the result JSON
        if (this.editingJobId && this.currentJobResultText.trim()) {
          try {
            payload.result = JSON.parse(this.currentJobResultText)
          } catch (e) {
            this.showError('Result must be valid JSON')
            return
          }
        }

        if (this.editingJobId) {
          // Update existing job
          await taskService.updateJob(this.id, this.editingJobId, payload)
          this.showSuccess('Job updated successfully')
        } else {
          // Create new job
          await taskService.createJob(this.id, payload)
          this.showSuccess('Job created successfully')
        }

        // Reset form
        this.newJob = {
          order: 0,
          generator: 'dalle',
          purpose: 'imagecontent',
          promptText: '',
        }
        this.editingJobId = null
        this.showJobModal = false

        // Reload task to show updated job
        this.loadTask()
      } catch (err) {
        this.showError(
          err.response?.data?.detail || err.message || `Failed to ${this.editingJobId ? 'update' : 'create'} job`
        )
      }
    },
    openJsonModal() {
      if (!this.task) return
      // Deep-clone to avoid any accidental refs, then pretty-print
      const cloned = JSON.parse(JSON.stringify(this.task))
      this.jsonEditorText = this.formatJson(cloned)
      this.showJsonModal = true
    },
    closeJsonModal() {
      this.showJsonModal = false
    },
    showError(message) {
      this.error = message
      this.success = null
      setTimeout(() => {
        this.error = null
      }, 5000)
    },
    showSuccess(message) {
      this.success = message
      this.error = null
      setTimeout(() => {
        this.success = null
      }, 3000)
    },
    async copyJobId(jobId) {
      try {
        await navigator.clipboard.writeText(jobId)
      } catch (err) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea')
        textArea.value = jobId
        textArea.style.position = 'fixed'
        textArea.style.opacity = '0'
        document.body.appendChild(textArea)
        textArea.select()
        try {
          document.execCommand('copy')
        } catch (fallbackErr) {
          // Silently fail
        }
        document.body.removeChild(textArea)
      }
    },
  },
}
</script>

<style scoped>
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.back-link {
  color: #667eea;
  text-decoration: none;
  font-weight: 500;
}

.back-link:hover {
  text-decoration: underline;
}

.header-actions {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.task-detail-content {
  display: block;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #374151;
}

.image-link {
  display: inline-block;
  margin-top: 0.5rem;
  color: #667eea;
  text-decoration: none;
}

.image-link-inline {
  margin-left: 0.75rem;
  font-size: 0.85rem;
  color: #667eea;
  text-decoration: underline;
}

.form-actions {
  margin-top: 1.5rem;
}

.json-display {
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 1rem;
  overflow-x: auto;
}

.json-textarea {
  width: 100%;
  box-sizing: border-box;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 0.85rem;
}

.image-preview {
  margin-top: 1rem;
}

.image-preview-img {
  max-width: 100%;
  max-height: 240px;
  display: block;
  border-radius: 4px;
  border: 1px solid #ddd;
}

.json-display pre {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 0.875rem;
  line-height: 1.5;
  color: #333;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.jobs-section {
  margin-top: 2rem;
}

.jobs-table-wrapper {
  overflow-x: auto;
}

.jobs-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.jobs-table th,
.jobs-table td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #e5e7eb;
  text-align: left;
  vertical-align: middle;
}

.jobs-table th {
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  color: #6b7280;
  background-color: #f9fafb;
}

.jobs-table tr:hover {
  background-color: #f3f4f6;
}

.jobs-actions {
  display: flex;
  gap: 0.5rem;
}

.jobs-purpose {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.jobs-prompt {
  max-width: 300px;
  word-wrap: break-word;
  line-height: 1.4;
}

.jobs-image {
  width: 60px;
}

.jobs-image-thumb {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #ddd;
  display: block;
}

.image-thumb-button {
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
}

.link-button {
  background: none;
  border: none;
  color: #667eea;
  cursor: pointer;
  padding: 0;
  margin-left: 0.25rem;
  text-decoration: underline;
  font-size: inherit;
}

.link-button:hover {
  color: #5568d3;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 0.8rem;
}

.job-id-clickable {
  cursor: pointer;
  color: #667eea;
  text-decoration: underline;
  user-select: none;
}

.job-id-clickable:hover {
  color: #5568d3;
  background-color: #f3f4f6;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  width: 90%;
  max-width: 520px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-content h3 {
  margin-bottom: 1.5rem;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}

.json-modal {
  max-width: 800px;
}

.json-textarea-large {
  min-height: 50vh;
  resize: vertical;
  margin-top: 1rem;
}

.json-modal-help {
  font-size: 0.85rem;
  color: #6b7280;
  margin-bottom: 0.5rem;
}

.image-modal {
  max-width: 800px;
}

.image-modal-img {
  max-width: 100%;
  max-height: 80vh;
  display: block;
  border-radius: 8px;
}

/* Top-of-screen toast messages */
.toast-container {
  position: fixed;
  top: 1rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1100;
  pointer-events: none;
}

.toast {
  min-width: 260px;
  max-width: 420px;
  background: #111827;
  color: #f9fafb;
  padding: 0.5rem 0.9rem;
  border-radius: 999px;
  font-size: 0.85rem;
  box-shadow: 0 10px 15px rgba(0, 0, 0, 0.15);
  pointer-events: auto;
  display: inline-flex;
  justify-content: center;
  align-items: center;
}

.toast-error {
  background: #7f1d1d;
}

.toast-success {
  background: #064e3b;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -10px);
}

.btn-pink {
  background-color: #ec4899; /* pink-500 */
  color: #ffffff;
}

.btn-pink:hover {
  background-color: #db2777; /* pink-600 */
}

.publish-modal h4 {
  margin-bottom: 0.75rem;
}

.instagram-preview-wrapper {
  margin-top: 1rem;
}

.instagram-preview-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #f9fafb;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.instagram-image-area {
  position: relative;
  background: #111827;
  min-height: 260px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.instagram-image-area-empty {
  color: #9ca3af;
  font-size: 0.875rem;
}

.instagram-image-container img {
  max-width: 100%;
  max-height: 400px;
  object-fit: contain;
  display: block;
}

.carousel-controls {
  position: absolute;
  top: 0.5rem;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.carousel-indicator {
  font-size: 0.75rem;
  color: #e5e7eb;
}

.instagram-caption-area {
  padding: 0.75rem 1rem 1rem;
  background: white;
  font-size: 0.9rem;
  color: #111827;
  max-height: 200px;
  overflow-y: auto;
}

.caption-placeholder {
  color: #9ca3af;
  font-style: italic;
}
</style>
