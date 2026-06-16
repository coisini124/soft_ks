<template>
  <div class="audit-page">
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="操作人">
          <el-input
            v-model="filters.username"
            clearable
            placeholder="用户名"
            style="width: 160px"
            @keyup.enter="fetchLogs"
          />
        </el-form-item>
        <el-form-item label="动作">
          <el-select v-model="filters.action" clearable placeholder="全部动作" style="width: 150px">
            <el-option label="新增" value="create" />
            <el-option label="更新" value="update" />
            <el-option label="删除" value="delete" />
            <el-option label="导入" value="import" />
            <el-option label="处理状态" value="update_status" />
            <el-option label="重建报表" value="rebuild" />
            <el-option label="清理存储" value="cleanup" />
          </el-select>
        </el-form-item>
        <el-form-item label="对象">
          <el-select v-model="filters.resourceType" clearable placeholder="全部对象" style="width: 160px">
            <el-option label="标志字典" value="sign" />
            <el-option label="违规记录" value="violation" />
            <el-option label="检测记录" value="detect_record" />
            <el-option label="日报" value="daily_report" />
            <el-option label="静态文件" value="storage" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间">
          <el-date-picker
            v-model="filters.dateRange"
            type="datetimerange"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 360px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="fetchLogs">查询</el-button>
          <el-button :icon="RefreshLeft" @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="table-header">
          <span>操作审计日志</span>
          <el-tag type="info">共 {{ total }} 条</el-tag>
        </div>
      </template>

      <el-table :data="logs" v-loading="loading" border stripe>
        <el-table-column prop="create_time" label="操作时间" width="190" />
        <el-table-column prop="username" label="操作人" width="130" />
        <el-table-column label="角色" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'success'" size="small">
              {{ row.role === 'admin' ? '管理员' : '驾驶员' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="动作" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="actionTagType(row.action)" size="small">{{ actionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="对象" width="130">
          <template #default="{ row }">{{ resourceLabel(row.resource_type) }}</template>
        </el-table-column>
        <el-table-column prop="resource_id" label="对象ID" width="100" />
        <el-table-column prop="summary" label="摘要" min-width="260" show-overflow-tooltip />
        <el-table-column label="详情" width="90" align="center">
          <template #default="{ row }">
            <el-button type="primary" link @click="openDetail(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchLogs"
          @current-change="fetchLogs"
        />
      </div>
    </el-card>

    <el-drawer v-model="detailVisible" title="审计详情" size="520px">
      <el-descriptions v-if="currentLog" :column="1" border>
        <el-descriptions-item label="操作时间">{{ currentLog.create_time }}</el-descriptions-item>
        <el-descriptions-item label="操作人">{{ currentLog.username }}</el-descriptions-item>
        <el-descriptions-item label="动作">{{ actionLabel(currentLog.action) }}</el-descriptions-item>
        <el-descriptions-item label="对象">{{ resourceLabel(currentLog.resource_type) }}</el-descriptions-item>
        <el-descriptions-item label="对象ID">{{ currentLog.resource_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="摘要">{{ currentLog.summary }}</el-descriptions-item>
      </el-descriptions>
      <pre class="detail-json">{{ formattedDetail }}</pre>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, RefreshLeft } from '@element-plus/icons-vue'
import api, { getErrorMessage } from '../api/client'

const loading = ref(false)
const logs = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const detailVisible = ref(false)
const currentLog = ref(null)

const filters = reactive({
  username: '',
  action: '',
  resourceType: '',
  dateRange: null
})

const actionLabels = {
  create: '新增',
  update: '更新',
  delete: '删除',
  import: '导入',
  update_status: '处理状态',
  rebuild: '重建报表',
  cleanup: '清理存储'
}

const resourceLabels = {
  sign: '标志字典',
  violation: '违规记录',
  detect_record: '检测记录',
  daily_report: '日报',
  storage: '静态文件'
}

const actionLabel = (action) => actionLabels[action] || action
const resourceLabel = (resourceType) => resourceLabels[resourceType] || resourceType

const actionTagType = (action) => {
  if (action === 'delete') return 'danger'
  if (action === 'create' || action === 'import') return 'success'
  if (action === 'rebuild' || action === 'cleanup') return 'warning'
  return 'primary'
}

const formattedDetail = computed(() => {
  if (!currentLog.value?.detail) return '{}'
  return JSON.stringify(currentLog.value.detail, null, 2)
})

const buildParams = () => {
  const params = {
    page: page.value,
    size: size.value,
    username: filters.username || undefined,
    action: filters.action || undefined,
    resource_type: filters.resourceType || undefined
  }
  if (filters.dateRange?.length === 2) {
    params.start_time = filters.dateRange[0]
    params.end_time = filters.dateRange[1]
  }
  return params
}

const fetchLogs = async () => {
  loading.value = true
  try {
    const res = await api.get('/api/audit-logs', { params: buildParams() })
    logs.value = res.data.data
    total.value = res.data.total
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '获取审计日志失败'))
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.username = ''
  filters.action = ''
  filters.resourceType = ''
  filters.dateRange = null
  page.value = 1
  fetchLogs()
}

const openDetail = (row) => {
  currentLog.value = row
  detailVisible.value = true
}

onMounted(fetchLogs)
</script>

<style scoped>
.audit-page {
  padding: 20px;
}

.filter-card {
  margin-bottom: 16px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 0 8px;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.detail-json {
  margin-top: 16px;
  padding: 12px;
  background: #f6f8fa;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
