<template>
  <div id="app">
    <header class="app-header">
      <h1>Task Management Admin</h1>
      <nav>
        <router-link to="/" class="nav-link">Tasks</router-link>
      </nav>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script>
export default {
  name: 'App'
}
</script>
