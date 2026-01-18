import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const taskService = {
  // Get all tasks
  async getTasks(params = {}) {
    const { limit = 100, offset = 0, status } = params
    const response = await api.get('/tasks', {
      params: { limit, offset, status },
    })
    return response.data
  },

  // Get task by ID
  async getTask(id) {
    const response = await api.get(`/tasks/${id}`)
    return response.data
  },

  // Create task
  async createTask(taskData) {
    const response = await api.post('/tasks', taskData)
    return response.data
  },

  // Update task
  async updateTask(id, taskData) {
    const response = await api.put(`/tasks/${id}`, taskData)
    return response.data
  },

  // Delete task
  async deleteTask(id) {
    await api.delete(`/tasks/${id}`)
  },

  // Status transitions
  async submitTask(id) {
    const response = await api.post(`/tasks/${id}/submit`)
    return response.data
  },

  async approveProcessing(id) {
    const response = await api.post(`/tasks/${id}/approve-processing`)
    return response.data
  },

  async disapproveTask(id) {
    const response = await api.post(`/tasks/${id}/disapprove`)
    return response.data
  },

  async approvePublication(id) {
    const response = await api.post(`/tasks/${id}/approve-publication`)
    return response.data
  },

  async publishTask(id) {
    const response = await api.post(`/tasks/${id}/publish`)
    return response.data
  },

  async rejectTask(id) {
    const response = await api.post(`/tasks/${id}/reject`)
    return response.data
  },

  // Get tasks by status
  async getTasksByStatus(status, limit = 100) {
    const response = await api.get(`/tasks/status/${status}`, {
      params: { limit },
    })
    return response.data
  },
}

export default api
