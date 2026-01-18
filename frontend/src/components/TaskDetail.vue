<template>
  <div class="task-detail">
    <div class="detail-header">
      <h2>Task Detail</h2>
      <div class="header-actions" v-if="task">
        <span :class="['badge', `badge-${task?.status}`]">{{ task?.status }}</span>
        <button @click="deleteTask" class="btn-danger">Delete</button>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading task...</div>
    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="success" class="success">{{ success }}</div>

    <div v-if="task" class="task-detail-content">
      <div class="card">
        <h3>Task Details</h3>
        <form @submit.prevent="updateTask">
          <div class="form-group">
            <label>Status</label>
            <input :value="task.status" disabled />
          </div>
          <div class="form-group">
            <label>Quote Text</label>
            <textarea v-model="editTask.quote_text" rows="4"></textarea>
          </div>
          <div class="form-group">
            <label>Caption Text</label>
            <input v-model="editTask.caption_text" type="text" />
          </div>
          <div class="form-group">
            <label>Image Generator</label>
            <select v-model="editTask.image_generator">
              <option value="">Default (Pillow)</option>
              <option value="pillow">Pillow</option>
              <option value="dalle">DALL-E</option>
            </select>
          </div>
          <div class="form-group">
            <label>Image Generator Prompt</label>
            <textarea v-model="editTask.image_generator_prompt" rows="3"></textarea>
          </div>
          <div class="form-group">
            <label>Image Path</label>
            <input :value="task.image_path || 'Not generated'" disabled />
            <a v-if="task.image_path" :href="getImageUrl(task.image_path)" target="_blank" class="image-link">
              View Image
            </a>
          </div>
          <div class="form-group">
            <label>Attempt Count</label>
            <input :value="task.attempt_count" disabled />
          </div>
          <div class="form-group" v-if="task.last_error">
            <label>Last Error</label>
            <textarea :value="task.last_error" disabled rows="3"></textarea>
          </div>
          <div class="form-group">
            <label>Created At</label>
            <input :value="formatDate(task.created_at)" disabled />
          </div>
          <div class="form-group">
            <label>Updated At</label>
            <input :value="formatDate(task.updated_at)" disabled />
          </div>
          <div class="form-actions">
            <button type="submit" class="btn-primary">Update Task</button>
          </div>
        </form>
      </div>

      <div class="card">
        <h3>Status Actions</h3>
        <div class="status-actions">
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
          <button
            v-if="task.status === 'ready'"
            @click="publishTask"
            class="btn-success"
          >
            Publish
          </button>
          <p v-if="getAvailableActions().length === 0" class="no-actions">
            No actions available for this status
          </p>
        </div>
      </div>
    </div>
  </div>
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
      editTask: {},
      loading: false,
      error: null,
      success: null,
    }
  },
  mounted() {
    this.loadTask()
  },
  methods: {
    async loadTask() {
      this.loading = true
      this.error = null
      try {
        this.task = await taskService.getTask(this.id)
        this.editTask = {
          quote_text: this.task.quote_text || '',
          caption_text: this.task.caption_text || '',
          image_generator: this.task.image_generator || '',
          image_generator_prompt: this.task.image_generator_prompt || '',
        }
      } catch (err) {
        this.error = err.response?.data?.detail || err.message || 'Failed to load task'
      } finally {
        this.loading = false
      }
    },
    async updateTask() {
      try {
        this.task = await taskService.updateTask(this.id, this.editTask)
        this.showSuccess('Task updated successfully')
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
    getAvailableActions() {
      if (!this.task) return []
      const actions = []
      if (this.task.status === 'draft') actions.push('submit')
      if (this.task.status === 'pending_approval') {
        actions.push('approve', 'disapprove')
      }
      if (this.task.status === 'pending_confirmation') {
        actions.push('approvePublication', 'reject')
      }
      if (this.task.status === 'ready') actions.push('publish')
      return actions
    },
    formatDate(dateString) {
      return new Date(dateString).toLocaleString()
    },
    getImageUrl(imagePath) {
      // Assuming images are served from the backend or a static server
      // Adjust this based on your setup
      if (imagePath.startsWith('http')) {
        return imagePath
      }
      return `http://localhost:8000/${imagePath}`
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
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 2rem;
}

@media (max-width: 1024px) {
  .task-detail-content {
    grid-template-columns: 1fr;
  }
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

.image-link:hover {
  text-decoration: underline;
}

.status-actions {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.no-actions {
  color: #999;
  font-style: italic;
}

.form-actions {
  margin-top: 1.5rem;
}
</style>
