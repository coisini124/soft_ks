<template>
  <div class="dashboard-container">
    <el-row :gutter="20" class="data-board">
      <el-col :span="6">
        <el-card shadow="hover" class="data-card">
          <div class="card-title">今日/累计检测总数</div>
          <div class="card-value">{{ totalDetections }} <span class="unit">次</span></div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="data-card warning-card">
          <div class="card-title">累计违规预警</div>
          <div class="card-value">{{ totalViolations }} <span class="unit">起</span></div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" :class="['data-card', pendingViolations > 0 ? 'danger-card' : 'success-card']">
          <div class="card-title">待处理预警</div>
          <div class="card-value">{{ pendingViolations }} <span class="unit">起</span></div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" :class="['data-card', isOnline ? 'success-card' : 'warning-card']">
          <div class="card-title">系统运行状态</div>
          <div class="card-value" v-if="isOnline">
            良好 <span class="unit">服务器在线</span>
          </div>
          <div class="card-value" v-else style="color: #F56C6C;">
            离线 <span class="unit" style="color: #F56C6C;">与服务器失去连接</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-alert
      v-if="modelStatus"
      :title="modelStatusTitle"
      :type="modelStatus.ready ? (modelStatus.mode === 'mock' ? 'warning' : 'success') : 'error'"
      show-icon
      :closable="false"
      style="margin-bottom: 20px;"
    />

    <el-row :gutter="20">
      <el-col :span="10">
        <el-card shadow="hover" class="control-panel">
          <template #header>
            <div class="panel-header">
              <span><el-icon><Setting /></el-icon> 实时车辆状态模拟</span>
            </div>
          </template>
          
          <el-form label-width="80px">
            <el-form-item label="当前车速">
              <el-input-number v-model="currentSpeed" :min="0" :max="200" />
              <span style="margin-left: 10px;">km/h</span>
            </el-form-item>
            <el-form-item label="当前动作">
              <el-select v-model="currentAction" placeholder="请选择">
                <el-option label="正常直行" value="直行" />
                <el-option label="正在掉头" value="掉头" />
                <el-option label="正在鸣笛" value="鸣笛" />
                <el-option label="正在停车" value="停车" />
              </el-select>
            </el-form-item>
            <el-form-item label="识别阈值">
              <div class="confidence-control">
                <el-slider
                  v-model="minConfidence"
                  :min="0.1"
                  :max="0.95"
                  :step="0.05"
                  :format-tooltip="formatConfidence"
                />
                <el-tag size="small" type="info">{{ formatConfidence(minConfidence) }}</el-tag>
              </div>
            </el-form-item>
          </el-form>

          <el-divider />

          <div class="panel-header" style="margin-bottom: 15px;">
            <span><el-icon><Camera /></el-icon> 实时画面上传</span>
          </div>
          <el-form-item label="输入类型">
            <el-segmented v-model="uploadMode" :options="uploadModeOptions" @change="resetUpload" />
          </el-form-item>
          <el-upload
            class="upload-demo"
            drag
            action="#"
            :auto-upload="false"
            :on-change="handleFileChange"
            :on-remove="resetUpload"
            :show-file-list="true"
            :limit="1"
            :accept="uploadMode === 'image' ? 'image/*' : 'video/*'"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              拖拽{{ uploadMode === 'image' ? '图片' : '视频' }}到此处，或 <em>点击上传</em>
            </div>
          </el-upload>

          <div class="camera-capture">
            <el-divider>摄像头抓拍</el-divider>
            <video
              v-show="cameraActive"
              ref="videoRef"
              class="camera-preview"
              autoplay
              playsinline
              muted
            />
            <div class="camera-actions">
              <el-button :loading="cameraLoading" @click="startCamera" :disabled="cameraActive">
                打开摄像头
              </el-button>
              <el-button type="success" @click="captureFrame" :disabled="!cameraActive">
                抓拍画面
              </el-button>
              <el-button @click="stopCamera" :disabled="!cameraActive">
                关闭
              </el-button>
            </div>
            <div class="monitor-actions">
              <span class="monitor-label">自动监控间隔</span>
              <el-input-number
                v-model="monitorIntervalSec"
                :min="3"
                :max="60"
                :step="1"
                size="small"
                :disabled="monitoringActive"
              />
              <span class="monitor-label">秒</span>
            </div>
            <div class="camera-actions">
              <el-button
                type="warning"
                :loading="cameraLoading"
                @click="startMonitoring"
                :disabled="monitoringActive"
              >
                开始连续监控
              </el-button>
              <el-button type="danger" @click="stopMonitoring" :disabled="!monitoringActive">
                停止监控
              </el-button>
            </div>
            <el-alert
              v-if="monitoringActive"
              :title="`连续监控运行中：已自动分析 ${monitoringCount} 帧${lastMonitorAt ? '，最近一次 ' + lastMonitorAt : ''}`"
              type="info"
              show-icon
              :closable="false"
              style="margin-top: 12px;"
            />
          </div>

          <el-button 
            type="primary" 
            size="large" 
            style="margin-top: 20px; width: 100%;" 
            @click="submitDetection"
            :loading="loading"
            :disabled="!selectedFile || monitoringActive"
          >
            启动 AI 智能识别
          </el-button>
        </el-card>
      </el-col>

      <el-col :span="14">
        <el-card shadow="hover" class="result-panel">
          <template #header>
            <div class="panel-header">
              <span><el-icon><DataBoard /></el-icon> AI 识别与预警结果</span>
            </div>
          </template>
          
          <div v-if="resultData" class="result-content">
            <el-alert
              v-if="resultData.is_violation"
              title="警告：检测到违规行为！"
              type="error"
              show-icon
              :closable="false"
              style="margin-bottom: 20px;"
            >
              <div v-for="(msg, index) in resultData.violation_msgs" :key="index">
                {{ msg }}
              </div>
              <div v-if="resultData.violation_events?.length" class="violation-tags">
                <el-tag
                  v-for="(event, index) in resultData.violation_events"
                  :key="`${event.type}-${index}`"
                  :type="getSeverityTag(event.severity)"
                  effect="dark"
                >
                  {{ event.label || event.type }} / {{ getSeverityText(event.severity) }}
                </el-tag>
              </div>
            </el-alert>
            
            <el-alert
              v-else
              title="行驶状态良好，未发现违规"
              type="success"
              show-icon
              :closable="false"
              style="margin-bottom: 20px;"
            />

            <el-row :gutter="10" style="margin-bottom: 20px;">
              <el-col :span="12">
                <div class="img-title">{{ resultData.source_type === 'video' ? '原始视频/抽帧' : '原始监控画面' }}</div>
                <el-image 
                  class="preview-img"
                  :src="resultData.original_image"
                  :preview-src-list="[resultData.original_image]"
                  fit="contain"
                />
              </el-col>
              <el-col :span="12">
                <div class="img-title active">AI 深度解析结果</div>
                <el-image 
                  class="preview-img result-img"
                  :src="resultData.result_image"
                  :preview-src-list="[resultData.result_image]"
                  fit="contain"
                />
              </el-col>
            </el-row>

            <h4>提取到的交通标志特征：</h4>
            <el-empty v-if="resultData.detected_signs.length === 0" description="未检测到交通标志" :image-size="60" />
            <div v-else>
              <el-tag 
                v-for="(sign, index) in resultData.detected_signs" 
                :key="index" 
                size="large" 
                effect="dark" 
                style="margin: 5px;"
              >
                {{ sign }}
              </el-tag>
            </div>
            <el-alert
              v-if="resultData.source_type === 'video'"
              :title="`视频抽帧检测完成，共分析 ${resultData.sampled_frames || 0} 帧`"
              type="info"
              show-icon
              :closable="false"
              style="margin-top: 16px;"
            />
            <el-alert
              :title="`本次识别置信度阈值：${formatConfidence(resultData.min_confidence || minConfidence)}`"
              type="info"
              show-icon
              :closable="false"
              style="margin-top: 12px;"
            />
          </div>
          
          <div v-else class="empty-state">
            <el-empty description="系统就绪，等待传入监控画面..." />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, ref, onBeforeUnmount, onMounted } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import { Setting, Camera, DataBoard, UploadFilled } from '@element-plus/icons-vue'
import api, { getErrorMessage } from '../api/client'

// 状态变量
const currentSpeed = ref(80)
const currentAction = ref('直行')
const minConfidence = ref(0.25)
const uploadMode = ref('image')
const uploadModeOptions = [
  { label: '图片', value: 'image' },
  { label: '视频', value: 'video' }
]
const selectedFile = ref(null)
const loading = ref(false)
const resultData = ref(null)
const videoRef = ref(null)
const cameraActive = ref(false)
const cameraLoading = ref(false)
const monitoringActive = ref(false)
const monitoringBusy = ref(false)
const monitorIntervalSec = ref(5)
const monitoringCount = ref(0)
const lastMonitorAt = ref('')
let cameraStream = null
let monitorTimer = null

// 真实统计数据变量
const totalDetections = ref(0)
const totalViolations = ref(0)
const pendingViolations = ref(0)
// 在原来的状态变量区域增加：
const isOnline = ref(true)
const modelStatus = ref(null)

const modelStatusTitle = computed(() => {
  if (!modelStatus.value) return ''
  if (modelStatus.value.mode === 'mock') {
    return `当前为演示检测模式，使用字典 ID ${modelStatus.value.mock_sign_id || '默认'} 生成可验收流程`
  }
  if (modelStatus.value.ready) {
    return `真实模型已就绪：${modelStatus.value.path}`
  }
  return `检测模型不可用：${modelStatus.value.error || modelStatus.value.path}`
})

const getSeverityTag = (severity) => {
  if (severity === 'high') return 'danger'
  if (severity === 'medium') return 'warning'
  return 'info'
}

const getSeverityText = (severity) => {
  if (severity === 'high') return '高危'
  if (severity === 'medium') return '中危'
  if (severity === 'low') return '低危'
  return '提示'
}

const formatConfidence = (value) => `${Math.round(Number(value || 0) * 100)}%`

// 修改 fetchStats 函数，加入对 isOnline 的控制：
const fetchStats = async () => {
  try {
    const response = await api.get('/api/stats')
    totalDetections.value = response.data.total_detections
    totalViolations.value = response.data.total_violations
    pendingViolations.value = response.data.pending_violations || 0
    isOnline.value = true // 连接成功，设为在线
  } catch (error) {
    console.error('获取统计数据失败:', error)
    isOnline.value = false // 连接失败，设为离线
    ElMessage.warning('无法连接到后端服务器')
  }
}

const fetchModelStatus = async () => {
  try {
    const response = await api.get('/api/model/status')
    modelStatus.value = response.data
  } catch (error) {
    modelStatus.value = null
  }
}

// 页面刚加载时，立刻去后端拉取真实数字
onMounted(() => {
  fetchStats()
  fetchModelStatus()
})

onBeforeUnmount(() => {
  stopMonitoring()
  stopCamera()
})

const handleFileChange = (file) => {
  selectedFile.value = file.raw
  if (file.raw?.type?.startsWith('video/')) {
    uploadMode.value = 'video'
  } else if (file.raw?.type?.startsWith('image/')) {
    uploadMode.value = 'image'
  }
}

const resetUpload = () => {
  selectedFile.value = null
  resultData.value = null
}

const startCamera = async () => {
  if (!navigator.mediaDevices?.getUserMedia) {
    ElMessage.warning('当前浏览器不支持摄像头访问')
    return
  }

  cameraLoading.value = true
  try {
    uploadMode.value = 'image'
    resetUpload()
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment' },
      audio: false
    })
    cameraActive.value = true
    if (videoRef.value) {
      videoRef.value.srcObject = cameraStream
      await videoRef.value.play()
    }
  } catch (error) {
    console.error('打开摄像头失败:', error)
    ElMessage.error('无法打开摄像头，请检查浏览器权限')
    stopCamera()
  } finally {
    cameraLoading.value = false
  }
}

const captureFrame = () => {
  createFrameFile()
    .then((file) => {
      selectedFile.value = file
      uploadMode.value = 'image'
      resultData.value = null
      ElMessage.success('已抓拍当前画面，可直接启动识别')
    })
    .catch((error) => {
      ElMessage.warning(error.message)
    })
}

const createFrameFile = () => {
  return new Promise((resolve, reject) => {
    const video = videoRef.value
    if (!video || !cameraActive.value || !video.videoWidth || !video.videoHeight) {
      reject(new Error('摄像头画面尚未就绪'))
      return
    }

    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const context = canvas.getContext('2d')
    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error('抓拍失败，请重试'))
        return
      }
      resolve(new File([blob], `camera_capture_${Date.now()}.jpg`, { type: 'image/jpeg' }))
    }, 'image/jpeg', 0.92)
  })
}

const startMonitoring = async () => {
  if (!cameraActive.value) {
    await startCamera()
  }
  if (!cameraActive.value) return

  monitoringActive.value = true
  monitoringCount.value = 0
  lastMonitorAt.value = ''
  await runMonitoringTick()
  monitorTimer = window.setInterval(runMonitoringTick, monitorIntervalSec.value * 1000)
  ElMessage.success('连续监控已启动')
}

const stopMonitoring = () => {
  if (monitorTimer) {
    window.clearInterval(monitorTimer)
    monitorTimer = null
  }
  monitoringActive.value = false
  monitoringBusy.value = false
}

const runMonitoringTick = async () => {
  if (!monitoringActive.value || monitoringBusy.value) return
  monitoringBusy.value = true
  try {
    const file = await createFrameFile()
    const payload = await detectFile(file, 'image', { silent: true })
    monitoringCount.value += 1
    lastMonitorAt.value = new Date().toLocaleTimeString()
    if (payload.is_violation) {
      ElNotification.error({
        title: '连续监控违规警报',
        message: (payload.violation_msgs || []).join('；') || '检测到违规行为',
        duration: 6000
      })
    }
  } catch (error) {
    console.error('连续监控检测失败:', error)
    ElMessage.error(getErrorMessage(error, error.message || '连续监控检测失败'))
  } finally {
    monitoringBusy.value = false
  }
}

const stopCamera = () => {
  stopMonitoring()
  if (cameraStream) {
    cameraStream.getTracks().forEach((track) => track.stop())
    cameraStream = null
  }
  if (videoRef.value) {
    videoRef.value.srcObject = null
  }
  cameraActive.value = false
}

const detectFile = async (file, mode, options = {}) => {
  if (!file) {
    ElMessage.warning('摄像头画面尚未就绪')
    return null
  }

  const formData = new FormData()
  formData.append('file', file)
  formData.append('current_speed', currentSpeed.value)
  formData.append('current_action', currentAction.value)
  formData.append('min_confidence', minConfidence.value)
  if (mode === 'video') {
    formData.append('frame_interval', 30)
    formData.append('max_frames', 20)
  }

  const endpoint = mode === 'video' ? '/api/detect/video' : '/api/detect'
  const response = await api.post(endpoint, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  resultData.value = response.data

  if (!options.silent) {
    if (response.data.is_violation) {
      ElMessage.error('触发违规警报！')
    } else {
      ElMessage.success('智能检测完成')
    }
  }

  fetchStats()
  return response.data
}

// 核心检测函数
const submitDetection = async () => {
  if (!selectedFile.value) {
    ElMessage.warning(`请先上传一段${uploadMode.value === 'image' ? '图片' : '视频'}！`)
    return
  }

  loading.value = true
  resultData.value = null

  try {
    await detectFile(selectedFile.value, uploadMode.value)
  } catch (error) {
    console.error(error)
    ElMessage.error(getErrorMessage(error, '连接 AI 引擎失败，请检查网络或后端服务'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.dashboard-container {
  /* 去掉这里的 padding，因为 Layout 里已经加了 */
}
.data-board {
  margin-bottom: 20px;
}
.data-card {
  border-radius: 8px;
}
.card-title {
  font-size: 14px;
  color: #909399;
  margin-bottom: 10px;
}
.card-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}
.unit {
  font-size: 14px;
  font-weight: normal;
  color: #909399;
}
.confidence-control {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) auto;
  gap: 12px;
  align-items: center;
  width: 100%;
}
.warning-card .card-value {
  color: #F56C6C;
}
.danger-card .card-value {
  color: #F56C6C;
}
.success-card .card-value {
  color: #67C23A;
}
.panel-header {
  font-size: 16px;
  font-weight: bold;
  display: flex;
  align-items: center;
  gap: 8px;
}
.camera-capture {
  margin-top: 18px;
}
.camera-preview {
  width: 100%;
  height: 220px;
  object-fit: contain;
  background: #111827;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
}
.camera-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.monitor-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.monitor-label {
  color: #606266;
  font-size: 13px;
}
.preview-img {
  width: 100%;
  height: 240px;
  background-color: #f5f7fa;
  border-radius: 4px;
  border: 1px solid #EBEEF5;
}
.result-img {
  border: 2px solid #409EFF;
}
.img-title {
  text-align: center;
  color: #606266;
  font-size: 14px;
  margin-bottom: 8px;
}
.img-title.active {
  color: #409EFF;
  font-weight: bold;
}
.violation-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.empty-state {
  height: 400px;
  display: flex;
  justify-content: center;
  align-items: center;
}
@media (max-width: 960px) {
  .camera-actions .el-button {
    flex: 1 1 120px;
  }
  .monitor-actions .el-input-number {
    flex: 1 1 140px;
  }
}
</style>
