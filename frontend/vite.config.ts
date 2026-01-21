import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0', // 明确指定监听所有接口
      port: 3000,
      strictPort: true, // 如果端口被占用则退出
      // 允许 Nginx 反向代理访问
      allowedHosts: ['frontend', 'localhost', '127.0.0.1', 'klandlz.com', 'www.klandlz.com'],
      proxy: {
        '/api': {
          target: env.VITE_API_TARGET || 'http://backend:8000',
          changeOrigin: true,
        }
      }
    }
  }
})
