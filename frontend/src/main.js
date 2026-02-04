import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import TasksView from './views/TasksView.vue'
import TenantsView from './views/TenantsView.vue'
import SchedulerView from './views/SchedulerView.vue'
import TaskDetail from './components/TaskDetail.vue'
import LoginView from './views/LoginView.vue'
import { authStore } from './authStore'
import './style.css'

const routes = [
  { path: '/', component: TasksView },
  { path: '/tenants', component: TenantsView },
  { path: '/scheduler', component: SchedulerView },
  { path: '/tasks/:id', component: TaskDetail, props: true },
  {
    path: '/login',
    component: LoginView,
    meta: { public: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  await authStore.bootstrap()
  if (!authStore.isAuthenticated() && !to.meta?.public) {
    if (to.path !== '/login') {
      return {
        path: '/login',
        query: { redirect: to.fullPath },
      }
    }
    return true
  }

  if (authStore.isAuthenticated() && to.path === '/login') {
    return { path: '/' }
  }

  return true
})

const app = createApp(App)
app.use(router)
app.mount('#app')
