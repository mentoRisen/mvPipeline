import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// When Nginx terminates TLS and proxies to this dev server, set on the VPS only, e.g.:
//   VITE_DEV_PUBLIC_HOST=flow.mentoverse.eu VITE_DEV_HMR_CLIENT_PORT=443
// Omit locally so HMR uses the default (same origin as the Vite URL).
const publicHost = process.env.VITE_DEV_PUBLIC_HOST
const hmrClientPort = parseInt(process.env.VITE_DEV_HMR_CLIENT_PORT || '443', 10)

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    strictPort: true,
    port: 3000,
    ...(publicHost
      ? {
          hmr: {
            protocol: 'wss',
            host: publicHost,
            clientPort: hmrClientPort,
          },
        }
      : {}),
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
