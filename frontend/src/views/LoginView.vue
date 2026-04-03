<template>
  <div class="login-view">
    <div class="login-brand">
      <img
        :src="logoUrl"
        alt="mentoFlow"
        class="login-logo"
        width="320"
        height="320"
      />
    </div>
    <AppCard quiet class="login-card">
      <form @submit.prevent="handleLogin">
        <h2 class="login-title">Sign in</h2>
        <p class="muted login-hint">Use the credentials provided by your administrator.</p>

        <TextInput
          v-model="form.username"
          label="Username"
          type="text"
          required
          autocomplete="username"
        />
        <TextInput
          v-model="form.password"
          label="Password"
          type="password"
          required
          autocomplete="current-password"
        />

        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

        <PrimaryButton type="submit" block size="lg" :disabled="isLoading">
          {{ isLoading ? 'Signing in…' : 'Sign in' }}
        </PrimaryButton>
      </form>
    </AppCard>
  </div>
</template>

<script>
import { authStore } from '../authStore'
import logoUrl from '../assets/mento-flow-logo.png'
import { AppCard, PrimaryButton, TextInput } from '../components/ui'

export default {
  name: 'LoginView',
  components: { AppCard, PrimaryButton, TextInput },
  data() {
    return {
      logoUrl,
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
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: var(--space-8) var(--space-4);
  gap: var(--space-8);
  background-color: var(--color-bg);
  background-image: radial-gradient(
      ellipse 140% 90% at 50% -30%,
      rgba(49, 46, 129, 0.09),
      transparent 55%
    ),
    radial-gradient(ellipse 80% 60% at 100% 100%, rgba(34, 211, 238, 0.06), transparent 45%),
    linear-gradient(180deg, var(--color-surface-alt) 0%, var(--color-bg) 38%);
}

.login-card {
  width: 100%;
  max-width: 420px;
}

.login-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  flex-shrink: 0;
}

.login-logo {
  width: min(320px, 72vw);
  height: auto;
  object-fit: contain;
  filter: drop-shadow(0 12px 40px rgba(49, 46, 129, 0.2));
}

.login-tagline {
  margin: 0;
  font-size: var(--text-lg);
  letter-spacing: 0.02em;
}

.login-tagline :deep(.mf-brand-mento) {
  color: var(--color-text-muted);
  opacity: 1;
}

.login-tagline :deep(.mf-brand-flow) {
  color: var(--color-primary);
}

.login-title {
  margin: 0 0 var(--space-2) 0;
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  letter-spacing: -0.03em;
}

.login-hint {
  margin: 0 0 var(--space-6) 0;
}

.error-text {
  color: var(--color-error);
  font-size: var(--text-sm);
  margin: calc(var(--space-2) * -1) 0 var(--space-4) 0;
}

.login-card :deep(.mf-btn--block) {
  margin-top: var(--space-5);
}
</style>
