import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
const TOKEN_STORAGE_KEY = 'mv_auth_token'

let authToken = (() => {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch (_) {
    return null
  }
})()

let unauthorizedHandler = null

export function getStoredAuthToken() {
  return authToken
}

export function setAuthToken(token) {
  authToken = token
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token)
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
    }
  } catch (_) {
    // Ignore storage errors (private browsing, etc.)
  }
}

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler
}

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  if (authToken) {
    config.headers.Authorization = `Bearer ${authToken}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (authToken && error?.response?.status === 401 && typeof unauthorizedHandler === 'function') {
      unauthorizedHandler(error)
    }
    return Promise.reject(error)
  }
)

export const taskService = {
  // Get all tasks
  async getTasks(params = {}) {
    const { limit = 100, offset = 0, status, tenant_id } = params
    const requestParams = { limit, offset }
    if (status != null) requestParams.status = status
    if (tenant_id != null) requestParams.tenant_id = tenant_id
    const response = await api.get('/tasks', {
      params: requestParams,
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

  async overrideProcessing(id) {
    const response = await api.post(`/tasks/${id}/override-processing`)
    return response.data
  },

  // Get tasks by status
  async getTasksByStatus(status, limit = 100) {
    const response = await api.get(`/tasks/status/${status}`, {
      params: { limit },
    })
    return response.data
  },

  // Create job for a task
  async createJob(taskId, jobData) {
    const response = await api.post(`/tasks/${taskId}/jobs`, jobData)
    return response.data
  },

  // Update job for a task
  async updateJob(taskId, jobId, jobData) {
    const response = await api.put(`/tasks/${taskId}/jobs/${jobId}`, jobData)
    return response.data
  },

  // Delete job for a task
  async deleteJob(taskId, jobId) {
    await api.delete(`/tasks/${taskId}/jobs/${jobId}`)
  },

  // Process job for a task
  async processJob(taskId, jobId) {
    const response = await api.post(`/tasks/${taskId}/jobs/${jobId}/process`)
    return response.data
  },

  // Get template JSON structure
  async getTemplate(templateName) {
    const response = await api.get(`/templates/${templateName}`)
    return response.data
  },
}

export const tenantService = {
  async getTenants(params = {}) {
    const { limit = 100, offset = 0 } = params
    const response = await api.get('/tenants', { params: { limit, offset } })
    return response.data
  },

  async getDefaultTenant() {
    const response = await api.get('/tenants/default')
    return response.data
  },

  async getTenant(id) {
    const response = await api.get(`/tenants/${id}`)
    return response.data
  },

  async createTenant(data) {
    const response = await api.post('/tenants', data)
    return response.data
  },

  async updateTenant(id, data) {
    const response = await api.put(`/tenants/${id}`, data)
    return response.data
  },

  async deleteTenant(id) {
    await api.delete(`/tenants/${id}`)
  },
}

export const scheduleRuleService = {
  async getByTenant(tenantId) {
    const response = await api.get(`/tenants/${tenantId}/schedule-rules`)
    return response.data
  },

  async get(id) {
    const response = await api.get(`/schedule-rules/${id}`)
    return response.data
  },

  async create(data) {
    const response = await api.post('/schedule-rules', data)
    return response.data
  },

  async update(id, data) {
    const response = await api.put(`/schedule-rules/${id}`, data)
    return response.data
  },

  async delete(id) {
    await api.delete(`/schedule-rules/${id}`)
  },
}

export const authService = {
  async login(credentials) {
    const response = await api.post('/auth/login', credentials)
    return response.data
  },

  async getCurrentUser() {
    const response = await api.get('/auth/me')
    return response.data
  },
}

export default api
