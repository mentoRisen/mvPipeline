<template>
  <div class="task-list">
    <div class="task-list-header">
      <h2>Tasks</h2>
      <div class="header-actions">
        <select v-model="selectedStatus" @change="loadTasks" class="status-filter">
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="pending_approval">Pending Approval</option>
          <option value="disapproved">Disapproved</option>
          <option value="processing">Processing</option>
          <option value="ready">Ready</option>
          <option value="pending_confirmation">Pending Confirmation</option>
          <option value="published">Published</option>
          <option value="rejected">Rejected</option>
          <option value="failed">Failed</option>
        </select>
        <button @click="showCreateModal = true" class="btn-primary">Create Task</button>
        <button @click="openCreateFromJsonModal" class="btn-secondary">From JSON</button>
        <button @click="loadTasks" class="btn-pink">Refresh</button>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading tasks...</div>

    <div v-else>
      <div class="tasks-table card">
        <div class="tasks-table-header">
          <div class="col-id">ID</div>
          <div class="col-status">Status</div>
          <div class="col-quote">Name</div>
          <div class="col-created">Created</div>
          <div class="col-actions">Actions</div>
        </div>
        <div
          v-for="task in tasks"
          :key="task.id"
          class="tasks-table-row"
          :class="{ 'row-selected': selectedTaskId === task.id }"
          @click="selectTask(task.id)"
        >
          <div class="col-id">
            <span 
              class="mono task-id-clickable" 
              @click.stop="copyTaskId(task.id)" 
              :title="`Click to copy full ID: ${task.id}`"
            >
              {{ task.id.slice(0, 8) }}
            </span>
          </div>
          <div class="col-status">
            <span :class="['badge', `badge-${task.status}`]">{{ task.status }}</span>
          </div>
          <div class="col-quote">
            <span v-if="task.name" class="quote-preview">{{ task.name }}</span>
            <span v-else class="muted">No name</span>
          </div>
          <div class="col-created">
            <small>{{ formatDate(task.created_at) }}</small>
          </div>
          <div class="col-actions" @click.stop>
            <!-- Actions for list view are currently managed in TaskDetail; none here -->
          </div>
        </div>
        <div v-if="!loading && tasks.length === 0" class="empty-state">
          <p>No tasks found</p>
        </div>
      </div>
    </div>

    <!-- Create Task Modal -->
    <div v-if="showCreateModal" class="modal-overlay" @click="showCreateModal = false">
      <div class="modal-content" @click.stop>
        <h3>Create New Task</h3>
        <form @submit.prevent="createTask">
          <div class="form-group">
            <label>Name <span class="required">*</span></label>
            <input v-model="newTask.name" type="text" required />
          </div>
          <div class="form-group">
            <label>Template <span class="required">*</span></label>
            <select v-model="newTask.template" required>
              <option value="">Select template</option>
              <option value="instagram_post">Instagram Post</option>
            </select>
          </div>
          <div class="form-actions">
            <button type="button" @click="showCreateModal = false" class="btn-secondary">
              Cancel
            </button>
            <button type="submit" class="btn-primary">Create</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Create from JSON Modal -->
    <div
      v-if="showCreateFromJsonModal"
      class="modal-overlay"
      @click="closeCreateFromJsonModal"
    >
      <div class="modal-content json-create-modal" @click.stop>
        <h3>Create Task from JSON</h3>
        <div class="form-group">
          <label>Template <span class="required">*</span></label>
          <select v-model="jsonTemplateName" @change="loadJsonTemplate" required>
            <option value="">Select template</option>
            <option value="instagram_post">Instagram Post</option>
          </select>
        </div>
        <div class="form-group">
          <label>JSON Template</label>
          <textarea
            v-model="jsonTemplateText"
            class="json-textarea json-textarea-large"
            spellcheck="false"
            placeholder="Select a template to load JSON structure..."
          ></textarea>
        </div>
        <div class="form-actions">
          <button
            type="button"
            @click="closeCreateFromJsonModal"
            class="btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            @click="createTaskFromJson"
            class="btn-primary"
            :disabled="!jsonTemplateText || !jsonTemplateName"
          >
            Create from JSON
          </button>
        </div>
      </div>
    </div>

    <!-- Error/Success Modal -->
    <div v-if="error" class="modal-overlay" @click="dismissMessage">
      <div class="modal-content message-modal" @click.stop>
        <div class="message-content message-error">
          <h3>Error</h3>
          <p>{{ error }}</p>
          <div class="message-actions">
            <button @click="dismissMessage" class="btn-primary">Close</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Compact top-of-screen toast for success messages -->
    <transition name="toast-fade">
      <div v-if="success" class="toast-container">
        <div class="toast toast-success">
          {{ success }}
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
import { taskService } from '../services/api'
import { tenantStore } from '../tenantStore'

export default {
  name: 'TaskList',
  props: {
    selectedTaskId: {
      type: String,
      default: null,
    },
  },
  data() {
    return {
      tasks: [],
      loading: false,
      error: null,
      success: null,
      selectedStatus: '',
      showCreateModal: false,
      newTask: {
        name: '',
        template: '',
        tenant_id: null,
      },
      tenantStore,
      messageTimeout: null,
      showCreateFromJsonModal: false,
      jsonTemplateName: '',
      jsonTemplateText: '',
    }
  },
  computed: {
    currentTenantId() {
      return this.tenantStore.currentTenantId
    },
  },
  watch: {
    currentTenantId() {
      this.loadTasks()
    },
  },
  mounted() {
    this.loadTasks()
  },
  methods: {
    async loadTasks() {
      this.loading = true
      this.error = null
      try {
        const params = {}
        if (this.selectedStatus) {
          params.status = this.selectedStatus
        }
        if (tenantStore.currentTenantId) {
          params.tenant_id = tenantStore.currentTenantId
        }
        const data = await taskService.getTasks(params)
        this.tasks = data.tasks
      } catch (err) {
        this.error = err.response?.data?.detail || err.message || 'Failed to load tasks'
      } finally {
        this.loading = false
      }
    },
    async submitTask(id) {
      try {
        await taskService.submitTask(id)
        this.showSuccess('Task submitted for approval')
        this.loadTasks()
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to submit task')
      }
    },
    async approveProcessing(id) {
      try {
        await taskService.approveProcessing(id)
        this.showSuccess('Task approved for processing')
        this.loadTasks()
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to approve task')
      }
    },
    async disapproveTask(id) {
      try {
        await taskService.disapproveTask(id)
        this.showSuccess('Task disapproved')
        this.loadTasks()
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to disapprove task')
      }
    },
    async approvePublication(id) {
      try {
        await taskService.approvePublication(id)
        this.showSuccess('Task approved for publication')
        this.loadTasks()
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to approve publication')
      }
    },
    async publishTask(id) {
      try {
        await taskService.publishTask(id)
        this.showSuccess('Task published')
        this.loadTasks()
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to publish task')
      }
    },
    async rejectTask(id) {
      try {
        await taskService.rejectTask(id)
        this.showSuccess('Task rejected')
        this.loadTasks()
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to reject task')
      }
    },
    async createTask() {
      if (!this.newTask.name || !this.newTask.template) {
        this.showError('Name and template are required')
        return
      }
      const payload = { ...this.newTask }
      if (tenantStore.currentTenantId) {
        payload.tenant_id = tenantStore.currentTenantId
      } else {
        delete payload.tenant_id
      }
      try {
        await taskService.createTask(payload)
        this.showSuccess('Task created successfully')
        this.showCreateModal = false
        this.newTask = { name: '', template: '', tenant_id: null }
        this.loadTasks()
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to create task')
      }
    },
    selectTask(id) {
      // Ensure ID is a string
      const taskId = String(id)
      this.$emit('select-task', taskId)
    },
    formatDate(dateString) {
      return new Date(dateString).toLocaleString()
    },
    showError(message) {
      // Clear any existing timeout
      if (this.messageTimeout) {
        clearTimeout(this.messageTimeout)
      }
      this.error = message
      this.success = null
      // Auto-dismiss after 15 seconds (longer visibility)
      this.messageTimeout = setTimeout(() => {
        this.error = null
        this.messageTimeout = null
      }, 15000)
    },
    showSuccess(message) {
      // Clear any existing timeout
      if (this.messageTimeout) {
        clearTimeout(this.messageTimeout)
      }
      this.success = message
      this.error = null
      // Auto-dismiss after 3 seconds (toast-style, shorter for quick feedback)
      this.messageTimeout = setTimeout(() => {
        this.success = null
        this.messageTimeout = null
      }, 3000)
    },
    dismissMessage() {
      // Clear timeout if message is manually dismissed
      if (this.messageTimeout) {
        clearTimeout(this.messageTimeout)
        this.messageTimeout = null
      }
      this.error = null
      this.success = null
    },
    async copyTaskId(taskId) {
      try {
        await navigator.clipboard.writeText(taskId)
        this.showSuccess('Task ID copied to clipboard')
      } catch (err) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea')
        textArea.value = taskId
        textArea.style.position = 'fixed'
        textArea.style.opacity = '0'
        document.body.appendChild(textArea)
        textArea.select()
        try {
          document.execCommand('copy')
          this.showSuccess('Task ID copied to clipboard')
        } catch (fallbackErr) {
          this.showError('Failed to copy task ID')
        }
        document.body.removeChild(textArea)
      }
    },
    async openCreateFromJsonModal() {
      this.showCreateFromJsonModal = true
      this.jsonTemplateName = 'instagram_post'
      // Load template automatically
      await this.$nextTick()
      await this.loadJsonTemplate()
    },
    closeCreateFromJsonModal() {
      this.showCreateFromJsonModal = false
      this.jsonTemplateName = ''
      this.jsonTemplateText = ''
    },
    async loadJsonTemplate() {
      if (!this.jsonTemplateName) {
        this.jsonTemplateText = ''
        return
      }
      try {
        const template = await taskService.getTemplate(this.jsonTemplateName)
        this.jsonTemplateText = JSON.stringify(template, null, 2)
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to load template')
      }
    },
    async createTaskFromJson() {
      if (!this.jsonTemplateText || !this.jsonTemplateName) {
        this.showError('Please select a template and provide JSON')
        return
      }

      try {
        // Parse JSON
        const taskData = JSON.parse(this.jsonTemplateText)

        // Validate required fields
        if (!taskData.name || !taskData.template) {
          this.showError('JSON must include "name" and "template" fields')
          return
        }

        // Validate name is not empty or just whitespace
        if (!taskData.name.trim()) {
          this.showError('Task name cannot be empty')
          return
        }

        // Extract jobs if present
        const jobs = taskData.jobs || []
        delete taskData.jobs

        // Map top-level theme/caption into meta/post so they appear correctly in the UI
        // and are persisted in a consistent way.
        const topLevelTheme = taskData.theme
        const topLevelCaption = taskData.caption
        delete taskData.theme
        delete taskData.caption

        if (topLevelTheme !== undefined && topLevelTheme !== null && topLevelTheme !== '') {
          taskData.meta = taskData.meta || {}
          if (taskData.meta.theme === undefined) {
            taskData.meta.theme = topLevelTheme
          }
        }

        if (topLevelCaption !== undefined && topLevelCaption !== null && topLevelCaption !== '') {
          // Store caption under post.caption so TaskDetail sees it
          taskData.post = taskData.post || {}
          if (taskData.post.caption === undefined) {
            taskData.post.caption = topLevelCaption
          }
          // Also set caption_text for backend legacy support, if not already set
          if (taskData.caption_text === undefined) {
            taskData.caption_text = topLevelCaption
          }
        }

        // Clean up meta and post - remove null values or convert empty explanatory strings to null.
        // Skip theme/caption here so user-provided values from JSON are preserved.
        if (taskData.meta) {
          for (const key in taskData.meta) {
            if (key === 'theme') continue
            if (taskData.meta[key] === null || taskData.meta[key] === '') {
              taskData.meta[key] = null
            } else if (typeof taskData.meta[key] === 'string' && taskData.meta[key].startsWith('Enter ')) {
              // If it's still the explanatory text, set to null
              taskData.meta[key] = null
            }
          }
        }

        if (taskData.post) {
          for (const key in taskData.post) {
            if (key === 'caption') continue
            if (taskData.post[key] === null || taskData.post[key] === '') {
              taskData.post[key] = null
            } else if (typeof taskData.post[key] === 'string' && taskData.post[key].startsWith('Enter ')) {
              // If it's still the explanatory text, set to null
              taskData.post[key] = null
            }
          }
        }

        // Clean up job prompts - preserve prompt value, only set to null if explicitly empty
        if (jobs && jobs.length > 0) {
          for (const job of jobs) {
            console.log(`[createTaskFromJson] Before cleanup - job prompt:`, JSON.stringify(job.prompt))
            
            if (job.prompt && typeof job.prompt === 'object' && job.prompt.prompt !== undefined) {
              // Only set to null if prompt.prompt is explicitly empty (empty string or only whitespace)
              // DO NOT remove explanatory text - preserve whatever the user has
              const promptValue = job.prompt.prompt
              if (promptValue === '' || (typeof promptValue === 'string' && promptValue.trim() === '')) {
                console.log(`[createTaskFromJson] Prompt is empty, setting to null`)
                job.prompt = null
              } else {
                console.log(`[createTaskFromJson] Keeping prompt value:`, promptValue.substring(0, 50) + '...')
              }
            } else if (!job.prompt) {
              // If prompt is missing entirely,
              //  set to null
              job.prompt = null
            }
            
            console.log(`[createTaskFromJson] After cleanup - job prompt:`, JSON.stringify(job.prompt))
          }
        }

        // Use current tenant when creating
        if (tenantStore.currentTenantId) {
          taskData.tenant_id = tenantStore.currentTenantId
        }

        // Create task
        console.log('[createTaskFromJson] Creating task with data:', JSON.stringify(taskData, null, 2))
        const createdTask = await taskService.createTask(taskData)
        console.log('[createTaskFromJson] Task created successfully:', createdTask.id)

        // Create jobs if provided
        console.log('[createTaskFromJson] Jobs to create:', jobs.length)
        if (jobs.length > 0) {
          for (let i = 0; i < jobs.length; i++) {
            const jobData = jobs[i]
            console.log(`[createTaskFromJson] Processing job ${i + 1}/${jobs.length}:`, JSON.stringify(jobData, null, 2))
            
            // Only create job if it has required fields (generator is required, prompt is optional)
            if (jobData.generator) {
              console.log(`[createTaskFromJson] Creating job ${i + 1} for task ${createdTask.id} with generator: ${jobData.generator}`)
              try {
                const createdJob = await taskService.createJob(createdTask.id, jobData)
                console.log(`[createTaskFromJson] Job ${i + 1} created successfully:`, createdJob.id)
              } catch (jobError) {
                console.error(`[createTaskFromJson] Failed to create job ${i + 1}:`, jobError)
                throw jobError
              }
            } else {
              console.warn(`[createTaskFromJson] Skipping job ${i + 1} - missing generator field`)
            }
          }
        } else {
          console.log('[createTaskFromJson] No jobs to create')
        }

        this.showSuccess('Task created successfully from JSON')
        this.closeCreateFromJsonModal()
        this.loadTasks()
      } catch (err) {
        if (err instanceof SyntaxError) {
          this.showError('Invalid JSON format: ' + err.message)
        } else {
          this.showError(err.response?.data?.detail || err.message || 'Failed to create task from JSON')
        }
      }
    },
  },
}
</script>

<style scoped>
.status-filter {
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 0.9rem;
}

.tasks-table {
  width: 100%;
  padding: 0;
}

.tasks-table-header,
.tasks-table-row {
  display: grid;
  grid-template-columns: 0.9fr 1.1fr 3fr 1.6fr 2.2fr;
  gap: 0.75rem;
  align-items: center;
  padding: 0.6rem 1rem;
}

.tasks-table-header {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #6b7280;
  border-bottom: 1px solid #e5e7eb;
}

.tasks-table-row {
  font-size: 0.9rem;
  border-bottom: 1px solid #f3f4f6;
  cursor: pointer;
}

.tasks-table-row:hover {
  background-color: #f9fafb;
}

.tasks-table-row.row-selected {
  background-color: #eef2ff;
}

.quote-preview {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #4b5563;
}

.col-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  justify-content: flex-end;
}

.empty-state {
  text-align: center;
  padding: 3rem;
  color: #999;
}

.json-create-modal {
  max-width: 800px;
}
</style>
