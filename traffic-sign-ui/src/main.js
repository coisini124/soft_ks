import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import router from './router'
import App from './App.vue'
import axios from 'axios'

// 全局请求拦截：自动在 Authorization 头携带 token
axios.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

const app = createApp(App)
app.use(ElementPlus)
app.use(router)
app.mount('#app')