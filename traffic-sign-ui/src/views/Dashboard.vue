<template>
  <div class="dashboard-container">
<el-row :gutter="20" class="data-board">
      <el-col :span="8">
        <el-card shadow="hover" class="data-card">
          <div class="card-title">今日/累计检测总数</div>
          <div class="card-value">{{ totalDetections }} <span class="unit">次</span></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="data-card warning-card">
          <div class="card-title">累计违规预警</div>
          <div class="card-value">{{ totalViolations }} <span class="unit">起</span></div>
        </el-card>
      </el-col>
<el-col :span="8">
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
              </el-select>
            </el-form-item>
          </el-form>

          <el-divider />

          <div class="panel-header" style="margin-bottom: 15px;">
            <span><el-icon><Camera /></el-icon> 实时画面抓拍上传</span>
          </div>
          <el-upload
            class="upload-demo"
            drag
            action="#"
            :auto-upload="false"
            :on-change="handleFileChange"
            :show-file-list="true"
            :limit="1"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              拖拽图片到此处，或 <em>点击上传</em>
            </div>
          </el-upload>

          <el-button 
            type="primary" 
            size="large" 
            style="margin-top: 20px; width: 100%;" 
            @click="submitDetection"
            :loading="loading"
            :disabled="!selectedFile"
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
                <div class="img-title">原始监控画面</div>
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
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Setting, Camera, DataBoard, UploadFilled } from '@element-plus/icons-vue'

// 后端统一接口地址 
const baseURL = 'http://localhost:8000'

// 状态变量
const currentSpeed = ref(80)
const currentAction = ref('直行')
const selectedFile = ref(null)
const loading = ref(false)
const resultData = ref(null)

// 真实统计数据变量
const totalDetections = ref(0)
const totalViolations = ref(0)
// 在原来的状态变量区域增加：
const isOnline = ref(true)

// 修改 fetchStats 函数，加入对 isOnline 的控制：
const fetchStats = async () => {
  try {
    const response = await axios.get(`${baseURL}/api/stats`)
    totalDetections.value = response.data.total_detections
    totalViolations.value = response.data.total_violations
    isOnline.value = true // 连接成功，设为在线
  } catch (error) {
    console.error('获取统计数据失败:', error)
    isOnline.value = false // 连接失败，设为离线
    ElMessage.warning('无法连接到后端服务器')
  }
}

// 页面刚加载时，立刻去后端拉取真实数字
onMounted(() => {
  fetchStats()
})

const handleFileChange = (file) => {
  selectedFile.value = file.raw
}

// 核心检测函数
const submitDetection = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先抓拍或上传一张图片！')
    return
  }

  loading.value = true
  resultData.value = null

  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('current_speed', currentSpeed.value)
  formData.append('current_action', currentAction.value)

  try {
    const response = await axios.post(`${baseURL}/api/detect`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    resultData.value = response.data
    if (resultData.value.is_violation) {
      ElMessage.error('触发违规警报！')
    } else {
      ElMessage.success('智能检测完成')
    }
    
    // 【魔法时刻】检测完成后，数据库里多了一条记录，我们立刻刷新顶部的数字！
    fetchStats()
    
  } catch (error) {
    console.error(error)
    ElMessage.error('连接 AI 引擎失败，请检查网络或后端服务')
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
.warning-card .card-value {
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
.empty-state {
  height: 400px;
  display: flex;
  justify-content: center;
  align-items: center;
}
</style>