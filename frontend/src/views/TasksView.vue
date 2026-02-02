<template>
  <div class="tasks-view">
    <section class="tasks-view-left">
      <TaskList
        ref="taskList"
        :selected-task-id="selectedTaskId"
        @select-task="handleSelectTask"
      />
    </section>
    <section class="tasks-view-right">
      <TaskDetail
        v-if="selectedTaskId"
        :id="selectedTaskId"
        :key="selectedTaskId"
        @task-deleted="handleTaskDeleted"
      />
      <div v-else class="placeholder card">
        <h3>Select a task</h3>
        <p>Choose a task from the list on the left to see its details here.</p>
      </div>
    </section>
  </div>
</template>

<script>
import TaskList from '../components/TaskList.vue'
import TaskDetail from '../components/TaskDetail.vue'

export default {
  name: 'TasksView',
  components: {
    TaskList,
    TaskDetail,
  },
  data() {
    return {
      selectedTaskId: null,
    }
  },
  methods: {
    handleSelectTask(id) {
      // Ensure ID is a string and update selected task
      this.selectedTaskId = String(id)
    },
    handleTaskDeleted(taskId) {
      // Clear selection and refresh task list
      this.selectedTaskId = null
      if (this.$refs.taskList) {
        this.$refs.taskList.loadTasks()
      }
    },
  },
}
</script>

<style scoped>
.tasks-view {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1.8fr);
  gap: 1.5rem;
}

@media (max-width: 1024px) {
  .tasks-view {
    grid-template-columns: 1fr;
  }
}

.tasks-view-left {
  min-width: 0;
}

.tasks-view-right {
  min-width: 0;
}
</style>

