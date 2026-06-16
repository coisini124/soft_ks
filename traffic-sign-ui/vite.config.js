import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('echarts')) return 'charts'
          if (id.includes('element-plus') || id.includes('@element-plus')) return 'element'
          if (id.includes('vue')) return 'vue'
          if (id.includes('axios')) return 'http'
          return 'vendor'
        }
      }
    }
  }
})
