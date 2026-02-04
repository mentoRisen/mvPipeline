<template>
  <div class="scheduler-view">
    <div v-if="!tenantId" class="placeholder card">
      <h3>Select a tenant</h3>
      <p>Choose a tenant from the header to manage schedule rules.</p>
    </div>

    <template v-else>
      <div class="scheduler-header card" style="display: flex; align-items: center; justify-content: space-between;">
        <div>
          <h2 style="margin: 0;">Schedule rules</h2>
        </div>
        <div>
          <button
            type="button"
            class="btn-primary"
            @click="startAdd"
          >
            Add
          </button>
        </div>
      </div>

      <div v-if="loading" class="loading">Loading rules...</div>
      <div v-else class="rules-list">
        <!-- New rule row (when adding) -->
        <div v-if="adding" class="rule-row card rule-row-edit">
          <div class="rule-col rule-col-left">
            <label>Action / Note</label>
            <div class="action-note-row">
              <select v-model="newRule.action" class="action-select">
                <option
                  v-for="opt in actionOptions"
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ opt.label }}
                </option>
              </select>
              <input
                v-model="newRule.note"
                type="text"
                class="note-input"
                placeholder="Optional note"
              />
            </div>
          </div>
          <div class="rule-col rule-col-middle">
            <div class="hour-and-days">
              <div class="hour-block">
                <label>Hour (00–23)</label>
                <select v-model.number="newRule.hour" class="hour-select">
                  <option v-for="h in hourOptions" :key="h" :value="h">{{ pad(h) }}</option>
                </select>
              </div>
              <div class="days-block">
                <label class="weekdays-label">Weekdays</label>
                <div class="weekdays">
                  <label
                    v-for="(day, idx) in weekdayLabels"
                    :key="idx"
                    class="weekday-checkbox"
                  >
                    <input v-model="newRule.days[idx]" type="checkbox" />
                    <span class="weekday-label">{{ day }}</span>
                  </label>
                </div>
              </div>
            </div>
          </div>
          <div class="rule-col rule-col-right">
            <button type="button" class="btn-primary btn-block" @click="createRule">Create</button>
            <button type="button" class="btn-secondary btn-block" @click="cancelAdd">Cancel</button>
          </div>
        </div>

        <!-- Existing rules -->
        <div
          v-for="rule in rules"
          :key="rule.id"
          class="rule-row card"
          :class="{ 'rule-row-edit': editingId === rule.id }"
        >
          <template v-if="editingId === rule.id">
            <div class="rule-col rule-col-left">
              <label>Action / Note</label>
              <div class="action-note-row">
                <select v-model="editForm.action" class="action-select">
                  <option
                    v-for="opt in actionOptions"
                    :key="opt.value"
                    :value="opt.value"
                  >
                    {{ opt.label }}
                  </option>
                </select>
                <input
                  v-model="editForm.note"
                  type="text"
                  class="note-input"
                  placeholder="Optional note"
                />
              </div>
            </div>
            <div class="rule-col rule-col-middle">
              <div class="hour-and-days">
                <div class="hour-block">
                  <label>Hour (00–23)</label>
                  <select v-model.number="editForm.hour" class="hour-select">
                    <option v-for="h in hourOptions" :key="h" :value="h">{{ pad(h) }}</option>
                  </select>
                </div>
                <div class="days-block">
                  <label class="weekdays-label">Weekdays</label>
                  <div class="weekdays">
                    <label
                      v-for="(day, idx) in weekdayLabels"
                      :key="idx"
                      class="weekday-checkbox"
                    >
                      <input v-model="editForm.days[idx]" type="checkbox" />
                      <span class="weekday-label">{{ day }}</span>
                    </label>
                  </div>
                </div>
              </div>
            </div>
            <div class="rule-col rule-col-right">
              <button type="button" class="btn-danger btn-block" @click="confirmDelete(rule)">Delete</button>
              <button type="button" class="btn-primary btn-block" @click="updateRule(rule.id)">Update</button>
            </div>
          </template>
          <template v-else>
            <div class="rule-col rule-col-left">
              <label>Action / Note</label>
              <div class="action-note-row action-note-row-display">
                <span class="rule-value">{{ actionLabel(rule.action) }}</span>
                <span v-if="rule.note" class="rule-value note-display">{{ rule.note }}</span>
              </div>
            </div>
            <div class="rule-col rule-col-middle">
              <label>Time</label>
              <span class="rule-value">{{ formatRuleTimes(rule.times) }}</span>
            </div>
            <div class="rule-col rule-col-right rule-actions-inline">
              <button type="button" class="btn-primary btn-small" @click="startEdit(rule)">Edit</button>
              <button type="button" class="btn-danger btn-small" @click="confirmDelete(rule)">Delete</button>
            </div>
          </template>
        </div>

        <p v-if="!loading && rules.length === 0 && !adding" class="muted empty-rules">
          No schedule rules yet. Click "Add" to create one.
        </p>
      </div>

      <!-- Delete confirmation -->
      <div v-if="ruleToDelete" class="modal-overlay" @click="ruleToDelete = null">
        <div class="modal-content card" @click.stop>
          <h3>Delete schedule rule?</h3>
          <p>Action: <strong>{{ actionLabel(ruleToDelete.action) }}</strong>. This cannot be undone.</p>
          <div class="form-actions">
            <button type="button" class="btn-secondary" @click="ruleToDelete = null">Cancel</button>
            <button type="button" class="btn-danger" @click="doDelete">Delete</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { tenantStore } from '../tenantStore'
import { scheduleRuleService } from '../services/api'

const ACTION_OPTIONS = [
  { value: 'testlog', label: 'Test log' },
  { value: 'publish_instagram', label: 'Publish Instagram' },
]

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
// Map weekday index (0=Mon..6=Sun) to cron-style day-of-week numbers (1=Mon..6=Sat, 0=Sun)
const CRON_DAYS = [1, 2, 3, 4, 5, 6, 0]

export default {
  name: 'SchedulerView',
  data() {
    return {
      actionOptions: ACTION_OPTIONS,
      weekdayLabels: WEEKDAYS,
      hourOptions: Array.from({ length: 24 }, (_, i) => i),
      rules: [],
      loading: false,
      adding: false,
      newRule: {
        action: 'testlog',
        hour: 9,
        days: [false, false, false, false, false, false, false],
      },
      editingId: null,
      editForm: {
        action: 'testlog',
        hour: 9,
        days: [false, false, false, false, false, false, false],
      },
      ruleToDelete: null,
    }
  },
  computed: {
    tenantId() {
      return tenantStore.state.id || null
    },
  },
  watch: {
    tenantId: {
      immediate: true,
      handler(id) {
        if (id) {
          this.loadRules()
        } else {
          this.rules = []
        }
        this.adding = false
        this.editingId = null
        this.ruleToDelete = null
      },
    },
  },
  methods: {
    pad(n) {
      return String(n).padStart(2, '0')
    },
    actionLabel(value) {
      const opt = ACTION_OPTIONS.find((o) => o.value === value)
      return opt ? opt.label : value
    },
    /** Build times JSON from hour + days (0=Mon .. 6=Sun) into {hour, days[]} using cron-style DOW. */
    buildTimes(hour, days) {
      const selectedDays = days
        .map((checked, idx) => (checked ? CRON_DAYS[idx] : null))
        .filter((v) => v !== null)
      return {
        hour,
        days: selectedDays,
      }
    },
    /** Parse times JSON from API into { hour, days[bool...] }. Supports both new {hour, days[]} and legacy arrays. */
    parseTimes(times) {
      if (!times) {
        return { hour: 9, days: [false, false, false, false, false, false, false] }
      }
      // New format: {hour, days: [cron-style]}
      if (!Array.isArray(times) && typeof times === 'object') {
        const hour = typeof times.hour === 'number' ? times.hour : 9
        const days = [false, false, false, false, false, false, false]
        const dowList = Array.isArray(times.days) ? times.days : []
        for (const dow of dowList) {
          const idx = CRON_DAYS.indexOf(dow)
          if (idx >= 0) days[idx] = true
        }
        return { hour, days }
      }

      // Legacy format: array of {day, hour}
      if (!Array.isArray(times) || times.length === 0) {
        return { hour: 9, days: [false, false, false, false, false, false, false] }
      }
      const first = times[0]
      const hour = typeof first.hour === 'number' ? first.hour : 9
      const days = [false, false, false, false, false, false, false]
      for (const t of times) {
        const d = typeof t.day === 'number' ? t.day : 0
        if (d >= 0 && d <= 6) days[d] = true
      }
      return { hour, days }
    },
    formatRuleTimes(times) {
      if (!times) return '—'
      const { hour, days } = this.parseTimes(times)
      const names = days.map((v, i) => (v ? WEEKDAYS[i] : null)).filter(Boolean)
      if (names.length === 0) return '—'
      return `${names.join(', ')} at ${this.pad(hour)}:00`
    },
    async loadRules() {
      if (!this.tenantId) return
      this.loading = true
      this.rules = []
      try {
        const data = await scheduleRuleService.getByTenant(this.tenantId)
        this.rules = Array.isArray(data) ? data : []
      } catch (e) {
        console.error('Failed to load schedule rules', e)
      } finally {
        this.loading = false
      }
    },
    startAdd() {
      this.adding = true
      this.editingId = null
      this.newRule = {
        action: 'testlog',
        hour: 9,
        days: [false, false, false, false, false, false, false],
        note: '',
      }
    },
    cancelAdd() {
      this.adding = false
    },
    async createRule() {
      const times = this.buildTimes(this.newRule.hour, this.newRule.days)
      try {
        const created = await scheduleRuleService.create({
          tenant_id: this.tenantId,
          action: this.newRule.action,
          note: this.newRule.note || null,
          times,
        })
        this.rules.push(created)
        this.adding = false
        this.newRule = {
          action: 'testlog',
          hour: 9,
          days: [false, false, false, false, false, false, false],
          note: '',
        }
      } catch (e) {
        console.error('Failed to create rule', e)
      }
    },
    startEdit(rule) {
      this.editingId = rule.id
      this.adding = false
      const { hour, days } = this.parseTimes(rule.times)
      this.editForm = {
        action: rule.action,
        hour,
        days: [...days],
        note: rule.note || '',
      }
    },
    cancelEdit() {
      this.editingId = null
    },
    async updateRule(ruleId) {
      const times = this.buildTimes(this.editForm.hour, this.editForm.days)
      try {
        const updated = await scheduleRuleService.update(ruleId, {
          action: this.editForm.action,
          note: this.editForm.note || null,
          times,
        })
        const idx = this.rules.findIndex((r) => r.id === ruleId)
        if (idx !== -1) this.rules.splice(idx, 1, updated)
        this.editingId = null
      } catch (e) {
        console.error('Failed to update rule', e)
      }
    },
    confirmDelete(rule) {
      this.ruleToDelete = rule
    },
    async doDelete() {
      if (!this.ruleToDelete) return
      const id = this.ruleToDelete.id
      this.ruleToDelete = null
      try {
        await scheduleRuleService.delete(id)
        this.rules = this.rules.filter((r) => r.id !== id)
        this.editingId = null
      } catch (e) {
        console.error('Failed to delete rule', e)
      }
    },
  },
}
</script>

<style scoped>
.scheduler-view {
  width: 100%;
  max-width: 100%;
}

.scheduler-header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.scheduler-header h2 {
  margin: 0 0 0.25rem 0;
  flex: 1 1 100%;
}

.scheduler-header .muted {
  margin: 0;
  flex: 1 1 100%;
}

.header-actions {
  margin-left: auto;
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.rule-row {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 1.5rem;
  align-items: start;
  width: 100%;
}

.rule-row-edit {
  align-items: start;
}

.rule-col {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.rule-col label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #6b7280;
}

.rule-col-left .action-select,
.rule-col-left .rule-value {
  width: 100%;
  max-width: 220px;
}

.action-note-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.action-note-row .action-select {
  max-width: 180px;
}

.note-input {
  flex: 1;
  min-width: 160px;
}

.action-note-row-display {
  align-items: center;
}

.note-display {
  color: #4b5563;
  font-style: italic;
}

.action-select,
.hour-select {
  padding: 0.5rem;
  font-size: 1rem;
  border-radius: 6px;
  border: 1px solid #ddd;
  background: white;
}

.rule-col-middle {
  flex: 1;
}

.hour-and-days {
  display: flex;
  align-items: flex-start;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.hour-block {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex-shrink: 0;
}

.hour-block .hour-select {
  width: 100%;
  max-width: 80px;
}

.days-block {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-width: 0;
}

.hour-select {
  width: 100%;
  max-width: 100px;
}

.weekdays-label {
  margin-top: 0;
}

.weekdays {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.weekday-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  padding: 0.6rem 0.9rem;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
  font-weight: 500;
  transition: border-color 0.2s, background 0.2s;
}

.weekday-checkbox:hover {
  border-color: #d1d5db;
  background: #f3f4f6;
}

.weekday-checkbox input {
  width: 1.2rem;
  height: 1.2rem;
  margin: 0;
  cursor: pointer;
}

.weekday-checkbox input:checked + .weekday-label {
  font-weight: 600;
}

.weekday-checkbox:has(input:checked) {
  border-color: #667eea;
  background: #eef2ff;
}

.weekday-label {
  font-size: 0.95rem;
  user-select: none;
}

.rule-col-right {
  flex-direction: column;
  gap: 0.75rem;
  min-width: 120px;
}

.btn-block {
  width: 100%;
  display: block;
}

.rule-col-right .btn-block:first-child {
  order: 1;
}

.rule-col-right .btn-block:last-child {
  order: 2;
}

.rule-row-edit .rule-col-right .btn-danger {
  order: 1;
}

.rule-row-edit .rule-col-right .btn-primary {
  order: 2;
}

.rule-actions-inline {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.rule-value {
  font-size: 0.95rem;
  word-break: break-word;
}

.empty-rules {
  padding: 1.5rem;
  text-align: center;
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
  min-width: 320px;
  max-width: 90vw;
}

.modal-content h3 {
  margin: 0 0 0.5rem 0;
}

.modal-content p {
  margin: 0 0 1rem 0;
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
}

.placeholder {
  padding: 2rem;
  text-align: center;
  color: #6b7280;
}

.placeholder h3 {
  margin-bottom: 0.5rem;
}
</style>
