import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000, // 前端运行在 3000 端口
    open: true  // 启动时自动打开浏览器
  }
})