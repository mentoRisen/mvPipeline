<template>
  <div class="login-view">
    <form class="card login-card" @submit.prevent="handleLogin">
      <h2>Sign in</h2>
      <p class="muted">Use the credentials provided by your administrator.</p>

      <label class="form-field">
        <span>Username</span>
        <input v-model="form.username" type="text" required autocomplete="username" />
      </label>

      <label class="form-field">
        <span>Password</span>
        <input v-model="form.password" type="password" required autocomplete="current-password" />
      </label>

      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

      <button type="submit" class="btn-primary" :disabled="isLoading">
        {{ isLoading ? 'Signing in…' : 'Sign in' }}
      </button>
    </form>
  </div>
</template>

<script>
import { authStore } from '../authStore'

export default {
  name: 'LoginView',
  data() {
    return {
      authStore,
      form: {
        username: '',
        password: '',
      },
      localError: null,
    }
  },
  computed: {
    isLoading() {
      return this.authStore.state.loading
    },
    errorMessage() {
      return this.localError || this.authStore.state.error
    },
  },
  methods: {
    async handleLogin() {
      if (!this.form.username || !this.form.password) return
      this.localError = null
      try {
        await this.authStore.login(this.form.username.trim(), this.form.password)
        const redirect = this.$route.query.redirect || '/'
        this.$router.replace(redirect)
      } catch (error) {
        this.localError = error?.response?.data?.detail || 'Invalid username or password'
      }
    },
  },
}
</script>

<style scoped>
.login-view {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, #1f2937, #4b5563);
  padding: 2rem;
}

.login-card {
  width: 100%;
  max-width: 420px;
}

.form-field {
  display: flex;
  flex-direction: column;
  margin-bottom: 1rem;
  font-weight: 500;
  color: #374151;
}

.form-field input {
  margin-top: 0.35rem;
  padding: 0.65rem 0.8rem;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  font-size: 1rem;
}

.btn-primary {
  width: 100%;
  padding: 0.75rem;
  font-size: 1rem;
  border-radius: 6px;
}

.error-text {
  color: #b91c1c;
  margin-bottom: 1rem;
}
</style>
