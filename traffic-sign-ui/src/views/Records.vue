<template>
  <div class="records-container">
    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar-wrapper">
        <div class="filter-section">
          <el-input
            v-model="searchParams.signType"
            placeholder="按标志名称过滤 (如: 限制速度)"
            clearable
            style="width: 200px;"
            prefix-icon="Search"
          />
          <el-date-picker
            v-model="searchParams.dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 360px; margin-left: 12px;"
          />
          <el-select
            v-model="searchParams.hasViolation"
            placeholder="是否违规"
            clearable
            style="width: 120px; margin-left: 12px;"
          >
            <el-option label="全部" value="" />
            <el-option label="有违规" value="true" />
            <el-option label="无违规" value="false" />
          </el-select>
          <el-button type="primary" style="margin-left: 12px;" @click="handleSearch">
            <el-icon style="margin-right: 5px;"><Search /></el-icon> 搜索
          </el-button>
          <el-button @click="resetSearch">重置</el-button>
        </div>

        <div class="action-section">
          <el-button v-if="isAdmin" type="success" @click="exportReport">
            <el-icon style="margin-right: 5px;"><Download /></el-icon> 导出 CSV 报表
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="table-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        
        <el-tab-pane label="全量检测记录" name="detections">
          <el-table :data="recordsList" v-loading="loading" border stripe style="width: 100%">
            <el-table-column prop="id" label="记录 ID" width="80" align="center" />
            <el-table-column prop="create_time" label="检测时间" width="180" />
            
            <el-table-column label="抓拍原图" width="120" align="center">
              <template #default="scope">
                <el-image 
                  style="width: 60px; height: 60px; border-radius: 4px;"
                  :src="scope.row.original_image"
                  :preview-src-list="[scope.row.original_image]"
                  preview-teleported
                  fit="cover"
                />
              </template>
            </el-table-column>
            
            <el-table-column label="AI 识别结果图" width="120" align="center">
              <template #default="scope">
                <el-image 
                  style="width: 60px; height: 60px; border-radius: 4px; border: 1px solid #409EFF;"
                  :src="scope.row.result_image"
                  :preview-src-list="[scope.row.result_image]"
                  preview-teleported
                  fit="cover"
                />
              </template>
            </el-table-column>

            <el-table-column label="提取到的标志">
              <template #default="scope">
                <span v-if="scope.row.detected_signs === '未检测到标志'" style="color: #909399;">无标志</span>
                <el-tag 
                  v-else 
                  v-for="(sign, index) in scope.row.detected_signs.split(',')" 
                  :key="index"
                  style="margin-right: 5px; margin-bottom: 2px;"
                >
                  {{ sign }}
                </el-tag>
              </template>
            </el-table-column>
            
            <el-table-column label="运行状态" width="120" align="center">
              <template #default="scope">
                <el-tag v-if="scope.row.has_violation" type="danger" effect="dark">产生违规</el-tag>
                <el-tag v-else type="success" effect="plain">正常</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" align="center" fixed="right">
              <template #default="scope">
                <el-button size="small" type="primary" link @click="openDetail(scope.row.id)">
                  <el-icon><ZoomIn /></el-icon> 详情
                </el-button>
                <el-popconfirm
                  v-if="isAdmin"
                  title="确定彻底删除此记录及其违规信息吗？"
                  confirm-button-text="删除"
                  cancel-button-text="取消"
                  confirm-button-type="danger"
                  @confirm="handleDeleteRecord(scope.row.id)"
                >
                  <template #reference>
                    <el-button size="small" type="danger" link>删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="recordPage.current"
              v-model:page-size="recordPage.size"
              :total="recordPage.total"
              :page-sizes="[10, 20, 50]"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="fetchRecords"
              @current-change="fetchRecords"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane label="违规预警台账" name="violations">
          <el-table :data="violationsList" v-loading="loading" border style="width: 100%">
            <el-table-column prop="id" label="警告编号" width="100" align="center" />
            <el-table-column prop="create_time" label="报警时间" width="180" />
            <el-table-column prop="detect_id" label="关联检测ID" width="120" align="center">
              <template #default="scope">
                <el-link type="primary" @click="openDetail(scope.row.detect_id)"># {{ scope.row.detect_id }}</el-link>
              </template>
            </el-table-column>
            <el-table-column label="违规详情说明">
              <template #default="scope">
                <el-alert :title="scope.row.violation_msg" type="error" :closable="false" show-icon />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center">
              <template #default="scope">
                <el-button size="small" type="primary" link @click="openDetail(scope.row.detect_id)">
                  查看对比图
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="violationPage.current"
              v-model:page-size="violationPage.size"
              :total="violationPage.total"
              :page-sizes="[10, 20, 50]"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="fetchViolations"
              @current-change="fetchViolations"
            />
          </div>
        </el-tab-pane>

      </el-tabs>
    </el-card>
  <!-- 检测详情抽屉：高清对比图 + 违规说明 -->
  <el-drawer v-model="drawerVisible" title="检测详情 — 高清对比图及违规说明" size="60%" direction="rtl">
    <div v-if="detailLoading" style="text-align:center; padding: 60px 0;">
      <el-icon class="is-loading" size="40"><Loading /></el-icon>
      <p style="color:#909399; margin-top:12px;">加载中...</p>
    </div>
    <div v-else-if="detailData">
      <!-- 违规警报区 -->
      <div v-if="detailData.violations && detailData.violations.length > 0" style="margin-bottom: 20px;">
        <el-alert
          v-for="(v, i) in detailData.violations"
          :key="i"
          :title="v.violation_msg"
          type="error"
          show-icon
          :closable="false"
          style="margin-bottom: 8px;"
        />
      </div>
      <el-alert v-else title="本次检测未发现违规行为" type="success" show-icon :closable="false" style="margin-bottom: 20px;" />

      <!-- 高清对比图 -->
      <el-row :gutter="16">
        <el-col :span="12">
          <p style="text-align:center; font-weight:bold; color:#606266; margin-bottom:8px;">原始抓拍图</p>
          <el-image
            :src="detailData.original_image"
            :preview-src-list="[detailData.original_image, detailData.result_image]"
            preview-teleported
            fit="contain"
            style="width:100%; border-radius:6px; border:1px solid #EBEEF5;"
          />
        </el-col>
        <el-col :span="12">
          <p style="text-align:center; font-weight:bold; color:#409EFF; margin-bottom:8px;">AI 识别标注图</p>
          <el-image
            :src="detailData.result_image"
            :preview-src-list="[detailData.original_image, detailData.result_image]"
            preview-teleported
            fit="contain"
            style="width:100%; border-radius:6px; border:2px solid #409EFF;"
          />
        </el-col>
      </el-row>

      <!-- 识别到的标志 -->
      <el-divider content-position="left">识别到的交通标志</el-divider>
      <div>
        <el-tag
          v-for="(sign, i) in detailData.detected_signs.split(',')"
          :key="i"
          size="large"
          effect="dark"
          style="margin: 4px;"
        >{{ sign }}</el-tag>
        <span v-if="!detailData.detected_signs || detailData.detected_signs === '未检测到标志'" style="color:#909399;">无标志</span>
      </div>

      <el-divider />
      <p style="color:#909399; font-size:13px;">检测时间：{{ detailData.create_time }}　记录ID：{{ detailData.id }}</p>
    </div>
  </el-drawer>
</div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Search, Download, Loading, ZoomIn } from '@element-plus/icons-vue'

const baseURL = 'http://localhost:8000'
const isAdmin = computed(() => localStorage.getItem('role') === 'admin')

// 页面状态
const activeTab = ref('detections')
const loading = ref(false)

// 搜索参数
const searchParams = reactive({
  signType: '',
  dateRange: null,
  hasViolation: ''
})

// 分页与数据状态 (全量记录)
const recordPage = reactive({ current: 1, size: 10, total: 0 })
const recordsList = ref([])

// 分页与数据状态 (违规记录)
const violationPage = reactive({ current: 1, size: 10, total: 0 })
const violationsList = ref([])

// 获取全量检测记录
const fetchRecords = async () => {
  loading.value = true
  try {
    const params = {
      page: recordPage.current,
      size: recordPage.size,
      sign_type: searchParams.signType || undefined,
      start_time: searchParams.dateRange ? searchParams.dateRange[0] : undefined,
      end_time: searchParams.dateRange ? searchParams.dateRange[1] : undefined,
      has_violation: searchParams.hasViolation || undefined
    }
    const res = await axios.get(`${baseURL}/api/records`, { params })
    recordsList.value = res.data.data
    recordPage.total = res.data.total
  } catch (error) {
    ElMessage.error('获取检测记录失败')
  } finally {
    loading.value = false
  }
}

// 获取违规记录
const fetchViolations = async () => {
  loading.value = true
  try {
    const params = {
      page: violationPage.current,
      size: violationPage.size,
      start_time: searchParams.dateRange ? searchParams.dateRange[0] : undefined,
      end_time: searchParams.dateRange ? searchParams.dateRange[1] : undefined
    }
    const res = await axios.get(`${baseURL}/api/violations`, { params })
    violationsList.value = res.data.data
    violationPage.total = res.data.total
  } catch (error) {
    ElMessage.error('获取违规记录失败')
  } finally {
    loading.value = false
  }
}

// 触发搜索
const handleSearch = () => {
  recordPage.current = 1
  violationPage.current = 1
  if (activeTab.value === 'detections') {
    fetchRecords()
  } else {
    fetchViolations()
  }
}

// 重置搜索
const resetSearch = () => {
  searchParams.signType = ''
  searchParams.dateRange = null
  searchParams.hasViolation = ''
  handleSearch()
}

// 彻底删除检测记录 (主记录与违规记录会同步删除)
const handleDeleteRecord = async (id) => {
  try {
    // 调用后端我们刚才加的 DELETE 接口
    await axios.delete(`${baseURL}/api/records/${id}`)
    ElMessage.success('记录删除成功')
    
    // 删除成功后，重新去后端拉取最新数据，刷新表格
    fetchRecords() 
  } catch (error) {
    ElMessage.error('删除失败，请检查网络或联系管理员')
    console.error(error)
  }
}

// 切换 Tab 时加载对应数据
const handleTabChange = (tabName) => {
  if (tabName === 'detections' && recordsList.value.length === 0) fetchRecords()
  if (tabName === 'violations' && violationsList.value.length === 0) fetchViolations()
}

// 详情抽屉
const drawerVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref(null)

const openDetail = async (detectId) => {
  drawerVisible.value = true
  detailLoading.value = true
  detailData.value = null
  try {
    const res = await axios.get(`${baseURL}/api/records/${detectId}`)
    detailData.value = res.data
  } catch {
    ElMessage.error('获取详情失败')
    drawerVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

// 导出 CSV（携带当前查询条件）
const exportReport = () => {
  const params = new URLSearchParams()
  if (searchParams.signType) params.append('sign_type', searchParams.signType)
  if (searchParams.dateRange) {
    params.append('start_time', searchParams.dateRange[0])
    params.append('end_time', searchParams.dateRange[1])
  }
  const query = params.toString() ? `?${params.toString()}` : ''
  window.open(`${baseURL}/api/report${query}`, '_blank')
  ElMessage.success('报表下载任务已启动')
}


// 页面加载初始化
onMounted(() => {
  fetchRecords()
})
</script>

<style scoped>
.toolbar-card {
  margin-bottom: 20px;
  border-radius: 8px;
}
.toolbar-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filter-section {
  display: flex;
  align-items: center;
}
.table-card {
  border-radius: 8px;
  min-height: 500px;
}
.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>