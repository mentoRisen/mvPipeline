import { reactive } from 'vue'
import {
  authService,
  getStoredAuthToken,
  setAuthToken,
  setUnauthorizedHandler,
} from './services/api'
import { tenantStore } from './tenantStore'

const USER_STORAGE_KEY = 'mv_auth_user'

function loadStoredUser() {
  try {
    const raw = localStorage.getItem(USER_STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch (_) {
    return null
  }
}

function persistUser(user) {
  try {
    if (user) {
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user))
    } else {
      localStorage.removeItem(USER_STORAGE_KEY)
    }
  } catch (_) {}
}

const state = reactive({
  token: getStoredAuthToken(),
  user: loadStoredUser(),
  initialized: false,
  loading: false,
  error: null,
})

async function bootstrap() {
  if (state.initialized) return
  if (state.token && !state.user) {
    try {
      state.user = await authService.getCurrentUser()
      persistUser(state.user)
    } catch (error) {
      console.warn('Failed to refresh session, logging out', error)
      logout()
    }
  }
  state.initialized = true
}

async function login(username, password) {
  state.loading = true
  state.error = null
  try {
    const data = await authService.login({ username, password })
    state.token = data.access_token
    state.user = data.user
    persistUser(data.user)
    setAuthToken(data.access_token)
    return data.user
  } catch (error) {
    const message = error?.response?.data?.detail || 'Login failed'
    state.error = message
    throw error
  } finally {
    state.loading = false
  }
}

function logout() {
  state.token = null
  state.user = null
  state.error = null
  persistUser(null)
  setAuthToken(null)
  tenantStore.clearCurrentTenant()
}

function isAuthenticated() {
  return Boolean(state.token)
}

setUnauthorizedHandler(() => {
  logout()
})

export const authStore = {
  state,
  bootstrap,
  login,
  logout,
  isAuthenticated,
}
