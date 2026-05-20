<template>
  <div class="register-page">
    <div class="register-card">
      <div class="register-header">
        <div class="logo-icon">🚗</div>
        <h1 class="system-title">交通标志智能管理系统</h1>
        <p class="system-subtitle">驾驶员注册</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleRegister"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请设置用户名（3-20位字母或数字）"
            size="large"
            prefix-icon="User"
            clearable
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请设置密码（至少6位）"
            size="large"
            prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            size="large"
            prefix-icon="Lock"
            show-password
            @keyup.enter="handleRegister"
          />
        </el-form-item>

        <el-alert
          title="注册账号默认为【驾驶员】角色，可使用实时检测功能。管理员账号由系统管理员分配。"
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 16px;"
        />

        <el-button
          type="primary"
          size="large"
          style="width: 100%;"
          :loading="loading"
          @click="handleRegister"
        >
          注 册
        </el-button>
      </el-form>

      <p class="login-link">
        已有账号？
        <el-link type="primary" @click="router.push('/login')">返回登录</el-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({ username: '', password: '', confirmPassword: '' })

const validateConfirmPwd = (rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度为 3-20 位', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]+$/, message: '只允许字母、数字和下划线', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPwd, trigger: 'blur' }
  ]
}

const handleRegister = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await axios.post('http://localhost:8000/api/register', {
        username: form.username,
        password: form.password,
        role: 'driver'
      })
      ElMessage.success('注册成功！请登录')
      router.push('/login')
    } catch (err) {
      const msg = err.response?.data?.detail || '注册失败，请稍后重试'
      ElMessage.error(msg)
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a2a4a 0%, #0d1b2e 50%, #162035 100%);
}

.register-card {
  width: 440px;
  background: rgba(255, 255, 255, 0.97);
  border-radius: 12px;
  padding: 48px 40px 36px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.register-header {
  text-align: center;
  margin-bottom: 32px;
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

.login-link {
  text-align: center;
  font-size: 13px;
  color: #909399;
  margin-top: 16px;
  margin-bottom: 0;
}
</style>
