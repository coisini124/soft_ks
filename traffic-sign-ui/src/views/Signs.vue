<template>
  <div class="signs-container">
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span class="header-title">系统支持的交通标志库 (共 {{ signsList.length }} 种)</span>
          <div class="header-actions">
            <el-upload
              action="#"
              :auto-upload="false"
              :show-file-list="false"
              accept=".csv,text/csv"
              :on-change="handleImportFile"
            >
              <el-button type="warning" :loading="importLoading">
                <el-icon style="margin-right: 5px;"><Upload /></el-icon> 导入 CSV
              </el-button>
            </el-upload>
            <el-button type="success" @click="exportSigns">
              <el-icon style="margin-right: 5px;"><Download /></el-icon> 导出 CSV
            </el-button>
            <el-button type="primary" @click="handleAdd">
              <el-icon style="margin-right: 5px;"><Plus /></el-icon> 新增交通标志
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="signsList" v-loading="loading" border stripe height="600" style="width: 100%">
        <el-table-column prop="id" label="字典 ID" width="80" align="center" />
        
        <el-table-column prop="sign_code" label="YOLO 标签编码 (英文)" width="200">
          <template #default="scope">
            <el-tag type="info" effect="plain">{{ scope.row.sign_code }}</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="meaning" label="中文含义" width="250" />
        <el-table-column prop="road_section" label="路段" width="180">
          <template #default="scope">
            <span>{{ scope.row.road_section || '未配置' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="direction" label="方向" width="110" />
        
        <el-table-column prop="sign_type" label="标志类型" width="150" align="center">
          <template #default="scope">
            <el-tag :type="getTypeTag(scope.row.sign_type)" effect="dark">
              {{ scope.row.sign_type }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="limit_value" label="限制数值 (用于违规判定)" width="200" align="center">
          <template #default="scope">
            <span v-if="scope.row.limit_value !== null" style="color: #F56C6C; font-weight: bold;">
              {{ scope.row.limit_value }}
            </span>
            <span v-else style="color: #909399;">无数值限制</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" fixed="right" width="180" align="center">
          <template #default="scope">
            <el-button size="small" type="primary" link @click="handleEdit(scope.row)">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            
            <el-popconfirm 
              title="确定要删除这个标志吗？删除后系统将无法识别它！" 
              confirm-button-text="确认删除"
              cancel-button-text="取消"
              confirm-button-type="danger"
              @confirm="handleDelete(scope.row.id)"
            >
              <template #reference>
                <el-button size="small" type="danger" link>
                  <el-icon><Delete /></el-icon> 删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog 
      v-model="dialogVisible" 
      :title="dialogTitle" 
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form 
        ref="formRef" 
        :model="formData" 
        :rules="formRules" 
        label-width="120px"
        @submit.prevent
      >
        <el-form-item label="标签编码" prop="sign_code">
          <el-input v-model="formData.sign_code" placeholder="输入模型训练时的标签，如: pl80" />
        </el-form-item>
        
        <el-form-item label="中文含义" prop="meaning">
          <el-input v-model="formData.meaning" placeholder="输入具体的含义，如: 限制速度80" />
        </el-form-item>
        
        <el-form-item label="标志类型" prop="sign_type">
          <el-select v-model="formData.sign_type" placeholder="请选择类型" style="width: 100%;">
            <el-option label="指示标志" value="指示标志" />
            <el-option label="警告标志" value="警告标志" />
            <el-option label="禁止标志" value="禁止标志" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="限制数值">
          <el-input-number 
            v-model="formData.limit_value" 
            :precision="1" 
            :step="10" 
            style="width: 100%;" 
            placeholder="如果有限速、限高则填入，没有留空"
          />
        </el-form-item>

        <el-divider content-position="left">位置与展示信息</el-divider>
        <el-form-item label="所属路段">
          <el-input v-model="formData.road_section" placeholder="如: G5京昆高速 K120" />
        </el-form-item>
        <el-form-item label="方向">
          <el-input v-model="formData.direction" placeholder="如: 成都方向" />
        </el-form-item>
        <el-form-item label="位置说明">
          <el-input v-model="formData.position_desc" placeholder="如: K120+300 路侧标志" />
        </el-form-item>
        <el-form-item label="建议速度">
          <el-input-number v-model="formData.recommended_speed" :precision="1" :step="10" :min="0" :max="200" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="经纬度">
          <div class="coord-row">
            <el-input-number v-model="formData.latitude" :precision="6" :step="0.0001" :min="-90" :max="90" placeholder="纬度" />
            <el-input-number v-model="formData.longitude" :precision="6" :step="0.0001" :min="-180" :max="180" placeholder="经度" />
          </div>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitForm" :loading="submitLoading">
            确认保存
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Download, Upload } from '@element-plus/icons-vue'
import api, { downloadBlob, getErrorMessage } from '../api/client'

const loading = ref(false)
const signsList = ref([])
const importLoading = ref(false)

// 弹窗与表单状态
const dialogVisible = ref(false)
const dialogTitle = ref('新增标志')
const submitLoading = ref(false)
const formRef = ref(null)

// 表单数据对象
const formData = reactive({
  id: null,
  sign_code: '',
  meaning: '',
  sign_type: '禁止标志',
  limit_value: null,
  road_section: '',
  direction: '',
  position_desc: '',
  latitude: null,
  longitude: null,
  recommended_speed: null
})

// 表单必填校验规则
const formRules = {
  sign_code: [{ required: true, message: '标签编码不能为空', trigger: 'blur' }],
  meaning: [{ required: true, message: '中文含义不能为空', trigger: 'blur' }],
  sign_type: [{ required: true, message: '请选择一种标志类型', trigger: 'change' }]
}

// 辅助函数：根据标志类型返回不同颜色的 Tag
const getTypeTag = (type) => {
  if (type === '指示标志') return 'primary'
  if (type === '警告标志') return 'warning'
  if (type === '禁止标志') return 'danger'
  return 'info'
}

// 获取全部字典数据
const fetchSigns = async () => {
  loading.value = true
  try {
    const res = await api.get('/api/signs')
    signsList.value = res.data
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '获取标志列表失败'))
  } finally {
    loading.value = false
  }
}

// 点击“新增”按钮
const handleAdd = () => {
  dialogTitle.value = '新增交通标志'
  // 清空表单
  Object.assign(formData, {
    id: null,
    sign_code: '',
    meaning: '',
    sign_type: '禁止标志',
    limit_value: null,
    road_section: '',
    direction: '',
    position_desc: '',
    latitude: null,
    longitude: null,
    recommended_speed: null
  })
  dialogVisible.value = true
  // 清除上次的校验红字
  if (formRef.value) formRef.value.clearValidate()
}

// 点击“编辑”按钮
const handleEdit = (row) => {
  dialogTitle.value = '编辑交通标志'
  // 将当前行的数据拷贝到表单中 (回显)
  Object.assign(formData, { ...row })
  dialogVisible.value = true
  if (formRef.value) formRef.value.clearValidate()
}

// 提交表单 (可能是新增，也可能是修改)
const submitForm = async () => {
  if (!formRef.value) return
  
  // 1. 触发前端必填校验
  await formRef.value.validate(async (valid) => {
    if (valid) {
      submitLoading.value = true
      try {
        const payload = Object.fromEntries(
          Object.entries(formData).map(([key, value]) => [key, value === '' ? null : value])
        )
        if (formData.id) {
          await api.put(`/api/signs/${formData.id}`, payload)
          ElMessage.success('修改成功')
        } else {
          await api.post('/api/signs', payload)
          ElMessage.success('新增成功')
        }
        dialogVisible.value = false
        fetchSigns()
      } catch (error) {
        ElMessage.error(getErrorMessage(error, '保存失败，请检查网络'))
      } finally {
        submitLoading.value = false
      }
    }
  })
}

// 删除标志
const handleDelete = async (id) => {
  try {
    await api.delete(`/api/signs/${id}`)
    ElMessage.success('删除成功')
    fetchSigns() // 刷新列表
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '删除失败'))
  }
}

const exportSigns = async () => {
  try {
    const res = await api.get('/api/signs/export', { responseType: 'blob' })
    const disposition = res.headers['content-disposition'] || ''
    const match = disposition.match(/filename=([^;]+)/)
    const filename = match ? decodeURIComponent(match[1].replace(/"/g, '')) : 'sign_dictionary.csv'
    downloadBlob(res.data, filename)
    ElMessage.success('标志字典导出成功')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '标志字典导出失败'))
  }
}

const submitImport = async (file, dryRun) => {
  const formData = new FormData()
  formData.append('file', file)
  const res = await api.post('/api/signs/import', formData, {
    params: { dry_run: dryRun },
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return res.data
}

const handleImportFile = async (uploadFile) => {
  const file = uploadFile.raw
  if (!file) return
  importLoading.value = true
  try {
    const preview = await submitImport(file, true)
    await ElMessageBox.confirm(
      `CSV 校验通过：共 ${preview.total_rows} 行，将新增 ${preview.created} 条、更新 ${preview.updated} 条。确认导入吗？`,
      '导入标志字典',
      {
        confirmButtonText: '确认导入',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    const result = await submitImport(file, false)
    ElMessage.success(`导入完成：新增 ${result.created} 条，更新 ${result.updated} 条`)
    fetchSigns()
  } catch (error) {
    if (error === 'cancel') return
    ElMessage.error(getErrorMessage(error, '标志字典导入失败'))
  } finally {
    importLoading.value = false
  }
}

// 页面加载时拉取数据
onMounted(() => {
  fetchSigns()
})
</script>

<style scoped>
.signs-container {
  /* 外层容器不加 padding，交由 layout 控制 */
}
.table-card {
  border-radius: 8px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.header-title {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.coord-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  width: 100%;
}
</style>
