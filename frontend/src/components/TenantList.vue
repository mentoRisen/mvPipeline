<template>
  <div class="tenant-list">
    <div class="tenant-list-header">
      <h2>Tenants</h2>
      <div class="header-actions">
        <button class="btn-primary" @click="addTenant">Add Tenant</button>
        <button class="btn-secondary" @click="loadTenants">Refresh</button>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading tenants...</div>

    <div v-else>
      <div class="tenant-list-table card">
        <div class="tenant-list-header-row">
          <div class="col-id">ID</div>
          <div class="col-name">Name</div>
          <div class="col-active">Active</div>
          <div class="col-links">Links</div>
        </div>
        <div
          v-for="tenant in tenants"
          :key="tenant.id"
          class="tenant-list-row"
          :class="{ 'row-selected': selectedTenantId === tenant.id }"
          @click="selectTenant(tenant.id)"
        >
          <div class="col-id">
            <span class="mono" :title="tenant.id">{{ String(tenant.id).slice(0, 8) }}</span>
          </div>
          <div class="col-name">{{ tenant.name || '—' }}</div>
          <div class="col-active">
            <span :class="['badge', tenant.is_active !== false ? 'badge-active' : 'badge-inactive']">
              {{ tenant.is_active !== false ? 'Active' : 'Inactive' }}
            </span>
          </div>
          <div class="col-links" @click.stop>
            <a
              v-if="tenant.facebook_page && isUrl(tenant.facebook_page)"
              :href="normalizeUrl(tenant.facebook_page)"
              target="_blank"
              rel="noopener noreferrer"
              class="link-small"
            >
              Facebook ↗
            </a>
            <span v-else class="muted">—</span>
          </div>
        </div>
        <div v-if="!loading && tenants.length === 0" class="empty-state">
          <p>No tenants. Click "Add Tenant" to create one.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { tenantService } from '../services/api'

export default {
  name: 'TenantList',
  props: {
    selectedTenantId: {
      type: String,
      default: null,
    },
  },
  data() {
    return {
      tenants: [],
      loading: false,
    }
  },
  mounted() {
    this.loadTenants()
  },
  methods: {
    async loadTenants() {
      this.loading = true
      try {
        const data = await tenantService.getTenants()
        this.tenants = Array.isArray(data) ? data : []
      } catch (e) {
        console.error('Failed to load tenants', e)
        this.tenants = []
      } finally {
        this.loading = false
      }
    },
    selectTenant(id) {
      this.$emit('select-tenant', id)
    },
    isUrl(s) {
      if (!s || typeof s !== 'string') return false
      const t = s.trim()
      return t.startsWith('http://') || t.startsWith('https://')
    },
    normalizeUrl(s) {
      const t = String(s).trim()
      if (t.startsWith('http://') || t.startsWith('https://')) return t
      return 'https://' + t
    },
    async addTenant() {
      const nextNum = this.tenants.length + 1
      const tenantId = `tenant-${Date.now()}`
      const name = `tenant${nextNum}`
      try {
        const created = await tenantService.createTenant({
          tenant_id: tenantId,
          name,
          description: null,
          env: null,
        })
        await this.loadTenants()
        this.$emit('select-tenant', created.id)
      } catch (e) {
        console.error('Failed to create tenant', e)
        alert('Failed to create tenant: ' + (e.response?.data?.detail || e.message))
      }
    },
  },
}
</script>

<style scoped>
.tenant-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.tenant-list-header h2 {
  margin: 0;
  font-size: 1.25rem;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

.tenant-list-table {
  padding: 0;
  overflow: hidden;
}

.tenant-list-header-row,
.tenant-list-row {
  display: grid;
  grid-template-columns: 80px 1fr 1fr 70px 80px;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  align-items: center;
}

.tenant-list-header-row {
  background: #f3f4f6;
  font-weight: 600;
  font-size: 0.85rem;
}

.tenant-list-row {
  border-bottom: 1px solid #eee;
  cursor: pointer;
}

.tenant-list-row:hover {
  background: #f9fafb;
}

.tenant-list-row.row-selected {
  background: #eef2ff;
}

.col-id {
  min-width: 0;
}

.col-name {
  min-width: 0;
}

.col-tenant-id {
  min-width: 0;
  font-size: 0.85rem;
  overflow: hidden;
  text-overflow: ellipsis;
}
.col-tenant-id .mono {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
}

.col-active {
  min-width: 0;
}

.col-links {
  min-width: 0;
}

.badge-active {
  background: #d1fae5;
  color: #065f46;
}

.badge-inactive {
  background: #f3f4f6;
  color: #6b7280;
}

.link-small {
  font-size: 0.85rem;
  color: #667eea;
  text-decoration: none;
}

.link-small:hover {
  text-decoration: underline;
}

.mono {
  font-family: ui-monospace, monospace;
  font-size: 0.85rem;
}

.muted {
  color: #6b7280;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #6b7280;
}

.loading {
  padding: 1rem;
  color: #6b7280;
}
</style>
