<template>
  <div class="analysis-container">
    <!-- 顶部工具栏：手动刷新 + 数据来源提示 -->
    <div class="toolbar">
      <span v-if="cacheDate" style="color: #909399; font-size: 13px;">
        <el-icon><InfoFilled /></el-icon>
        TOP10 / 违规占比数据来源：{{ cacheDate }} 预聚合缓存（每天 00:00 自动更新）
      </span>
      <span v-else style="color: #E6A23C; font-size: 13px;">
        <el-icon><Warning /></el-icon> 暂无预聚合缓存，当前为实时计算数据
      </span>
      <el-button type="primary" :loading="refreshing" @click="refresh" style="margin-left: 16px;">
        <el-icon><Refresh /></el-icon> 手动刷新
      </el-button>
    </div>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card shadow="hover" class="chart-card">
          <template #header><div class="card-header"><span style="font-weight: bold;"><el-icon><DataLine /></el-icon> 交通标志高频识别 TOP 10</span></div></template>
          <div ref="barChartRef" style="height: 350px; width: 100%;"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover" class="chart-card">
          <template #header><div class="card-header"><span style="font-weight: bold;"><el-icon><Warning /></el-icon> 核心违规行为占比分析</span></div></template>
          <div ref="pieChartRef" style="height: 350px; width: 100%;"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card shadow="hover" class="chart-card">
          <template #header><div class="card-header"><span style="font-weight: bold;"><el-icon><Odometer /></el-icon> 近30天系统检测量趋势 (吞吐量)</span></div></template>
          <div ref="detectLineChartRef" style="height: 350px; width: 100%;"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover" class="chart-card">
          <template #header><div class="card-header"><span style="font-weight: bold; color: #F56C6C;"><el-icon><Bell /></el-icon> 近30天违规预警触发趋势 (警报量)</span></div></template>
          <div ref="violationLineChartRef" style="height: 350px; width: 100%;"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="24">
        <el-card shadow="hover" class="chart-card">
          <template #header><div class="card-header"><span style="font-weight: bold; color: #67C23A;"><el-icon><Refresh /></el-icon> 近30天标志字典更新频率</span></div></template>
          <div ref="signUpdateLineChartRef" style="height: 300px; width: 100%;"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="isAdmin" shadow="hover" class="mapping-card">
      <template #header>
        <div class="report-header">
          <span style="font-weight: bold;"><el-icon><InfoFilled /></el-icon> 模型类别映射检查</span>
          <el-button type="primary" :loading="mappingChecking" @click="fetchMappingCheck">
            <el-icon><Refresh /></el-icon> 重新检查
          </el-button>
        </div>
      </template>
      <el-skeleton v-if="mappingChecking && !mappingCheck" :rows="3" animated />
      <template v-else-if="mappingCheck">
        <el-alert
          :type="mappingCheck.ready ? 'success' : 'warning'"
          :title="mappingCheck.ready ? '字典与模型映射检查通过' : '模型映射仍需关注'"
          :closable="false"
          show-icon
          class="mapping-alert"
        />
        <el-descriptions :column="4" border size="small">
          <el-descriptions-item label="检测模式">{{ mappingCheck.mode }}</el-descriptions-item>
          <el-descriptions-item label="字典数量">{{ mappingCheck.dictionary.total }}</el-descriptions-item>
          <el-descriptions-item label="字典 ID 范围">
            {{ mappingCheck.dictionary.min_id }} - {{ mappingCheck.dictionary.max_id }}
          </el-descriptions-item>
          <el-descriptions-item label="模型类别数">
            {{ mappingCheck.model.class_count ?? '未加载' }}
          </el-descriptions-item>
          <el-descriptions-item label="模型文件">
            <el-tag :type="mappingCheck.model.available ? 'success' : 'warning'" size="small">
              {{ mappingCheck.model.available ? '已找到' : '缺失' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="缺失字典 ID">
            {{ mappingCheck.dictionary.missing_ids.length ? mappingCheck.dictionary.missing_ids.join(', ') : '无' }}
          </el-descriptions-item>
          <el-descriptions-item label="重复编码">
            {{ mappingCheck.dictionary.duplicate_codes.length ? mappingCheck.dictionary.duplicate_codes.join(', ') : '无' }}
          </el-descriptions-item>
          <el-descriptions-item label="限速规则问题">
            {{ mappingCheck.dictionary.limit_rule_issues.length }}
          </el-descriptions-item>
        </el-descriptions>
        <div v-if="mappingCheck.blocking_issues.length || mappingCheck.warnings.length" class="mapping-notes">
          <el-tag
            v-for="item in [...mappingCheck.blocking_issues, ...mappingCheck.warnings]"
            :key="item"
            :type="mappingCheck.blocking_issues.includes(item) ? 'danger' : 'warning'"
            effect="plain"
          >
            {{ item }}
          </el-tag>
        </div>
      </template>
    </el-card>

    <el-card v-if="isAdmin" shadow="hover" class="storage-card">
      <template #header>
        <div class="report-header">
          <span style="font-weight: bold;"><el-icon><InfoFilled /></el-icon> 静态文件存储</span>
          <div>
            <el-button :loading="storageLoading" @click="fetchStorageStatus">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
            <el-popconfirm
              title="确定清理未被检测记录引用的孤儿文件吗？"
              confirm-button-text="清理"
              cancel-button-text="取消"
              @confirm="cleanupStorage"
            >
              <template #reference>
                <el-button type="warning" :loading="storageCleaning" :disabled="!storageStatus?.orphaned_files">
                  清理孤儿文件
                </el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </template>
      <el-skeleton v-if="storageLoading && !storageStatus" :rows="2" animated />
      <el-descriptions v-else-if="storageStatus" :column="4" border size="small">
        <el-descriptions-item label="文件总数">{{ storageStatus.total_files }}</el-descriptions-item>
        <el-descriptions-item label="总占用">{{ formatBytes(storageStatus.total_bytes) }}</el-descriptions-item>
        <el-descriptions-item label="记录引用">{{ storageStatus.referenced_files }}</el-descriptions-item>
        <el-descriptions-item label="孤儿文件">
          <el-tag :type="storageStatus.orphaned_files ? 'warning' : 'success'" size="small">
            {{ storageStatus.orphaned_files }} 个 / {{ formatBytes(storageStatus.orphaned_bytes) }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <div v-if="storageStatus?.orphaned_samples?.length" class="storage-samples">
        <el-tag
          v-for="item in storageStatus.orphaned_samples.slice(0, 8)"
          :key="item.path"
          type="warning"
          effect="plain"
        >
          {{ item.path }} ({{ formatBytes(item.size) }})
        </el-tag>
      </div>
    </el-card>

    <el-card v-if="isAdmin" shadow="hover" class="report-card">
      <template #header>
        <div class="report-header">
          <span style="font-weight: bold;"><el-icon><InfoFilled /></el-icon> 每日统计报告</span>
          <el-button type="success" :loading="rebuildingReport" @click="rebuildYesterdayReport">
            <el-icon><Refresh /></el-icon> 生成昨日报告
          </el-button>
        </div>
      </template>
      <el-table :data="dailyReports" border stripe>
        <el-table-column prop="stat_date" label="统计日期" width="140" />
        <el-table-column prop="total_detections" label="检测总数" width="120" align="center" />
        <el-table-column prop="total_violations" label="违规总数" width="120" align="center" />
        <el-table-column label="高频标志 TOP3" min-width="240">
          <template #default="{ row }">
            <el-tag
              v-for="item in row.top_signs.slice(0, 3)"
              :key="item.name"
              effect="plain"
              style="margin-right: 6px;"
            >
              {{ item.name }} x{{ item.value }}
            </el-tag>
            <span v-if="row.top_signs.length === 0" style="color: #909399;">暂无标志数据</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="生成时间" width="180" />
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button type="primary" link @click="exportDailyReport(row.stat_date)">
              <el-icon><Download /></el-icon> 下载
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { DataLine, Warning, Odometer, Bell, Refresh, InfoFilled, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api, { downloadBlob, getErrorMessage } from '../api/client'

const barChartRef = ref(null)
const pieChartRef = ref(null)
const detectLineChartRef = ref(null)
const violationLineChartRef = ref(null)
const signUpdateLineChartRef = ref(null)
const cacheDate = ref(null)
const refreshing = ref(false)
const rebuildingReport = ref(false)
const mappingChecking = ref(false)
const mappingCheck = ref(null)
const dailyReports = ref([])
const storageStatus = ref(null)
const storageLoading = ref(false)
const storageCleaning = ref(false)
const isAdmin = computed(() => localStorage.getItem('role') === 'admin')

let instances = {}

// 1. 横向柱状图 (TOP 10)
const initBarChart = (data) => {
  instances.bar = echarts.init(barChartRef.value)
  const sortedData = [...data].reverse() // 第一名放最上面
  instances.bar.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '8%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: sortedData.map(item => item.name) },
    series: [{
      type: 'bar',
      data: sortedData.map(item => item.value),
      itemStyle: { color: '#409EFF', borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right' }
    }]
  })
}

// 2. 环形图 (违规占比)
const initPieChart = (data) => {
  instances.pie = echarts.init(pieChartRef.value)
  instances.pie.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}起 ({d}%)' },
    legend: { bottom: '0%', left: 'center' },
    color: ['#F56C6C', '#E6A23C', '#909399'], // 采用警示颜色
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}\n{c}起' },
      data: data
    }]
  })
}

// 3. 通用折线图生成函数
const initLineChart = (domRef, data, colorStr, areaColorRgba, name) => {
  const instance = echarts.init(domRef)
  const reversedData = [...data].reverse() // 时间正序
  instance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: reversedData.map(item => item.date) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      name: name,
      type: 'line',
      smooth: true,
      itemStyle: { color: colorStr },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: areaColorRgba },
          { offset: 1, color: 'rgba(255,255,255,0)' }
        ])
      },
      data: reversedData.map(item => item.count)
    }]
  })
  return instance
}

const fetchDataAndRender = async () => {
  try {
    const res = await api.get('/api/stats')
    cacheDate.value = res.data.cache_date || null

    // 销毁旧实例再重绘，避免手动刷新时图表叠加
    Object.values(instances).forEach(i => i && i.dispose())
    instances = {}

    initBarChart(res.data.top_signs)
    initPieChart(res.data.violation_pie)
    
    // 蓝色检测趋势
    instances.detectLine = initLineChart(
      detectLineChartRef.value, 
      res.data.detect_trend, 
      '#409EFF', 
      'rgba(64,158,255,0.5)', 
      '检测量'
    )
    
    // 红色违规趋势
    instances.violationLine = initLineChart(
      violationLineChartRef.value, 
      res.data.violation_trend, 
      '#F56C6C', 
      'rgba(245,108,108,0.5)', 
      '预警量'
    )

    instances.signUpdateLine = initLineChart(
      signUpdateLineChartRef.value,
      res.data.sign_update_trend || [],
      '#67C23A',
      'rgba(103,194,58,0.35)',
      '更新次数'
    )
    
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '获取统计数据失败'))
  }
}

const fetchDailyReports = async () => {
  if (!isAdmin.value) return
  try {
    const res = await api.get('/api/reports/daily', { params: { limit: 30 } })
    dailyReports.value = res.data
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '获取日报列表失败'))
  }
}

const fetchMappingCheck = async () => {
  if (!isAdmin.value) return
  mappingChecking.value = true
  try {
    const res = await api.get('/api/model/mapping-check')
    mappingCheck.value = res.data
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '获取模型映射检查失败'))
  } finally {
    mappingChecking.value = false
  }
}

const rebuildYesterdayReport = async () => {
  rebuildingReport.value = true
  try {
    await api.post('/api/reports/daily/rebuild')
    ElMessage.success('昨日报告已生成')
    await fetchDailyReports()
    await fetchDataAndRender()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '生成日报失败'))
  } finally {
    rebuildingReport.value = false
  }
}

const exportDailyReport = async (statDate) => {
  try {
    const res = await api.get(`/api/reports/daily/${statDate}/export`, { responseType: 'blob' })
    downloadBlob(res.data, `daily_report_${statDate}.csv`)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '下载日报失败'))
  }
}

const formatBytes = (bytes) => {
  const value = Number(bytes || 0)
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`
  return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`
}

const fetchStorageStatus = async () => {
  if (!isAdmin.value) return
  storageLoading.value = true
  try {
    const res = await api.get('/api/storage/status')
    storageStatus.value = res.data
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '获取静态文件存储状态失败'))
  } finally {
    storageLoading.value = false
  }
}

const cleanupStorage = async () => {
  storageCleaning.value = true
  try {
    const res = await api.post('/api/storage/cleanup', null, { params: { dry_run: false } })
    storageStatus.value = res.data.status
    ElMessage.success(`已清理 ${res.data.removed_file_count} 个孤儿文件`)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '清理孤儿文件失败'))
  } finally {
    storageCleaning.value = false
  }
}

// 监听窗口缩放
const handleResize = () => {
  Object.values(instances).forEach(instance => {
    if (instance) instance.resize()
  })
}

onMounted(() => {
  fetchDataAndRender()
  fetchDailyReports()
  fetchMappingCheck()
  fetchStorageStatus()
  window.addEventListener('resize', handleResize)
})

const refresh = async () => {
  refreshing.value = true
  await fetchDataAndRender()
  await fetchDailyReports()
  await fetchMappingCheck()
  await fetchStorageStatus()
  refreshing.value = false
}

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  Object.values(instances).forEach(instance => {
    if (instance) instance.dispose()
  })
})
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  padding: 10px 16px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #EBEEF5;
}
.chart-card {
  border-radius: 8px;
  margin-bottom: 20px;
}
.report-card {
  border-radius: 8px;
}
.mapping-card {
  border-radius: 8px;
  margin-bottom: 20px;
}
.storage-card {
  border-radius: 8px;
  margin-bottom: 20px;
}
.storage-samples {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.mapping-alert {
  margin-bottom: 12px;
}
.mapping-notes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.report-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.card-header {
  font-size: 15px;
  color: #303133;
}
</style>
