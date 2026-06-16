import { createRouter, createWebHistory } from 'vue-router'
import Layout from '../layout/index.vue'
import { ElMessage } from 'element-plus'
import api from '../api/client'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    redirect: '/dashboard',
    component: Layout,
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue')
      },
      {
        path: 'records',
        name: 'Records',
        component: () => import('../views/Records.vue')
      },
      {
        path: 'query',
        name: 'SignQuery',
        component: () => import('../views/SignQuery.vue')
      },
      {
        path: 'signs',
        name: 'Signs',
        component: () => import('../views/Signs.vue'),
        meta: { requiresAdmin: true }
      },
      {
        path: 'analysis',
        name: 'Analysis',
        component: () => import('../views/Analysis.vue'),
        meta: { requiresAdmin: true }
      },
      {
        path: 'audit-logs',
        name: 'AuditLogs',
        component: () => import('../views/AuditLogs.vue'),
        meta: { requiresAdmin: true }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const clearAuth = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  localStorage.removeItem('role')
}

let cachedProfile = null
let cachedToken = ''
let profileRequest = null

const loadCurrentProfile = async () => {
  const token = localStorage.getItem('token')
  if (!token) return null

  if (cachedProfile && cachedToken === token) {
    return cachedProfile
  }

  if (!profileRequest) {
    profileRequest = api.get('/api/me')
      .then(({ data }) => {
        cachedToken = token
        cachedProfile = data
        localStorage.setItem('username', data.username)
        localStorage.setItem('role', data.role)
        return data
      })
      .catch(error => {
        clearAuth()
        cachedToken = ''
        cachedProfile = null
        throw error
      })
      .finally(() => {
        profileRequest = null
      })
  }

  return profileRequest
}

// 导航守卫：未登录跳转登录页，管理页面以服务端 /api/me 返回的角色为准。
router.beforeEach(async (to) => {
  const token = localStorage.getItem('token')

  if (to.meta.public) {
    if (token && (to.path === '/login' || to.path === '/register')) {
      try {
        await loadCurrentProfile()
        return '/dashboard'
      } catch {
        clearAuth()
      }
    }
    return true
  }

  if (!token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  let profile = null
  try {
    profile = await loadCurrentProfile()
  } catch {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (to.matched.some(record => record.meta.requiresAdmin) && profile?.role !== 'admin') {
    ElMessage.error('权限不足，该页面仅管理员可访问')
    return '/dashboard'
  }

  return true
})

export default router
