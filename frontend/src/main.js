import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import TasksView from './views/TasksView.vue'
import TaskDetail from './components/TaskDetail.vue'
import './style.css'

const routes = [
  // Main master-detail view
  { path: '/', component: TasksView },
  // Optional direct detail route (kept for deep links if you want it)
  { path: '/tasks/:id', component: TaskDetail, props: true },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const app = createApp(App)
app.use(router)
app.mount('#app')
