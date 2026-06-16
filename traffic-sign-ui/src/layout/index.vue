<template>
  <el-container class="layout-container">
    <el-aside width="220px" class="aside">
      <div class="logo">交通标志智能管理系统</div>
      <el-menu
        active-text-color="#409EFF"
        background-color="#304156"
        class="el-menu-vertical"
        text-color="#bfcbd9"
        :default-active="$route.path"
        router
      >
        <!-- 所有角色可见 -->
        <el-menu-item index="/dashboard">
          <el-icon><Monitor /></el-icon>
          <span>实时监控工作台</span>
        </el-menu-item>

        <!-- 所有角色可见：驾驶员查自己的记录，管理员查全量 -->
        <el-menu-item index="/records">
          <el-icon><Document /></el-icon>
          <span>历史检测记录</span>
        </el-menu-item>

        <el-menu-item index="/query">
          <el-icon><Search /></el-icon>
          <span>标志位置查询</span>
        </el-menu-item>

        <!-- 仅管理员可见 -->
        <template v-if="isAdmin">
          <el-menu-item index="/signs">
            <el-icon><Setting /></el-icon>
            <span>标志字典管理</span>
          </el-menu-item>
          <el-menu-item index="/analysis">
            <el-icon><PieChart /></el-icon>
            <span>数据分析可视化</span>
          </el-menu-item>
          <el-menu-item index="/audit-logs">
            <el-icon><Operation /></el-icon>
            <span>操作审计日志</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          欢迎使用系统
          <el-tag
            :type="isAdmin ? 'danger' : 'success'"
            size="small"
            style="margin-left: 10px;"
          >
            {{ isAdmin ? '管理员' : '驾驶员' }}
          </el-tag>
        </div>
        <div class="header-right">
          <el-avatar size="small" src="https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png" />
          <span style="margin-left: 10px;">{{ username }}</span>
          <el-button
            type="danger"
            link
            style="margin-left: 20px;"
            @click="handleLogout"
          >
            退出登录
          </el-button>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view></router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { Monitor, Document, Setting, PieChart, Search, Operation } from '@element-plus/icons-vue'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'

const router = useRouter()
const username = ref(localStorage.getItem('username') || '用户')
const role = ref(localStorage.getItem('role') || 'driver')
const isAdmin = computed(() => role.value === 'admin')

const handleLogout = () => {
  ElMessageBox.confirm('确定要退出登录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('role')
    ElMessage.success('已退出登录')
    router.push('/login')
  }).catch(() => {})
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}
.aside {
  background-color: #304156;
  color: white;
}
.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  font-size: 18px;
  font-weight: bold;
  color: #fff;
  border-bottom: 1px solid #1f2d3d;
}
.el-menu-vertical {
  border-right: none;
}
.header {
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  box-shadow: 0 1px 4px rgba(0,21,41,.08);
}
.header-right {
  display: flex;
  align-items: center;
}
.main-content {
  background-color: #f0f2f5;
  padding: 20px;
}
</style>
