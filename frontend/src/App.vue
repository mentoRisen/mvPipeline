<template>
  <div id="app">
    <header class="app-header">
      <h1>Mentoverse Pipeline</h1>
      <nav>
        <router-link to="/" class="nav-link">Tasks</router-link>
        <router-link to="/tenants" class="nav-link">Tenants</router-link>
      </nav>
      <div class="header-tenant">
        <button
          type="button"
          class="tenant-bubble"
          :class="{ 'tenant-bubble-empty': !tenantStore.state.name }"
          @click="showTenantPicker = true"
          :title="tenantStore.state.name ? 'Change tenant' : 'Select tenant'"
        >
          {{ tenantStore.state.name || 'Select tenant' }}
        </button>
      </div>
    </header>

    <!-- Tenant picker popup -->
    <div v-if="showTenantPicker" class="tenant-picker-overlay" @click="showTenantPicker = false">
      <div class="tenant-picker-popup card" @click.stop>
        <h3>Select tenant</h3>
        <p v-if="pickerLoading" class="muted">Loading tenants...</p>
        <ul v-else class="tenant-picker-list">
          <li
            v-for="t in pickerTenants"
            :key="t.id"
            class="tenant-picker-item"
            :class="{ 'tenant-picker-item-active': tenantStore.state.id === t.id }"
            @click="pickTenant(t)"
          >
            <span class="tenant-picker-name">{{ t.name || t.tenant_id }}</span>
            <span v-if="!t.is_active" class="tenant-picker-inactive">Inactive</span>
          </li>
        </ul>
        <p v-if="!pickerLoading && pickerTenants.length === 0" class="muted">No tenants. Create one under Tenants.</p>
        <div class="tenant-picker-actions">
          <button type="button" class="btn-secondary" @click="showTenantPicker = false">Close</button>
        </div>
      </div>
    </div>

    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script>
import { tenantStore } from './tenantStore'
import { tenantService } from './services/api'

export default {
  name: 'App',
  data() {
    return {
      tenantStore,
      showTenantPicker: false,
      pickerTenants: [],
      pickerLoading: false,
    }
  },
  mounted() {
    this.ensureTenantSelected()
  },
  watch: {
    showTenantPicker(visible) {
      if (visible) this.loadTenantsForPicker()
    },
  },
  methods: {
    async ensureTenantSelected() {
      // If a tenant is already selected (e.g., from localStorage), keep it
      if (this.tenantStore.state.id) return
      try {
        const t = await tenantService.getDefaultTenant()
        tenantStore.setCurrentTenant(t.id, t.name || t.tenant_id || 'Tenant')
      } catch (e) {
        // No tenants or API error - user can pick/create later
        console.error('Failed to get default tenant', e)
      }
    },
    async loadTenantsForPicker() {
      this.pickerLoading = true
      this.pickerTenants = []
      try {
        const data = await tenantService.getTenants()
        this.pickerTenants = Array.isArray(data) ? data : []
      } catch (e) {
        console.error('Failed to load tenants for picker', e)
      } finally {
        this.pickerLoading = false
      }
    },
    pickTenant(t) {
      tenantStore.setCurrentTenant(t.id, t.name || t.tenant_id || 'Tenant')
      this.showTenantPicker = false
    },
  },
}
</script>

<style scoped>
.header-tenant {
  display: flex;
  align-items: center;
  margin-left: 1rem;
}

.tenant-bubble {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.4);
  padding: 0.4rem 0.9rem;
  border-radius: 999px;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tenant-bubble:hover {
  background: rgba(255, 255, 255, 0.3);
}

.tenant-bubble-empty {
  font-style: italic;
  opacity: 0.9;
}

.tenant-picker-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.tenant-picker-popup {
  min-width: 280px;
  max-width: 90vw;
  max-height: 80vh;
  overflow: auto;
}

.tenant-picker-popup h3 {
  margin: 0 0 1rem 0;
  font-size: 1.1rem;
}

.tenant-picker-list {
  list-style: none;
  padding: 0;
  margin: 0 0 1rem 0;
}

.tenant-picker-item {
  padding: 0.6rem 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tenant-picker-item:hover {
  background: #f3f4f6;
}

.tenant-picker-item-active {
  background: #eef2ff;
  font-weight: 600;
}

.tenant-picker-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tenant-picker-inactive {
  font-size: 0.75rem;
  color: #6b7280;
  margin-left: 0.5rem;
}

.tenant-picker-actions {
  display: flex;
  justify-content: flex-end;
}

.muted {
  color: #6b7280;
  font-size: 0.9rem;
  margin: 0.5rem 0;
}
</style>
