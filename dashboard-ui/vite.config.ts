import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    outDir: '../justpipe/dashboard/static',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          elkjs: ['elkjs/lib/elk.bundled.js'],
          pixijs: ['pixi.js'],
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:4242',
    },
  },
})
