<template>
  <div class="query-page">
    <el-card shadow="never" class="toolbar-card">
      <el-form :inline="true" :model="filters" class="query-form">
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" clearable placeholder="编码 / 含义 / 位置" style="width: 200px" />
        </el-form-item>
        <el-form-item label="路段">
          <el-input v-model="filters.road_section" clearable placeholder="如 G5京昆高速 K120" style="width: 220px" />
        </el-form-item>
        <el-form-item label="方向">
          <el-input v-model="filters.direction" clearable placeholder="如 成都方向" style="width: 160px" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="filters.sign_type" clearable placeholder="全部类型" style="width: 140px">
            <el-option label="指示标志" value="指示标志" />
            <el-option label="警告标志" value="警告标志" />
            <el-option label="禁止标志" value="禁止标志" />
          </el-select>
        </el-form-item>
        <el-form-item label="纬度">
          <el-input-number
            v-model="filters.latitude"
            :min="-90"
            :max="90"
            :precision="6"
            :controls="false"
            placeholder="如 30.12"
            style="width: 130px"
          />
        </el-form-item>
        <el-form-item label="经度">
          <el-input-number
            v-model="filters.longitude"
            :min="-180"
            :max="180"
            :precision="6"
            :controls="false"
            placeholder="如 103.12"
            style="width: 130px"
          />
        </el-form-item>
        <el-form-item label="半径">
          <el-input-number
            v-model="filters.radius_km"
            :min="0.1"
            :max="500"
            :precision="1"
            style="width: 120px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchSigns" :loading="loading">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="result-card">
      <template #header>
        <div class="card-header">
          <span>查询结果</span>
          <el-tag type="info" effect="plain">{{ total }} 条</el-tag>
        </div>
      </template>

      <el-table :data="rows" border stripe v-loading="loading" style="width: 100%">
        <el-table-column prop="road_section" label="路段" min-width="160" />
        <el-table-column prop="direction" label="方向" width="110" />
        <el-table-column prop="position_desc" label="位置说明" min-width="220" />
        <el-table-column prop="meaning" label="标志含义" min-width="150">
          <template #default="scope">
            <el-tag :type="getTypeTag(scope.row.sign_type)" effect="plain">{{ scope.row.meaning }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sign_code" label="编码" width="100" />
        <el-table-column prop="distance_km" label="距离" width="100" align="center">
          <template #default="scope">
            <span v-if="scope.row.distance_km !== undefined">{{ scope.row.distance_km }} km</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="recommended_speed" label="建议速度" width="110" align="center">
          <template #default="scope">
            <span v-if="scope.row.recommended_speed !== null && scope.row.recommended_speed !== undefined">
              {{ scope.row.recommended_speed }} km/h
            </span>
            <span v-else class="muted">无</span>
          </template>
        </el-table-column>
        <el-table-column label="坐标" min-width="160">
          <template #default="scope">
            <span v-if="scope.row.latitude !== null && scope.row.latitude !== undefined && scope.row.longitude !== null && scope.row.longitude !== undefined">
              {{ Number(scope.row.latitude).toFixed(4) }}, {{ Number(scope.row.longitude).toFixed(4) }}
            </span>
            <span v-else class="muted">未配置</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import api, { getErrorMessage } from '../api/client'

const loading = ref(false)
const total = ref(0)
const rows = ref([])
const filters = reactive({
  keyword: '',
  road_section: '',
  direction: '',
  sign_type: '',
  latitude: null,
  longitude: null,
  radius_km: 5
})

const getTypeTag = (type) => {
  if (type === '指示标志') return 'primary'
  if (type === '警告标志') return 'warning'
  if (type === '禁止标志') return 'danger'
  return 'info'
}

const fetchSigns = async () => {
  loading.value = true
  try {
    const hasLatitude = filters.latitude !== null && filters.latitude !== undefined
    const hasLongitude = filters.longitude !== null && filters.longitude !== undefined
    if (hasLatitude !== hasLongitude) {
      ElMessage.warning('经纬度需要同时填写')
      return
    }

    const params = Object.fromEntries(
      Object.entries(filters).filter(([, value]) => value !== '' && value !== null && value !== undefined)
    )
    const endpoint = hasLatitude && hasLongitude ? '/api/signs/nearby' : '/api/signs/search'
    const res = await api.get(endpoint, { params })
    rows.value = res.data.data
    total.value = res.data.total
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '查询标志信息失败'))
  } finally {
    loading.value = false
  }
}

const reset = () => {
  Object.assign(filters, {
    keyword: '',
    road_section: '',
    direction: '',
    sign_type: '',
    latitude: null,
    longitude: null,
    radius_km: 5
  })
  fetchSigns()
}

onMounted(fetchSigns)
</script>

<style scoped>
.toolbar-card {
  margin-bottom: 16px;
}
.query-form {
  margin-bottom: -18px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}
.muted {
  color: #909399;
}
</style>
