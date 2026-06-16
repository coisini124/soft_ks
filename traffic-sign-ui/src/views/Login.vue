<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <div class="logo-icon">🚦</div>
        <h1 class="system-title">交通标志智能管理系统</h1>
        <p class="system-subtitle">管理员登录</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            size="large"
            prefix-icon="User"
            clearable
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          style="width: 100%; margin-top: 8px;"
          :loading="loading"
          @click="handleLogin"
        >
          登 录
        </el-button>
      </el-form>

      <p class="hint">默认管理员账号：admin &nbsp;/&nbsp; 密码：admin123</p>
      <p class="register-link">
        没有账号？
        <el-link type="primary" @click="router.push('/register')">立即注册（驾驶员）</el-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api, { getErrorMessage } from '../api/client'

const router = useRouter()
const route = useRoute()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({ username: '', password: '' })

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const handleLogin = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const res = await api.post('/api/login', {
        username: form.username,
        password: form.password
      })
      localStorage.setItem('token', res.data.token)
      localStorage.setItem('username', res.data.username)
      localStorage.setItem('role', res.data.role)
      ElMessage.success('登录成功，欢迎回来！')
      const redirect = typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/')
        ? route.query.redirect
        : '/dashboard'
      router.push(redirect)
    } catch (err) {
      ElMessage.error(getErrorMessage(err, '登录失败，请检查网络'))
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a2a4a 0%, #0d1b2e 50%, #162035 100%);
}

.login-card {
  width: 420px;
  background: rgba(255, 255, 255, 0.97);
  border-radius: 12px;
  padding: 48px 40px 36px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.login-header {
  text-align: center;
  margin-bottom: 36px;
}

.logo-icon {
  font-size: 48px;
  line-height: 1;
  margin-bottom: 12px;
}

.system-title {
  font-size: 20px;
  font-weight: 700;
  color: #1a2a4a;
  margin: 0 0 6px;
  letter-spacing: 1px;
}

.system-subtitle {
  font-size: 14px;
  color: #909399;
  margin: 0;
}

.hint {
  text-align: center;
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 20px;
  margin-bottom: 0;
}

.register-link {
  text-align: center;
  font-size: 13px;
  color: #909399;
  margin-top: 12px;
  margin-bottom: 0;
}
</style>
