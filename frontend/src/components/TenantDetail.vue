<template>
  <div class="tenant-detail">
    <div v-if="loading" class="loading">Loading tenant...</div>
    <div v-else-if="tenant" class="tenant-form card">
      <div class="detail-header">
        <h2>Tenant</h2>
        <div class="header-actions">
          <button type="button" class="btn-primary" @click="save">Save</button>
          <button type="button" class="btn-danger" @click="confirmDelete">Delete</button>
          <button type="button" class="btn-secondary" @click="loadTenant">Refresh</button>
        </div>
      </div>

      <form @submit.prevent="save" class="form-fields">
        <div class="form-group">
          <label>Tenant ID (slug)</label>
          <div class="id-fields">
            <div>
              <label class="inline-label">UUID:</label>
              <input :value="form.id" type="text" readonly class="readonly uuid-input" />
            </div>
            <div>
              <label class="inline-label">Tenant ID:</label>
              <input v-model="form.tenant_id" type="text" readonly class="readonly" />
            </div>
          </div>
          <small class="muted">Unique identifier; cannot be changed after creation.</small>
        </div>
        <div class="form-group">
          <label>Name</label>
          <input v-model="form.name" type="text" required />
        </div>
        <div class="form-group">
          <label>Description</label>
          <textarea v-model="form.description" rows="2" placeholder="Optional description"></textarea>
        </div>
        <div class="form-group">
          <label>Instagram account</label>
          <input v-model="form.instagram_account" type="text" placeholder="e.g. @handle or account name" />
        </div>
        <div class="form-group">
          <label>Facebook page</label>
          <input v-model="form.facebook_page" type="url" placeholder="https://facebook.com/..." />
          <a
            v-if="form.facebook_page && isUrl(form.facebook_page)"
            :href="normalizeUrl(form.facebook_page)"
            target="_blank"
            rel="noopener noreferrer"
            class="link-external"
          >
            Open Facebook page ↗
          </a>
        </div>
        <div class="form-group form-group-inline">
          <label class="checkbox-label">
            <input v-model="form.is_active" type="checkbox" />
            Active
          </label>
          <small class="muted">Inactive tenants can be hidden from task creation.</small>
        </div>
        <div class="form-group">
          <label>Env (JSON)</label>
          <textarea
            v-model="form.envText"
            class="json-textarea"
            rows="12"
            spellcheck="false"
            placeholder='{"INSTAGRAM_ACCESS_TOKEN": "...", "INSTAGRAM_ACCOUNT_ID": "...", "PUBLIC_URL": "..."}'
          ></textarea>
          <small class="muted">Tenant-specific config, e.g. Instagram credentials, PUBLIC_URL.</small>
          <p v-if="envError" class="error-msg">{{ envError }}</p>
        </div>
        <div class="form-actions">
          <button type="submit" class="btn-primary">Save</button>
          <button type="button" class="btn-secondary" @click="resetForm">Reset</button>
        </div>
      </form>
    </div>
    <div v-else class="placeholder card">
      <h3>Tenant not found</h3>
      <p>Select a tenant from the list or add a new one.</p>
    </div>

    <!-- Delete confirmation -->
    <div v-if="showDeleteConfirm" class="modal-overlay" @click="showDeleteConfirm = false">
      <div class="modal-content" @click.stop>
        <h3>Delete tenant?</h3>
        <p>This will unlink all tasks from this tenant. The tenant will be removed.</p>
        <div class="form-actions">
          <button type="button" class="btn-secondary" @click="showDeleteConfirm = false">Cancel</button>
          <button type="button" class="btn-danger" @click="doDelete">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { tenantService } from '../services/api'

export default {
  name: 'TenantDetail',
  props: {
    id: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      tenant: null,
      loading: false,
      form: {
        id: '',
        tenant_id: '',
        name: '',
        description: '',
        instagram_account: '',
        facebook_page: '',
        is_active: true,
        envText: '{}',
      },
      envError: null,
      showDeleteConfirm: false,
    }
  },
  watch: {
    id: {
      immediate: true,
      handler(newId) {
        if (newId) this.loadTenant()
        else this.tenant = null
      },
    },
  },
  methods: {
    async loadTenant() {
      if (!this.id) return
      this.loading = true
      this.envError = null
      try {
        this.tenant = await tenantService.getTenant(this.id)
        this.syncFormFromTenant()
      } catch (e) {
        console.error('Failed to load tenant', e)
        this.tenant = null
      } finally {
        this.loading = false
      }
    },
    syncFormFromTenant() {
      if (!this.tenant) return
      this.form.id = this.tenant.id != null ? String(this.tenant.id) : ''
      this.form.tenant_id = this.tenant.tenant_id || ''
      this.form.name = this.tenant.name || ''
      this.form.description = this.tenant.description || ''
      this.form.instagram_account = this.tenant.instagram_account || ''
      this.form.facebook_page = this.tenant.facebook_page || ''
      this.form.is_active = this.tenant.is_active !== false
      this.form.envText =
        this.tenant.env != null
          ? JSON.stringify(this.tenant.env, null, 2)
          : '{}'
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
    resetForm() {
      this.syncFormFromTenant()
      this.envError = null
    },
    parseEnv() {
      this.envError = null
      if (!this.form.envText || !this.form.envText.trim()) return {}
      try {
        return JSON.parse(this.form.envText)
      } catch (e) {
        this.envError = 'Invalid JSON: ' + e.message
        return null
      }
    },
    async save() {
      const env = this.parseEnv()
      if (env === null) return
      try {
        await tenantService.updateTenant(this.id, {
          name: this.form.name,
          description: this.form.description || null,
          instagram_account: this.form.instagram_account || null,
          facebook_page: this.form.facebook_page || null,
          is_active: this.form.is_active,
          env: Object.keys(env).length ? env : null,
        })
        await this.loadTenant()
      } catch (e) {
        console.error('Failed to save tenant', e)
        alert('Failed to save: ' + (e.response?.data?.detail || e.message))
      }
    },
    confirmDelete() {
      this.showDeleteConfirm = true
    },
    async doDelete() {
      try {
        await tenantService.deleteTenant(this.id)
        this.showDeleteConfirm = false
        this.$emit('tenant-deleted', this.id)
      } catch (e) {
        console.error('Failed to delete tenant', e)
        alert('Failed to delete: ' + (e.response?.data?.detail || e.message))
      }
    },
  },
}
</script>

<style scoped>
.tenant-detail {
  min-width: 0;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.detail-header h2 {
  margin: 0;
  font-size: 1.25rem;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

.form-fields {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.form-group label {
  font-weight: 600;
  font-size: 0.9rem;
}

.form-group .readonly {
  background: #f3f4f6;
  color: #6b7280;
}

.form-group small.muted {
  font-size: 0.8rem;
  color: #6b7280;
}

.form-group .error-msg {
  font-size: 0.85rem;
  color: #dc2626;
  margin-top: 0.25rem;
}

.form-group-inline .checkbox-label {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: normal;
  cursor: pointer;
}

.form-group-inline .checkbox-label input[type="checkbox"] {
  width: auto;
}

.link-external {
  font-size: 0.9rem;
  color: #667eea;
  margin-top: 0.25rem;
  display: inline-block;
}

.link-external:hover {
  text-decoration: underline;
}

.json-textarea {
  font-family: ui-monospace, monospace;
  font-size: 0.85rem;
}

.form-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.placeholder {
  padding: 2rem;
  text-align: center;
  color: #6b7280;
}

.placeholder h3 {
  margin-bottom: 0.5rem;
}

.loading {
  padding: 1rem;
  color: #6b7280;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  max-width: 400px;
  width: 90%;
}

.modal-content h3 {
  margin-bottom: 0.5rem;
}

.modal-content p {
  margin-bottom: 1rem;
  color: #6b7280;
}
</style>
