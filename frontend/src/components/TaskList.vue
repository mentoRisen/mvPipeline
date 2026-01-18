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
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="success" class="success">{{ success }}</div>

    <div v-if="loading" class="loading">Loading tasks...</div>

    <div v-else>
      <div class="tasks-table card">
        <div class="tasks-table-header">
          <div class="col-id">ID</div>
          <div class="col-status">Status</div>
          <div class="col-quote">Quote</div>
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
            <span class="mono">{{ task.id.slice(0, 8) }}</span>
          </div>
          <div class="col-status">
            <span :class="['badge', `badge-${task.status}`]">{{ task.status }}</span>
          </div>
          <div class="col-quote">
            <span v-if="task.quote_text" class="quote-preview">{{ task.quote_text }}</span>
            <span v-else class="muted">No quote text</span>
          </div>
          <div class="col-created">
            <small>{{ formatDate(task.created_at) }}</small>
          </div>
          <div class="col-actions" @click.stop>
            <button
              v-if="task.status === 'draft'"
              @click="submitTask(task.id)"
              class="btn-primary btn-small"
            >
              Submit
            </button>
            <button
              v-if="task.status === 'pending_approval'"
              @click="approveProcessing(task.id)"
              class="btn-success btn-small"
            >
              Approve
            </button>
            <button
              v-if="task.status === 'pending_approval'"
              @click="disapproveTask(task.id)"
              class="btn-danger btn-small"
            >
              Disapprove
            </button>
            <button
              v-if="task.status === 'pending_confirmation'"
              @click="approvePublication(task.id)"
              class="btn-success btn-small"
            >
              Approve Pub.
            </button>
            <button
              v-if="task.status === 'pending_confirmation'"
              @click="rejectTask(task.id)"
              class="btn-danger btn-small"
            >
              Reject
            </button>
            <button
              v-if="task.status === 'ready'"
              @click="publishTask(task.id)"
              class="btn-success btn-small"
            >
              Publish
            </button>
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
            <label>Quote Text</label>
            <textarea v-model="newTask.quote_text" rows="4"></textarea>
          </div>
          <div class="form-group">
            <label>Caption Text</label>
            <input v-model="newTask.caption_text" type="text" />
          </div>
          <div class="form-group">
            <label>Image Generator</label>
            <select v-model="newTask.image_generator">
              <option value="">Default (Pillow)</option>
              <option value="pillow">Pillow</option>
              <option value="dalle">DALL-E</option>
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
  </div>
</template>

<script>
import { taskService } from '../services/api'

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
        quote_text: '',
        caption_text: '',
        image_generator: '',
      },
    }
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
      try {
        await taskService.createTask(this.newTask)
        this.showSuccess('Task created successfully')
        this.showCreateModal = false
        this.newTask = { quote_text: '', caption_text: '', image_generator: '' }
        this.loadTasks()
      } catch (err) {
        this.showError(err.response?.data?.detail || 'Failed to create task')
      }
    },
    selectTask(id) {
      this.$emit('select-task', id)
    },
    formatDate(dateString) {
      return new Date(dateString).toLocaleString()
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
  },
}
</script>

<style scoped>
.task-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.header-actions {
  display: flex;
  gap: 1rem;
  align-items: center;
}

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

.col-id .mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 0.8rem;
}

.quote-preview {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #4b5563;
}

.muted {
  color: #9ca3af;
  font-size: 0.85rem;
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
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-content h3 {
  margin-bottom: 1.5rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #374151;
}

.form-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
}
</style>
