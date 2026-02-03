<template>
  <div class="tenants-view">
    <section class="tenants-view-left">
      <TenantList
        ref="tenantList"
        :selected-tenant-id="selectedTenantId"
        @select-tenant="handleSelectTenant"
      />
    </section>
    <section class="tenants-view-right">
      <TenantDetail
        v-if="selectedTenantId"
        :id="selectedTenantId"
        :key="selectedTenantId"
        @tenant-deleted="handleTenantDeleted"
      />
      <div v-else class="placeholder card">
        <h3>Select a tenant</h3>
        <p>Choose a tenant from the list on the left, or click "Add Tenant" to create one.</p>
      </div>
    </section>
  </div>
</template>

<script>
import TenantList from '../components/TenantList.vue'
import TenantDetail from '../components/TenantDetail.vue'

export default {
  name: 'TenantsView',
  components: {
    TenantList,
    TenantDetail,
  },
  data() {
    return {
      selectedTenantId: null,
    }
  },
  methods: {
    handleSelectTenant(id) {
      this.selectedTenantId = id ? String(id) : null
    },
    handleTenantDeleted() {
      this.selectedTenantId = null
      if (this.$refs.tenantList) {
        this.$refs.tenantList.loadTenants()
      }
    },
  },
}
</script>

<style scoped>
.tenants-view {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1.8fr);
  gap: 1.5rem;
}

@media (max-width: 1024px) {
  .tenants-view {
    grid-template-columns: 1fr;
  }
}

.tenants-view-left {
  min-width: 0;
}

.tenants-view-right {
  min-width: 0;
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
