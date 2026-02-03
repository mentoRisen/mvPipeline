import { reactive } from 'vue'

const STORAGE_KEY = 'mentoverse_current_tenant'

const state = reactive({
  id: null,
  name: null,
})

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const data = JSON.parse(raw)
    if (data && (data.id || data.name)) {
      state.id = data.id || null
      state.name = data.name || null
    }
  } catch (_) {
    state.id = null
    state.name = null
  }
}

function setCurrentTenant(id, name) {
  state.id = id
  state.name = name
  try {
    if (id && name) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ id, name }))
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  } catch (_) {}
}

function clearCurrentTenant() {
  state.id = null
  state.name = null
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch (_) {}
}

// Load once on module init
loadFromStorage()

export const tenantStore = {
  get state() {
    return state
  },
  get currentTenantId() {
    return state.id
  },
  get currentTenantName() {
    return state.name
  },
  setCurrentTenant,
  clearCurrentTenant,
  loadFromStorage,
}
