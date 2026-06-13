/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const devProxyTarget = process.env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['lucide-react'],
    include: ['react-window'],
    esbuildOptions: {
      target: 'es2020',
    },
  },
  server: {
    // OneDrive / cloud-sync folders on macOS often miss native FS events; polling keeps HMR reliable.
    watch: {
      usePolling: true,
      interval: 1000,
    },
    proxy: {
      '/api': {
        target: devProxyTarget,
        changeOrigin: true,
        secure: false,
        timeout: 600000,
        proxyTimeout: 600000,
      },
      '/health': {
        target: devProxyTarget,
        changeOrigin: true,
        secure: false,
        timeout: 600000,
        proxyTimeout: 600000,
      }
    }
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
  },
  // Bundle large dependencies into a separate vendor chunk
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['xlsx', 'html2canvas', 'jspdf']
        }
      }
    }
  }
});
