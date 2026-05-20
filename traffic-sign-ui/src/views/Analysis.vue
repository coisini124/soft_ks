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
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'
import { DataLine, Warning, Odometer, Bell, Refresh, InfoFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// --- 根据后端同学 IP 修改 ---
const baseURL = 'http://localhost:8000'

const barChartRef = ref(null)
const pieChartRef = ref(null)
const detectLineChartRef = ref(null)
const violationLineChartRef = ref(null)
const cacheDate = ref(null)
const refreshing = ref(false)

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
    const res = await axios.get(`${baseURL}/api/stats`)
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
    
  } catch (error) {
    ElMessage.error('获取统计数据失败')
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
  window.addEventListener('resize', handleResize)
})

const refresh = async () => {
  refreshing.value = true
  await fetchDataAndRender()
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
.card-header {
  font-size: 15px;
  color: #303133;
}
</style>