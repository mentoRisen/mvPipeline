<template>
  <div class="prompts-view">
    <div v-if="!tenantId" class="placeholder card">
      <h3>Select a tenant</h3>
      <p>Choose a tenant from the header to view and edit prompts.</p>
    </div>

    <template v-else>
      <div class="prompts-header card prompts-header-bar">
        <h2 style="margin: 0;">Prompts</h2>
        <div class="prompts-header-actions">
          <button type="button" class="btn-primary" :disabled="!!editingId || adding" @click="startAdd">
            Add prompt
          </button>
          <button type="button" class="btn-pink" @click="loadPrompts">Refresh</button>
        </div>
      </div>

      <div v-if="error" class="error-banner">{{ error }}</div>
      <div v-if="loading" class="loading">Loading prompts...</div>

      <div v-else class="prompts-body">
        <div v-if="adding" class="card prompt-form-card">
          <h3>New prompt</h3>
          <div class="form-row">
            <label for="new-prompt-name">Name</label>
            <input
              id="new-prompt-name"
              v-model="newForm.name"
              type="text"
              maxlength="200"
              class="text-input"
              placeholder="Short label for this prompt"
            />
          </div>
          <div class="form-row">
            <label for="new-prompt-type">Type</label>
            <select id="new-prompt-type" v-model="newForm.type" class="status-filter">
              <option v-for="opt in typeOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>
          <div class="form-row">
            <label for="new-prompt-body">Prompt text</label>
            <textarea
              id="new-prompt-body"
              v-model="newForm.body"
              class="prompt-textarea"
              rows="10"
              placeholder="Long-form instructions"
            />
          </div>
          <div class="form-actions">
            <button type="button" class="btn-primary" @click="createPrompt">Save</button>
            <button type="button" class="btn-secondary" @click="cancelAdd">Cancel</button>
          </div>
        </div>

        <div v-if="prompts.length > 0" class="card prompts-table-card">
          <table class="prompts-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Preview</th>
                <th>Updated</th>
                <th class="actions-col">Actions</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="row in prompts" :key="row.id">
                <tr v-if="editingId !== row.id">
                  <td class="name-col">{{ row.name }}</td>
                  <td><span class="badge badge-muted">{{ typeLabel(row.type) }}</span></td>
                  <td class="preview-col">{{ row.body_preview }}</td>
                  <td class="updated-col">{{ formatDate(row.updated_at) }}</td>
                  <td class="actions-col">
                    <div class="prompt-row-actions">
                      <button type="button" class="btn-secondary" @click="startEdit(row)">Edit</button>
                      <button type="button" class="btn-danger" @click="confirmDelete(row)">Delete</button>
                    </div>
                  </td>
                </tr>
                <tr v-else class="edit-row">
                  <td colspan="5">
                    <div class="edit-row-inner">
                      <h3>Edit prompt</h3>
                      <div class="form-row">
                        <label :for="'edit-name-' + row.id">Name</label>
                        <input
                          :id="'edit-name-' + row.id"
                          v-model="editForm.name"
                          type="text"
                          maxlength="200"
                          class="text-input"
                        />
                      </div>
                      <div class="form-row">
                        <label :for="'edit-type-' + row.id">Type</label>
                        <select :id="'edit-type-' + row.id" v-model="editForm.type" class="status-filter">
                          <option v-for="opt in typeOptions" :key="opt.value" :value="opt.value">
                            {{ opt.label }}
                          </option>
                        </select>
                      </div>
                      <div class="form-row">
                        <label :for="'edit-body-' + row.id">Prompt text</label>
                        <textarea
                          :id="'edit-body-' + row.id"
                          v-model="editForm.body"
                          class="prompt-textarea"
                          rows="10"
                        />
                      </div>
                      <div class="form-actions">
                        <button type="button" class="btn-primary" @click="saveEdit">Save</button>
                        <button type="button" class="btn-secondary" @click="cancelEdit">Cancel</button>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <div v-if="!loading && prompts.length === 0 && !adding" class="empty-state card">
          <p>No prompts yet. Add one to store task-creation instructions for this tenant.</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { tenantStore } from '../tenantStore'
import { promptService } from '../services/api'

const TYPE_OPTIONS = [
  { value: 'task-creation', label: 'Tasks Creation' },
  { value: 'master-prompt', label: 'Master Prompt' },
]

export default {
  name: 'PromptsView',
  data() {
    return {
      tenantStore,
      prompts: [],
      loading: false,
      error: null,
      adding: false,
      editingId: null,
      newForm: {
        name: '',
        type: 'task-creation',
        body: '',
      },
      editForm: {
        name: '',
        type: 'task-creation',
        body: '',
      },
      typeOptions: TYPE_OPTIONS,
    }
  },
  computed: {
    tenantId() {
      return this.tenantStore.currentTenantId
    },
  },
  watch: {
    tenantId() {
      this.cancelAdd()
      this.cancelEdit()
      this.loadPrompts()
    },
  },
  mounted() {
    this.loadPrompts()
  },
  methods: {
    typeLabel(value) {
      const o = TYPE_OPTIONS.find((x) => x.value === value)
      return o ? o.label : value
    },
    formatDate(iso) {
      if (!iso) return ''
      try {
        return new Date(iso).toLocaleString()
      } catch (_) {
        return String(iso)
      }
    },
    async loadPrompts() {
      if (!tenantStore.currentTenantId) {
        this.prompts = []
        this.loading = false
        this.error = null
        return
      }
      this.loading = true
      this.error = null
      try {
        this.prompts = await promptService.list()
      } catch (err) {
        this.error = err.response?.data?.detail || err.message || 'Failed to load prompts'
        this.prompts = []
      } finally {
        this.loading = false
      }
    },
    startAdd() {
      this.editingId = null
      this.adding = true
      this.newForm = { name: '', type: 'task-creation', body: '' }
      this.error = null
    },
    cancelAdd() {
      this.adding = false
    },
    async createPrompt() {
      if (!this.newForm.name?.trim()) {
        this.error = 'Name is required'
        return
      }
      if (!this.newForm.body?.trim()) {
        this.error = 'Prompt text is required'
        return
      }
      this.error = null
      try {
        await promptService.create({
          name: this.newForm.name.trim(),
          type: this.newForm.type,
          body: this.newForm.body,
        })
        this.adding = false
        await this.loadPrompts()
      } catch (err) {
        this.error = err.response?.data?.detail || err.message || 'Failed to create prompt'
      }
    },
    async startEdit(row) {
      this.adding = false
      this.error = null
      try {
        const full = await promptService.get(row.id)
        this.editingId = row.id
        this.editForm = {
          name: full.name,
          type: full.type,
          body: full.body,
        }
      } catch (err) {
        this.error = err.response?.data?.detail || err.message || 'Failed to load prompt'
      }
    },
    cancelEdit() {
      this.editingId = null
    },
    async saveEdit() {
      if (!this.editForm.name?.trim()) {
        this.error = 'Name is required'
        return
      }
      if (!this.editForm.body?.trim()) {
        this.error = 'Prompt text is required'
        return
      }
      this.error = null
      try {
        await promptService.update(this.editingId, {
          name: this.editForm.name.trim(),
          type: this.editForm.type,
          body: this.editForm.body,
        })
        this.editingId = null
        await this.loadPrompts()
      } catch (err) {
        this.error = err.response?.data?.detail || err.message || 'Failed to update prompt'
      }
    },
    confirmDelete(row) {
      if (!window.confirm(`Delete prompt "${row.name}"?`)) return
      this.deletePrompt(row.id)
    },
    async deletePrompt(id) {
      this.error = null
      try {
        await promptService.delete(id)
        if (this.editingId === id) this.editingId = null
        await this.loadPrompts()
      } catch (err) {
        this.error = err.response?.data?.detail || err.message || 'Failed to delete prompt'
      }
    },
  },
}
</script>

<style scoped>
.prompts-view {
  max-width: 960px;
  margin: 0 auto;
}

.prompts-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.prompts-header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.error-banner {
  background: rgba(220, 53, 69, 0.12);
  color: #842029;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.prompt-form-card {
  margin-bottom: 1rem;
}

.prompts-table-card {
  padding: 0;
  overflow: hidden;
}

.prompts-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}

.prompts-table thead th {
  text-align: left;
  padding: 0.65rem 0.75rem;
  border-bottom: 1px solid var(--border-subtle, #e5e7eb);
  background: #f8fafc;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: #475569;
}

.prompts-table tbody td {
  padding: 0.55rem 0.75rem;
  border-bottom: 1px solid var(--border-subtle, #eef2f7);
  vertical-align: top;
}

.prompts-table tbody tr:last-child td {
  border-bottom: none;
}

.name-col {
  font-weight: 600;
  max-width: 220px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.preview-col {
  color: #475569;
  max-width: 420px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.updated-col {
  white-space: nowrap;
  color: #6b7280;
}

.actions-col {
  width: 1%;
  white-space: nowrap;
}

.edit-row td {
  background: #fafcff;
}

.edit-row-inner {
  padding: 0.5rem 0;
}

.edit-row-inner h3 {
  margin: 0 0 0.75rem;
  font-size: 1rem;
}

.prompt-row-actions {
  display: flex;
  gap: 0.5rem;
}

.form-row {
  margin-bottom: 1rem;
}

.form-row label {
  display: block;
  margin-bottom: 0.35rem;
  font-weight: 600;
  font-size: 0.9rem;
}

.text-input {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  padding: 0.5rem 0.65rem;
  border-radius: 6px;
  border: 1px solid var(--border-subtle, #ccc);
  background: var(--input-bg, #fff);
  color: inherit;
}

.prompt-textarea {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  padding: 0.5rem 0.65rem;
  border-radius: 6px;
  border: 1px solid var(--border-subtle, #ccc);
  font-family: inherit;
  font-size: 0.95rem;
  resize: vertical;
  background: var(--input-bg, #fff);
  color: inherit;
}

.form-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.badge-muted {
  margin-left: 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: none;
}

.btn-danger {
  background: #dc3545;
  color: #fff;
  border: none;
  padding: 0.45rem 0.85rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}

.btn-danger:hover {
  filter: brightness(0.95);
}
</style>
