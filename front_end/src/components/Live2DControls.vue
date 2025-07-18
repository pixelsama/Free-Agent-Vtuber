<template>
  <v-card class="live2d-controls" elevation="2">
    <v-card-text>
      <!-- 模型状态 -->
      <div class="mb-4">
        <v-chip 
          :color="modelLoaded ? 'success' : 'warning'"
          :prepend-icon="modelLoaded ? 'mdi-check-circle' : 'mdi-loading'"
          size="small"
        >
          {{ modelLoaded ? '模型已加载' : '加载中...' }}
        </v-chip>
      </div>

      <!-- 预设文件管理 -->
      <div class="mb-4">
        <v-subheader class="px-0 text-subtitle-2 font-weight-bold">
          <v-icon class="mr-1" size="small">mdi-content-save-settings</v-icon>
          预设文件管理
          <v-spacer></v-spacer>
          <v-btn
            @click="showPresetConfig = !showPresetConfig"
            variant="text"
            size="x-small"
            icon="mdi-cog"
            class="ml-2"
          ></v-btn>
        </v-subheader>
        
        <!-- 预设文件配置面板 -->
        <v-expand-transition>
          <div v-show="showPresetConfig" class="mb-3 pa-3 bg-grey-lighten-5 rounded">
            <div class="text-caption font-weight-bold mb-2">预设文件操作</div>
            
            <!-- 保存预设 -->
            <div class="mb-3">
              <v-text-field
                v-model="newPresetName"
                label="预设文件名称"
                variant="outlined"
                density="compact"
                hide-details
                :placeholder="generateDefaultPresetName()"
                class="mb-2"
              ></v-text-field>
              <v-btn
                @click="savePreset"
                size="small"
                variant="outlined"
                color="primary"
                prepend-icon="mdi-content-save"
                class="mr-2"
              >
                保存当前配置为预设
              </v-btn>
            </div>
            
            <!-- 加载预设 -->
            <div class="mb-3" v-if="savedPresets.length > 0">
              <div class="text-caption mb-2">已保存的预设文件:</div>
              <v-list density="compact" class="bg-white rounded">
                <v-list-item
                  v-for="preset in savedPresets"
                  :key="preset.id"
                  class="px-2"
                >
                  <template v-slot:prepend>
                    <v-icon size="small">mdi-file-cog</v-icon>
                  </template>
                  
                  <v-list-item-title class="text-body-2">{{ preset.name }}</v-list-item-title>
                  <v-list-item-subtitle class="text-caption">{{ preset.modelName }} - {{ preset.createdAt }}</v-list-item-subtitle>
                  
                  <template v-slot:append>
                    <v-btn
                      @click="loadPreset(preset)"
                      size="x-small"
                      variant="text"
                      icon="mdi-play"
                      color="primary"
                      class="mr-1"
                      title="使用此预设"
                    ></v-btn>
                    
                    <v-btn
                      @click="exportPreset(preset)"
                      size="x-small"
                      variant="text"
                      icon="mdi-download"
                      color="info"
                      class="mr-1"
                      title="下载预设文件"
                    ></v-btn>

                    <v-btn
                      @click="deletePreset(preset.name)"
                      size="x-small"
                      variant="text"
                      icon="mdi-delete"
                      color="error"
                      title="删除预设"
                    ></v-btn>
                  </template>
                </v-list-item>
              </v-list>
            </div>
            
            <!-- 导入/导出预设 -->
            <div class="mb-3">
              <v-btn
                @click="importPreset"
                size="small"
                variant="outlined"
                color="info"
                prepend-icon="mdi-import"
              >
                导入预设文件
              </v-btn>
              <input
                ref="presetFileInput"
                type="file"
                accept=".json"
                @change="handlePresetFileImport"
                style="display: none;"
              />
            </div>
          </div>
        </v-expand-transition>
      </div>

      <!-- 动作控制 -->
      <div class="mb-4">
        <v-subheader class="px-0 text-subtitle-2 font-weight-bold">
          <v-icon class="mr-1" size="small">mdi-play-circle</v-icon>
          动作控制
          <v-spacer></v-spacer>
          <v-btn
            @click="showMotionConfig = !showMotionConfig"
            variant="text"
            size="x-small"
            icon="mdi-cog"
            class="ml-2"
          ></v-btn>
        </v-subheader>
        
        <!-- 动作配置面板 -->
        <v-expand-transition>
          <div v-show="showMotionConfig" class="mb-3 pa-3 bg-grey-lighten-5 rounded">
            <div class="text-caption font-weight-bold mb-2">动作文件配置</div>
            
            <!-- 手动输入动作文件名 -->
            <div class="mb-3">
              <v-textarea
                v-model="manualMotionFiles"
                label="手动输入动作文件名"
                variant="outlined"
                density="compact"
                rows="3"
                hide-details
                placeholder="每行一个文件名，例如：&#10;idle_01&#10;tap_body_01&#10;tap_head_01"
                class="mb-2"
              ></v-textarea>
              <v-btn
                @click="parseManualMotionFiles"
                size="small"
                variant="outlined"
                color="primary"
              >
                解析文件名
              </v-btn>
            </div>
            
            <div v-if="availableMotionFiles.length > 0" class="mb-3">
              <div class="text-caption text-primary mb-2">当前可用动作文件 ({{ availableMotionFiles.length }}个):</div>
              <div class="d-flex flex-wrap gap-1">
                <v-chip
                  v-for="file in availableMotionFiles"
                  :key="file.path"
                  size="small"
                  variant="outlined"
                  color="primary"
                  class="text-caption"
                >
                  {{ file.name }}
                </v-chip>
              </div>
            </div>
            
            <!-- 动作管理操作 -->
            <div class="mb-3">
              <div class="d-flex align-center gap-2 mb-2">
                <v-text-field
                  v-model="newMotionName"
                  label="新动作名称"
                  variant="outlined"
                  density="compact"
                  hide-details
                  placeholder="输入动作名称"
                  class="flex-grow-1"
                ></v-text-field>
                <v-btn
                  @click="addNewMotion"
                  variant="outlined"
                  size="small"
                  color="success"
                  :disabled="!newMotionName.trim()"
                >
                  <v-icon size="small" class="mr-1">mdi-plus</v-icon>
                  添加动作
                </v-btn>
              </div>
            </div>
            
            <div v-for="motion in motions" :key="motion.id" class="mb-3">
              <div class="d-flex align-center justify-space-between mb-1">
                <div class="text-caption font-weight-medium">{{ motion.name }}:</div>
                <v-btn
                  @click="removeMotion(motion.id)"
                  variant="text"
                  size="x-small"
                  icon="mdi-delete"
                  color="error"
                  :disabled="motions.length <= 1"
                ></v-btn>
              </div>
              
              <!-- 可用文件快速选择 -->
              <div v-if="availableMotionFiles.length > 0" class="mb-2">
                <div class="text-caption text-grey mb-1">快速选择:</div>
                <div class="d-flex flex-wrap gap-1">
                  <v-btn
                    v-for="file in availableMotionFiles"
                    :key="file.path"
                    size="x-small"
                    variant="outlined"
                    :color="motion.filePath === file.path ? 'success' : 'default'"
                    @click="linkMotionFile(motion.id, file)"
                  >
                    {{ file.name }}
                  </v-btn>
                </div>
              </div>
              
              <!-- 自定义文件上传 -->
              <div class="d-flex align-center gap-2">
                <span class="text-caption" style="min-width: 80px;">自定义文件:</span>
                <v-file-input
                  v-model="motion.file"
                  accept=".motion3.json"
                  variant="outlined"
                  density="compact"
                  hide-details
                  :placeholder="motion.fileName && !motion.file ? `已关联: ${motion.fileName}` : '选择动作文件'"
                  prepend-icon=""
                  append-inner-icon="mdi-file-document"
                  class="flex-grow-1"
                  @update:model-value="(file) => updateMotionFile(motion.id, file)"
                >
                  <template v-slot:selection="{ fileNames }">
                    <span class="text-caption">{{ fileNames[0] || (motion.fileName && !motion.file ? `已关联: ${motion.fileName}` : '未选择文件') }}</span>
                  </template>
                </v-file-input>
                <v-btn
                  v-if="motion.filePath"
                  @click="clearMotionFile(motion.id)"
                  variant="text"
                  size="x-small"
                  icon="mdi-close"
                  color="error"
                ></v-btn>
              </div>
              
              <div v-if="motion.filePath" class="text-caption text-success ml-2 mt-1">
                已关联: {{ motion.fileName || motion.filePath }}
              </div>
              <!-- 调试信息 -->
              <div class="text-caption text-grey ml-2 mt-1">
                调试: filePath={{ motion.filePath || 'null' }}, fileName={{ motion.fileName || 'null' }}
              </div>
            </div>
          </div>
        </v-expand-transition>
        
        <v-row dense>
          <v-col cols="12" v-for="motion in motions" :key="motion.id">
            <div class="d-flex align-center gap-2">
              <v-btn
                :disabled="!modelLoaded"
                @click="playMotion(motion.group, motion.index, motion.id)"
                variant="outlined"
                size="small"
                class="text-caption motion-btn flex-grow-1"
                :class="{ 'has-file': motion.filePath }"
              >
                <v-icon v-if="motion.filePath" size="x-small" class="mr-1">mdi-file-check</v-icon>
                {{ motion.name }}
                <span v-if="motion.filePath" class="text-caption text-grey ml-1">({{ motion.fileName || '已关联' }})</span>
              </v-btn>
              <v-btn
                :disabled="!modelLoaded"
                @click="openClickAreaAssociation(motion.id)"
                variant="outlined"
                size="small"
                color="primary"
                class="text-caption"
                :class="{ 'has-click-areas': motion.clickAreas && motion.clickAreas.length > 0 }"
              >
                <v-icon size="x-small">mdi-cursor-pointer</v-icon>
                <span v-if="motion.clickAreas && motion.clickAreas.length > 0" class="ml-1">({{ motion.clickAreas.length }})</span>
              </v-btn>
            </div>
          </v-col>
        </v-row>
      </div>

      <!-- 表情控制 -->
      <div class="mb-4">
        <v-subheader class="px-0 text-subtitle-2 font-weight-bold">
          <v-icon class="mr-1" size="small">mdi-emoticon-happy</v-icon>
          表情控制
          <v-spacer></v-spacer>
          <v-btn
            @click="showExpressionConfig = !showExpressionConfig"
            variant="text"
            size="x-small"
            icon="mdi-cog"
            class="ml-2"
          ></v-btn>
        </v-subheader>
        
        <!-- 表情配置面板 -->
        <v-expand-transition>
          <div v-if="showExpressionConfig" class="mb-3 pa-3 bg-grey-lighten-5 rounded">
            <div class="d-flex align-center justify-space-between mb-2">
               <h4 class="text-subtitle-2">表情文件关联配置</h4>
               <v-btn
                 size="small"
                 variant="outlined"
                 @click="loadAvailableExpressions"
               >
                 刷新可用文件
               </v-btn>
             </div>
            
            <!-- 手动输入表情文件名 -->
            <div class="mb-3">
              <div class="text-caption text-primary mb-2">手动输入表情文件名:</div>
              <v-textarea
                v-model="manualExpressionFiles"
                label="输入表情文件名（每行一个，不需要.exp3.json后缀）"
                placeholder="例如：\nF01\nF02\nF03\nAngry\nSmile"
                variant="outlined"
                density="compact"
                rows="4"
                hide-details
                class="mb-2"
              ></v-textarea>
              <v-btn
                @click="parseManualExpressionFiles"
                size="small"
                variant="outlined"
                color="primary"
              >
                解析文件名
              </v-btn>
            </div>
            
            <div v-if="availableExpressionFiles.length > 0" class="mb-3">
              <div class="text-caption text-primary mb-2">当前可用表情文件 ({{ availableExpressionFiles.length }}个):</div>
              <div class="d-flex flex-wrap gap-1">
                <v-chip
                  v-for="file in availableExpressionFiles"
                  :key="file.path"
                  size="small"
                  variant="outlined"
                  color="primary"
                  class="text-caption"
                >
                  {{ file.name }}
                </v-chip>
              </div>
            </div>
            
            <!-- 表情管理操作 -->
            <div class="mb-3">
              <div class="d-flex align-center gap-2 mb-2">
                <v-text-field
                  v-model="newExpressionName"
                  label="新表情名称"
                  variant="outlined"
                  density="compact"
                  hide-details
                  placeholder="输入表情名称"
                  class="flex-grow-1"
                ></v-text-field>
                <v-btn
                  @click="addNewExpression"
                  variant="outlined"
                  size="small"
                  color="success"
                  :disabled="!newExpressionName.trim()"
                >
                  <v-icon size="small" class="mr-1">mdi-plus</v-icon>
                  添加表情
                </v-btn>
              </div>
            </div>
            
            <div v-for="expression in expressions" :key="expression.id" class="mb-3">
              <div class="d-flex align-center justify-space-between mb-1">
                <div class="text-caption font-weight-medium">{{ expression.name }}:</div>
                <v-btn
                  @click="removeExpression(expression.id)"
                  variant="text"
                  size="x-small"
                  icon="mdi-delete"
                  color="error"
                  :disabled="expressions.length <= 1"
                ></v-btn>
              </div>
              
              <!-- 可用文件快速选择 -->
              <div v-if="availableExpressionFiles.length > 0" class="mb-2">
                <div class="text-caption text-grey mb-1">快速选择:</div>
                <div class="d-flex flex-wrap gap-1">
                  <v-btn
                    v-for="file in availableExpressionFiles"
                    :key="file.path"
                    size="x-small"
                    variant="outlined"
                    :color="expression.filePath === file.path ? 'success' : 'default'"
                    @click="linkExpressionFile(expression.id, file)"
                  >
                    {{ file.name }}
                  </v-btn>
                </div>
              </div>
              
              <!-- 自定义文件上传 -->
              <div class="d-flex align-center gap-2">
                <span class="text-caption" style="min-width: 80px;">自定义文件:</span>
                <v-file-input
                  v-model="expression.file"
                  accept=".exp3.json"
                  variant="outlined"
                  density="compact"
                  hide-details
                  :placeholder="expression.fileName && !expression.file ? `已关联: ${expression.fileName}` : '选择表情文件'"
                  prepend-icon=""
                  append-inner-icon="mdi-file-document"
                  class="flex-grow-1"
                  @update:model-value="(file) => updateExpressionFile(expression.id, file)"
                >
                  <template v-slot:selection="{ fileNames }">
                    <span class="text-caption">{{ fileNames[0] || (expression.fileName && !expression.file ? `已关联: ${expression.fileName}` : '未选择文件') }}</span>
                  </template>
                </v-file-input>
                <v-btn
                  v-if="expression.filePath"
                  @click="clearExpressionFile(expression.id)"
                  variant="text"
                  size="x-small"
                  icon="mdi-close"
                  color="error"
                ></v-btn>
              </div>
              
              <div v-if="expression.filePath" class="text-caption text-success ml-2 mt-1">
                已关联: {{ expression.fileName }}
              </div>
            </div>
          </div>
        </v-expand-transition>
        
        <v-row dense>
          <v-col cols="12" v-for="expression in expressions" :key="expression.id">
            <div class="d-flex align-center gap-2">
              <v-btn
                :disabled="!modelLoaded"
                @click="setExpression(expression.id)"
                variant="outlined"
                size="small"
                class="text-caption expression-btn flex-grow-1"
                :class="{ 'has-file': expression.filePath }"
              >
                <v-icon v-if="expression.filePath" size="x-small" class="mr-1">mdi-file-check</v-icon>
                {{ expression.name }}
              </v-btn>
              <v-btn
                :disabled="!modelLoaded"
                @click="openClickAreaAssociation(expression.id, 'expression')"
                variant="outlined"
                size="small"
                color="primary"
                class="text-caption"
                :class="{ 'has-click-areas': expression.clickAreas && expression.clickAreas.length > 0 }"
              >
                <v-icon size="x-small">mdi-cursor-pointer</v-icon>
                <span v-if="expression.clickAreas && expression.clickAreas.length > 0" class="ml-1">({{ expression.clickAreas.length }})</span>
              </v-btn>
            </div>
          </v-col>
        </v-row>
      </div>

      <!-- 模型设置 -->
      <div class="mb-4">
        <v-subheader class="px-0 text-subtitle-2 font-weight-bold">
          <v-icon class="mr-1" size="small">mdi-cog</v-icon>
          模型设置
        </v-subheader>
        
        <!-- 模型选择 -->
        <v-select
          v-model="selectedModel"
          :items="availableModels"
          item-title="name"
          item-value="path"
          label="选择模型"
          variant="outlined"
          density="compact"
          @update:model-value="changeModel"
        ></v-select>
        
        <!-- 自动眨眼 -->
        <v-switch
          v-model="autoEyeBlink"
          label="自动眨眼"
          color="primary"
          density="compact"
          @update:model-value="toggleAutoEyeBlink"
        ></v-switch>
        
        <!-- 自动呼吸 -->
        <v-switch
          v-model="autoBreath"
          label="自动呼吸"
          color="primary"
          density="compact"
          @update:model-value="toggleAutoBreath"
        ></v-switch>
        
        <!-- 眼神跟随 -->
        <v-switch
          v-model="eyeTracking"
          label="眼神跟随"
          color="primary"
          density="compact"
          @update:model-value="toggleEyeTracking"
        ></v-switch>
        
        <!-- 模型大小 -->
        <div class="mt-3">
          <v-slider
            v-model="modelScale"
            label="模型大小"
            min="0.1"
            max="3.0"
            step="0.1"
            thumb-label
            :disabled="!modelLoaded"
            @update:model-value="updateModelScale"
          >
            <template v-slot:prepend>
              <v-icon size="small">mdi-resize</v-icon>
            </template>
          </v-slider>
        </div>
      </div>
      
      <!-- 背景设置 -->
      <div class="mb-4">
        <v-subheader class="px-0 text-subtitle-2 font-weight-bold">
          <v-icon class="mr-1" size="small">mdi-image</v-icon>
          背景设置
        </v-subheader>
        
        <!-- 上传背景图片 -->
        <v-file-input
          v-model="backgroundImage"
          label="上传背景图片"
          accept="image/*"
          variant="outlined"
          density="compact"
          prepend-icon="mdi-upload"
          @update:model-value="uploadBackground"
          class="mb-2"
        ></v-file-input>
        
        <!-- 背景透明度 -->
        <v-slider
          v-model="backgroundOpacity"
          label="背景透明度"
          min="0"
          max="1"
          step="0.01"
          thumb-label
          @update:model-value="updateBackgroundOpacity"
        ></v-slider>
        
        <!-- 清除背景 -->
        <v-btn
          variant="outlined"
          color="error"
          size="small"
          prepend-icon="mdi-delete"
          @click="clearBackground"
          :disabled="!hasBackground"
          class="mt-2"
        >
          清除背景
        </v-btn>
        
        <!-- 缓存的背景图片 -->
        <div v-if="cachedBackgrounds.length > 0" class="mt-4">
          <v-subheader class="px-0 text-caption font-weight-bold">
            <v-icon class="mr-1" size="small">mdi-cached</v-icon>
            缓存的背景图片 ({{ cachedBackgrounds.length }})
          </v-subheader>
          
          <div class="cached-backgrounds-grid">
            <div 
              v-for="cache in cachedBackgrounds" 
              :key="cache.id"
              class="cached-background-item"
            >
              <!-- 图片预览 -->
              <div class="image-preview" @click="selectCachedBackground(cache)">
                <img 
                  :src="cache.dataUrl" 
                  :alt="cache.name"
                  class="preview-image"
                />
                <div class="image-overlay">
                  <v-icon color="white" size="large">mdi-play</v-icon>
                </div>
              </div>
              
              <!-- 图片信息 -->
              <div class="image-info">
                <div class="image-name" :title="cache.name">{{ cache.name }}</div>
                <div class="image-size">{{ formatFileSize(cache.size) }}</div>
              </div>
              
              <!-- 删除按钮 -->
              <v-btn
                icon="mdi-delete"
                size="x-small"
                color="error"
                variant="text"
                @click="removeFromCache(cache.id)"
                class="delete-btn"
              ></v-btn>
            </div>
          </div>
          
          <!-- 清空所有缓存 -->
          <v-btn
            variant="outlined"
            color="warning"
            size="small"
            prepend-icon="mdi-delete-sweep"
            @click="clearAllCache"
            class="mt-2"
          >
            清空所有缓存
          </v-btn>
        </div>
      </div>

      <!-- 功能测试 -->
      <div class="mb-4">
        <v-subheader class="px-0 text-subtitle-2 font-weight-bold">
          <v-icon class="mr-1" size="small">mdi-test-tube</v-icon>
          功能测试
        </v-subheader>
        
        <div class="d-flex flex-column gap-2">
          <!-- 口型同步测试 -->
          <v-btn
            @click="testLipSync"
            :disabled="!modelLoaded || isTestingLipSync"
            variant="outlined"
            color="primary"
            size="small"
            prepend-icon="mdi-account-voice"
            block
          >
            {{ isTestingLipSync ? '测试中... (5秒)' : '🎭 测试口型同步' }}
          </v-btn>
          
          <!-- 随机动作测试 -->
          <v-btn
            @click="testRandomMotion"
            :disabled="!modelLoaded"
            variant="outlined"
            color="secondary"
            size="small"
            prepend-icon="mdi-play-circle"
            block
          >
            🎪 播放随机动作
          </v-btn>
          
          <!-- 测试说明 -->
          <div class="text-caption text-medium-emphasis mt-1">
            <v-icon size="x-small" class="mr-1">mdi-information</v-icon>
            口型测试会模拟5秒音频驱动的嘴部动画
          </div>
        </div>
      </div>

      <!-- 调试信息 -->
      <div v-if="showDebugInfo">
        <v-subheader class="px-0 text-subtitle-2 font-weight-bold">
          <v-icon class="mr-1" size="small">mdi-bug</v-icon>
          调试信息
        </v-subheader>
        <v-textarea
          v-model="debugInfo"
          readonly
          variant="outlined"
          density="compact"
          rows="3"
          class="text-caption"
        ></v-textarea>
      </div>
    </v-card-text>

    <v-card-actions>
      <v-btn
        @click="showDebugInfo = !showDebugInfo"
        variant="text"
        size="small"
        prepend-icon="mdi-bug"
      >
        {{ showDebugInfo ? '隐藏' : '显示' }}调试
      </v-btn>
      <v-spacer></v-spacer>
      <v-btn
        @click="resetModel"
        :disabled="!modelLoaded"
        variant="text"
        size="small"
        prepend-icon="mdi-refresh"
      >
        重置
      </v-btn>
    </v-card-actions>
  </v-card>

  <!-- 点击区域关联对话框 -->
  <v-dialog v-model="showClickAreaDialog" max-width="800" persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-cursor-pointer</v-icon>
        为{{ currentAssociationType === 'motion' ? '动作' : '表情' }}"{{ currentMotionForArea?.name }}"设置点击区域关联
      </v-card-title>
      
      <v-card-text>
        <div class="mb-4">
          <v-alert type="info" variant="tonal" class="mb-3">
            <div class="text-body-2">
              <strong>操作说明：</strong><br>
              1. 模型将自动回到默认姿态并静止<br>
              2. 选择要关联的点击区域（可多选）<br>
              3. 重复点击区域可取消选择<br>
              4. 点击确定完成关联
            </div>
          </v-alert>
        </div>
        
        <div class="mb-4">
          <v-subheader class="px-0 text-subtitle-2 font-weight-bold mb-2">
            可用点击区域
          </v-subheader>
          
          <v-row dense>
            <v-col cols="6" sm="4" md="3" v-for="area in availableClickAreas" :key="area.id">
              <div class="position-relative">
                <v-btn
                  @click="toggleClickArea(area.id)"
                  :variant="selectedClickAreas.includes(area.id) ? 'flat' : 'outlined'"
                  :color="getAreaButtonColor(area.id)"
                  size="small"
                  block
                  class="text-caption"
                >
                  <v-icon v-if="selectedClickAreas.includes(area.id)" size="x-small" class="mr-1">mdi-check</v-icon>
                  <v-icon v-else-if="getAreaConflictMotions(area.id).length > 0" size="x-small" class="mr-1">mdi-alert</v-icon>
                  {{ area.name }}
                </v-btn>
                
                <!-- 冲突提示 -->
                <v-tooltip v-if="getAreaConflictMotions(area.id).length > 0" activator="parent" location="top">
                  <div class="text-caption">
                    <strong>该区域已被以下动作关联：</strong><br>
                    {{ getAreaConflictMotions(area.id).map(m => m.name).join('、') }}
                  </div>
                </v-tooltip>
              </div>
            </v-col>
          </v-row>
        </div>
        
        <div v-if="selectedClickAreas.length > 0" class="mb-4">
          <v-subheader class="px-0 text-subtitle-2 font-weight-bold mb-2">
            已选择的区域 ({{ selectedClickAreas.length }}个)
          </v-subheader>
          
          <div class="d-flex flex-wrap gap-2">
            <v-chip
              v-for="areaId in selectedClickAreas"
              :key="areaId"
              :color="availableClickAreas.find(a => a.id === areaId)?.color"
              size="small"
              closable
              @click:close="toggleClickArea(areaId)"
            >
              {{ availableClickAreas.find(a => a.id === areaId)?.name }}
            </v-chip>
          </div>
          
          <!-- 冲突警告 -->
          <div v-if="getSelectedAreasConflicts().length > 0" class="mt-3">
            <v-alert type="warning" variant="tonal" density="compact">
              <div class="text-body-2">
                <strong>区域冲突提醒：</strong><br>
                <div v-for="conflict in getSelectedAreasConflicts()" :key="conflict.areaId" class="mt-1">
                  • <strong>{{ conflict.areaName }}</strong> 已被动作 
                  <span class="text-primary font-weight-bold">{{ conflict.motions.map(m => m.name).join('、') }}</span> 关联
                </div>
                <div class="mt-2 text-caption text-medium-emphasis">
                  点击该区域时将从所有关联的动作中随机选择一个播放
                </div>
              </div>
            </v-alert>
          </div>
        </div>
      </v-card-text>
      
      <v-card-actions>
        <v-btn
          @click="cancelClickAreaAssociation"
          variant="text"
        >
          取消
        </v-btn>
        <v-spacer></v-spacer>
        <v-btn
          @click="confirmClickAreaAssociation"
          color="primary"
          variant="flat"
        >
          {{ selectedClickAreas.length === 0 ? '取消关联' : `确定关联 (${selectedClickAreas.length}个区域)` }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'

// Props
const props = defineProps({
  live2dViewer: {
    type: Object,
    default: null
  },
  modelLoaded: {
    type: Boolean,
    default: false
  }
})

// Emits
const emit = defineEmits(['model-change', 'motions-update', 'expressions-update', 'auto-eye-blink-change', 'auto-breath-change', 'eye-tracking-change', 'model-scale-change', 'background-change'])

// Reactive data
const selectedModel = ref('/src/live2d/models/Haru/Haru.model3.json')
const autoEyeBlink = ref(true)
const autoBreath = ref(true)
const eyeTracking = ref(true)
const modelScale = ref(1.0)
const showDebugInfo = ref(true)
const debugInfo = ref('Live2D 模型调试信息将在这里显示...')
const showExpressionConfig = ref(false)
const showPresetConfig = ref(false)

// 预设文件相关数据
const newPresetName = ref('')
const savedPresets = ref([])
const presetFileInput = ref(null)
const PRESET_CONFIG_KEY = 'live2d-preset-configs'

// 背景相关数据
const backgroundImage = ref(null)
const backgroundOpacity = ref(1.0)
const hasBackground = ref(false)
const cachedBackgrounds = ref([]) // 缓存的背景图片列表

// 点击区域关联相关数据
const showClickAreaDialog = ref(false)
const currentMotionForArea = ref(null)
const currentAssociationType = ref('motion') // 'motion' 或 'expression'
const selectedClickAreas = ref([])
const availableClickAreas = ref([])

// 测试功能相关数据
const isTestingLipSync = ref(false)

// 更新可用的点击区域（从Live2D模型获取）
const updateAvailableClickAreas = () => {
  if (props.live2dViewer && props.live2dViewer.live2dManager && props.live2dViewer.live2dManager.isModelLoaded) {
    const hitAreas = props.live2dViewer.live2dManager.getModelHitAreas()
    const colors = ['#FF5722', '#E91E63', '#2196F3', '#4CAF50', '#FF9800', '#9C27B0', '#607D8B', '#795548', '#009688', '#CDDC39', '#FFC107']
    
    availableClickAreas.value = hitAreas.map((area, index) => ({
      id: area.name, // 使用HitArea的名称作为ID
      name: area.name, // 显示名称也使用HitArea的名称
      color: colors[index % colors.length] // 循环使用颜色
    }))
    
    console.log('Available click areas updated from model:', availableClickAreas.value)
  } else {
    // 如果模型未加载，使用默认区域
    availableClickAreas.value = [
      { id: 'Head', name: 'Head', color: '#FF5722' },
      { id: 'Body', name: 'Body', color: '#2196F3' }
    ]
  }
}

// 可用的动作
const motions = ref([
  { id: 'm01', name: '待机', group: 'Idle', index: 0, file: null, filePath: null, fileName: null, clickAreas: [] },
  { id: 'm02', name: '点击身体', group: 'TapBody', index: 0, file: null, filePath: null, fileName: null, clickAreas: [] },
  { id: 'm03', name: '点击头部', group: 'TapHead', index: 0, file: null, filePath: null, fileName: null, clickAreas: [] },
  { id: 'm04', name: '挥手', group: 'Flick', index: 0, file: null, filePath: null, fileName: null, clickAreas: [] }
])

// 可用的表情
const expressions = ref([
  { id: 'f01', name: '开心', file: null, filePath: null, fileName: null, clickAreas: [] },
  { id: 'f02', name: '生气', file: null, filePath: null, fileName: null, clickAreas: [] },
  { id: 'f03', name: '惊讶', file: null, filePath: null, fileName: null, clickAreas: [] },
  { id: 'f04', name: '伤心', file: null, filePath: null, fileName: null, clickAreas: [] }
])

// 可用的模型
const availableModels = ref([
  {
    name: 'Haru',
    path: '/src/live2d/models/Haru/Haru.model3.json'
  },
  {
    name: 'Hiyori',
    path: '/src/live2d/models/Hiyori/Hiyori.model3.json'
  },
  {
    name: 'Mao',
    path: '/src/live2d/models/Mao/Mao.model3.json'
  },
  {
    name: 'Mark',
    path: '/src/live2d/models/Mark/Mark.model3.json'
  },
  {
    name: 'Natori',
    path: '/src/live2d/models/Natori/Natori.model3.json'
  },
  {
    name: 'Rice',
    path: '/src/live2d/models/Rice/Rice.model3.json'
  },
  {
    name: 'Wanko',
    path: '/src/live2d/models/Wanko/Wanko.model3.json'
  }
])

// 播放动作
const playMotion = (motionGroup, motionIndex, motionId) => {
  if (props.live2dViewer) {
    const motion = motions.value.find(m => m.id === motionId)
    
    if (motion && motion.filePath) {
      // 如果有关联的文件，使用自定义动作文件
      props.live2dViewer.setMotionFromFile(motion.filePath)
      updateDebugInfo(`播放动作: ${motion.name} (使用文件: ${motion.fileName})`)
    } else {
      // 使用默认动作
      const manager = props.live2dViewer.getManager()
      if (manager && manager.isModelLoaded) {
        manager.startMotion(motionGroup, motionIndex, 2)
        updateDebugInfo(`播放动作: ${motionGroup}[${motionIndex}] (默认)`)
      } else {
        console.warn('Model not loaded yet')
        updateDebugInfo('模型尚未加载完成')
      }
    }
  }
}

// 设置表情
const setExpression = (expressionId) => {
  if (props.live2dViewer) {
    const expression = expressions.value.find(exp => exp.id === expressionId)
    
    if (expression && expression.filePath) {
      // 如果有关联的文件，使用自定义表情文件
      props.live2dViewer.setExpressionFromFile(expression.filePath)
      updateDebugInfo(`设置表情: ${expression.name} (使用文件: ${expression.fileName})`)
    } else {
      // 使用默认表情
      props.live2dViewer.setExpression(expressionId)
      updateDebugInfo(`设置表情: ${expressionId} (默认)`)
    }
  }
}

// 自动检测逻辑已移除，请使用手动输入功能

// 可用的表情文件列表
const availableExpressionFiles = ref([])

// 手动输入的表情文件名
const manualExpressionFiles = ref('')

// 新表情名称输入
const newExpressionName = ref('')

// 动作配置面板显示状态
const showMotionConfig = ref(false)

// 可用的动作文件列表
const availableMotionFiles = ref([])

// 手动输入的动作文件名
const manualMotionFiles = ref('')

// 新动作名称输入
const newMotionName = ref('')

// 加载当前模型的表情文件
const loadAvailableExpressions = async () => {
  // 清空当前列表
  availableExpressionFiles.value = []
  updateDebugInfo('已清空表情文件列表，请使用手动输入功能添加表情文件')
}

// 解析手动输入的表情文件名
const parseManualExpressionFiles = () => {
  if (!manualExpressionFiles.value.trim()) {
    updateDebugInfo('请输入表情文件名')
    return
  }
  
  const currentModelPath = selectedModel.value
  if (!currentModelPath) {
    updateDebugInfo('请先选择模型')
    return
  }
  
  // 从模型路径中提取模型目录
  const modelDir = currentModelPath.substring(0, currentModelPath.lastIndexOf('/'))
  
  // 解析输入的文件名
  const fileNames = manualExpressionFiles.value
    .split('\n')
    .map(name => name.trim())
    .filter(name => name.length > 0)
  
  // 转换为表情文件对象
  const expressionFiles = fileNames.map(name => {
    const fileName = name.endsWith('.exp3.json') ? name : `${name}.exp3.json`
    return {
      name: name.replace('.exp3.json', ''),
      path: `${modelDir}/expressions/${fileName}`,
      fileName: fileName
    }
  })
  
  availableExpressionFiles.value = expressionFiles
  updateDebugInfo(`手动添加了 ${expressionFiles.length} 个表情文件`)
}

// 添加新表情
const addNewExpression = () => {
  if (!newExpressionName.value.trim()) {
    updateDebugInfo('请输入表情名称')
    return
  }
  
  // 检查名称是否已存在
  const existingExpression = expressions.value.find(exp => exp.name === newExpressionName.value.trim())
  if (existingExpression) {
    updateDebugInfo('表情名称已存在，请使用其他名称')
    return
  }
  
  // 生成新的ID
  const newId = `f${String(expressions.value.length + 1).padStart(2, '0')}`
  
  // 添加新表情
  expressions.value.push({
    id: newId,
    name: newExpressionName.value.trim(),
    file: null,
    filePath: null,
    fileName: null,
    clickAreas: []
  })
  
  // 清空输入框
  newExpressionName.value = ''
  
  updateDebugInfo(`已添加新表情: ${expressions.value[expressions.value.length - 1].name}`)
  saveExpressionConfig()
}

// 删除表情
const removeExpression = (expressionId) => {
  if (expressions.value.length <= 1) {
    updateDebugInfo('至少需要保留一个表情')
    return
  }
  
  const expressionIndex = expressions.value.findIndex(exp => exp.id === expressionId)
  if (expressionIndex === -1) {
    updateDebugInfo('未找到要删除的表情')
    return
  }
  
  const expressionName = expressions.value[expressionIndex].name
  expressions.value.splice(expressionIndex, 1)
  
  updateDebugInfo(`已删除表情: ${expressionName}`)
  saveExpressionConfig()
}

// 解析手动输入的动作文件名
const parseManualMotionFiles = () => {
  if (!manualMotionFiles.value.trim()) {
    updateDebugInfo('请输入动作文件名')
    return
  }
  
  const currentModelPath = selectedModel.value
  if (!currentModelPath) {
    updateDebugInfo('请先选择模型')
    return
  }
  
  // 从模型路径中提取模型目录
  const modelDir = currentModelPath.substring(0, currentModelPath.lastIndexOf('/'))
  
  // 解析输入的文件名
  const fileNames = manualMotionFiles.value
    .split('\n')
    .map(name => name.trim())
    .filter(name => name.length > 0)
  
  // 转换为动作文件对象
  const motionFiles = fileNames.map(name => {
    const fileName = name.endsWith('.motion3.json') ? name : `${name}.motion3.json`
    return {
      name: name.replace('.motion3.json', ''),
      path: `${modelDir}/motions/${fileName}`,
      fileName: fileName
    }
  })
  
  availableMotionFiles.value = motionFiles
  updateDebugInfo(`手动添加了 ${motionFiles.length} 个动作文件`)
}

// 添加新动作
const addNewMotion = () => {
  if (!newMotionName.value.trim()) {
    updateDebugInfo('请输入动作名称')
    return
  }
  
  // 检查名称是否已存在
  const existingMotion = motions.value.find(motion => motion.name === newMotionName.value.trim())
  if (existingMotion) {
    updateDebugInfo('动作名称已存在，请使用其他名称')
    return
  }
  
  // 生成新的ID
  const newId = `m${String(motions.value.length + 1).padStart(2, '0')}`
  
  // 添加新动作
  motions.value.push({
    id: newId,
    name: newMotionName.value.trim(),
    group: 'Custom',
    index: 0,
    file: null,
    filePath: null,
    fileName: null
  })
  
  // 清空输入框
  newMotionName.value = ''
  
  updateDebugInfo(`已添加新动作: ${motions.value[motions.value.length - 1].name}`)
  saveMotionConfig()
}

// 删除动作
const removeMotion = (motionId) => {
  if (motions.value.length <= 1) {
    updateDebugInfo('至少需要保留一个动作')
    return
  }
  
  const motionIndex = motions.value.findIndex(motion => motion.id === motionId)
  if (motionIndex === -1) {
    updateDebugInfo('未找到要删除的动作')
    return
  }
  
  const motionName = motions.value[motionIndex].name
  motions.value.splice(motionIndex, 1)
  
  updateDebugInfo(`已删除动作: ${motionName}`)
  saveMotionConfig()
}

// 关联动作文件
const linkMotionFile = async (motionId, motionFile) => {
  const motion = motions.value.find(m => m.id === motionId)
  if (!motion || !motionFile) return
  
  try {
    // 尝试从路径获取文件内容
    const response = await fetch(motionFile.path)
    if (response.ok) {
      const blob = await response.blob()
      const file = new File([blob], motionFile.fileName, { type: 'application/json' })
      
      // 使用统一的文件更新函数
      await updateMotionFile(motionId, [file])
    } else {
      // 如果无法获取文件内容，只设置路径信息
      motion.filePath = motionFile.path
      motion.fileName = motionFile.fileName
      motion.file = null // 明确设置为null
      
      updateDebugInfo(`动作 ${motion.name} 已关联文件路径: ${motionFile.fileName} (无法加载文件内容)`)
      saveMotionConfig()
    }
  } catch (error) {
    // 如果获取文件失败，只设置路径信息
    motion.filePath = motionFile.path
    motion.fileName = motionFile.fileName
    motion.file = null // 明确设置为null
    
    updateDebugInfo(`动作 ${motion.name} 已关联文件路径: ${motionFile.fileName} (无法加载文件内容)`)
    saveMotionConfig()
  }
}

// 更新动作文件关联
const updateMotionFile = async (motionId, fileArray) => {
  const motion = motions.value.find(m => m.id === motionId)
  if (!motion || !fileArray || fileArray.length === 0) return
  
  const file = fileArray[0]
  
  try {
    // 读取文件内容以验证格式
    const text = await file.text()
    const motionData = JSON.parse(text)
    
    // 简单验证是否为动作文件
    if (!motionData.Version || !motionData.Meta) {
      updateDebugInfo('文件格式不正确，请选择有效的.motion3.json文件')
      return
    }
    
    // 创建文件URL
    const fileUrl = URL.createObjectURL(file)
    
    // 更新动作配置
    motion.file = fileArray // 保存文件对象数组
    motion.filePath = fileUrl
    motion.fileName = file.name
    
    updateDebugInfo(`动作 ${motion.name} 已关联文件: ${file.name}`)
    saveMotionConfig()
    
  } catch (error) {
    console.error('Failed to read motion file:', error)
    updateDebugInfo('读取动作文件失败，请检查文件格式')
  }
}

// 清除动作文件关联
const clearMotionFile = (motionId) => {
  const motion = motions.value.find(m => m.id === motionId)
  if (!motion) return
  
  // 如果是blob URL，需要释放
  if (motion.filePath && motion.filePath.startsWith('blob:')) {
    URL.revokeObjectURL(motion.filePath)
  }
  
  motion.file = null
  motion.filePath = null
  motion.fileName = null
  
  updateDebugInfo(`已清除动作 ${motion.name} 的文件关联`)
  saveMotionConfig()
}

// 打开点击区域关联对话框
const openClickAreaAssociation = (itemId, type = 'motion') => {
  let item = null
  
  if (type === 'motion') {
    item = motions.value.find(m => m.id === itemId)
  } else if (type === 'expression') {
    item = expressions.value.find(e => e.id === itemId)
  }
  
  if (!item) return
  
  currentMotionForArea.value = item
  currentAssociationType.value = type
  // 确保clickAreas属性存在
  if (!item.clickAreas) {
    item.clickAreas = []
  }
  selectedClickAreas.value = [...item.clickAreas]
  showClickAreaDialog.value = true
  
  const itemType = type === 'motion' ? '动作' : '表情'
  console.log(`打开点击区域关联对话框 - ${itemType}: ${item.name}, 当前关联区域:`, item.clickAreas)
  
  // 让模型回到默认姿态并静止
  if (props.live2dViewer) {
    const manager = props.live2dViewer.getManager()
    if (manager && manager.isModelLoaded) {
      // 停止当前动作，回到默认姿态
      manager.startMotion('Idle', 0, 3)
      updateDebugInfo(`模型已回到默认姿态，准备设置点击区域关联`)
    }
  }
}

// 切换点击区域选择
const toggleClickArea = (areaId) => {
  const index = selectedClickAreas.value.indexOf(areaId)
  if (index > -1) {
    // 如果已选择，则取消选择
    selectedClickAreas.value.splice(index, 1)
  } else {
    // 如果未选择，则添加选择
    selectedClickAreas.value.push(areaId)
  }
}

// 获取区域冲突的动作列表
const getAreaConflictMotions = (areaId) => {
  if (!currentMotionForArea.value) return []
  
  return motions.value.filter(motion => 
    motion.id !== currentMotionForArea.value.id && 
    motion.clickAreas && 
    motion.clickAreas.includes(areaId)
  )
}

// 获取区域按钮颜色
const getAreaButtonColor = (areaId) => {
  if (selectedClickAreas.value.includes(areaId)) {
    return availableClickAreas.value.find(a => a.id === areaId)?.color || 'primary'
  }
  
  const conflictMotions = getAreaConflictMotions(areaId)
  if (conflictMotions.length > 0) {
    return 'warning'
  }
  
  return 'default'
}

// 获取已选择区域的冲突信息
const getSelectedAreasConflicts = () => {
  const conflicts = []
  
  for (const areaId of selectedClickAreas.value) {
    const conflictMotions = getAreaConflictMotions(areaId)
    if (conflictMotions.length > 0) {
      const areaName = availableClickAreas.value.find(a => a.id === areaId)?.name || areaId
      conflicts.push({
        areaId,
        areaName,
        motions: conflictMotions
      })
    }
  }
  
  return conflicts
}

// 取消点击区域关联
const cancelClickAreaAssociation = () => {
  showClickAreaDialog.value = false
  currentMotionForArea.value = null
  selectedClickAreas.value = []
}

// 确认点击区域关联
const confirmClickAreaAssociation = () => {
  if (!currentMotionForArea.value) return
  
  const itemType = currentAssociationType.value === 'motion' ? '动作' : '表情'
  console.log(`确认关联 - ${itemType}: ${currentMotionForArea.value.name}, 选择的区域:`, selectedClickAreas.value)
  
  // 更新项目的点击区域关联
  currentMotionForArea.value.clickAreas = [...selectedClickAreas.value]
  
  console.log(`关联完成 - ${itemType}: ${currentMotionForArea.value.name}, 最终关联区域:`, currentMotionForArea.value.clickAreas)
  
  let debugMessage
  if (selectedClickAreas.value.length === 0) {
    debugMessage = `${itemType} ${currentMotionForArea.value.name} 已取消所有点击区域关联`
  } else {
    const areaNames = selectedClickAreas.value.map(areaId => 
      availableClickAreas.value.find(a => a.id === areaId)?.name
    ).join('、')
    debugMessage = `${itemType} ${currentMotionForArea.value.name} 已关联点击区域: ${areaNames}`
  }
  
  updateDebugInfo(debugMessage)
  
  // 保存配置
  if (currentAssociationType.value === 'motion') {
    saveMotionConfig()
  } else {
    saveExpressionConfig()
  }
  
  // 关闭对话框
  showClickAreaDialog.value = false
  currentMotionForArea.value = null
  selectedClickAreas.value = []
}

// 保存动作配置
const saveMotionConfig = () => {
  const config = {
    motions: motions.value.map(motion => ({
      id: motion.id,
      name: motion.name,
      group: motion.group,
      index: motion.index,
      filePath: motion.filePath,
      fileName: motion.fileName,
      clickAreas: motion.clickAreas || []
    }))
  }
  
  console.log('保存动作配置:', config)
  localStorage.setItem('live2d-motion-config', JSON.stringify(config))
  
  // 通知父组件动作数据已更新
  emit('motions-update', motions.value)
  emit('expressions-update', expressions.value)
}

// 关联表情文件
const linkExpressionFile = async (expressionId, expressionFile) => {
  const expression = expressions.value.find(exp => exp.id === expressionId)
  if (!expression || !expressionFile) return
  
  try {
    // 尝试从路径获取文件内容
    const response = await fetch(expressionFile.path)
    if (response.ok) {
      const blob = await response.blob()
      const file = new File([blob], expressionFile.fileName, { type: 'application/json' })
      
      // 使用统一的文件更新函数
      await updateExpressionFile(expressionId, [file])
    } else {
      // 如果无法获取文件内容，只设置路径信息
      expression.filePath = expressionFile.path
      expression.fileName = expressionFile.fileName
      expression.file = null // 明确设置为null
      
      updateDebugInfo(`表情 ${expression.name} 已关联文件路径: ${expressionFile.fileName} (无法加载文件内容)`)
      saveExpressionConfig()
    }
  } catch (error) {
    // 如果获取文件失败，只设置路径信息
    expression.filePath = expressionFile.path
    expression.fileName = expressionFile.fileName
    expression.file = null // 明确设置为null
    
    updateDebugInfo(`表情 ${expression.name} 已关联文件路径: ${expressionFile.fileName} (无法加载文件内容)`)
    saveExpressionConfig()
  }
}

// 更新表情文件关联
const updateExpressionFile = async (expressionId, fileArray) => {
  const expression = expressions.value.find(exp => exp.id === expressionId)
  if (!expression) return
  
  if (!fileArray || fileArray.length === 0) {
    // 清除文件关联
    expression.file = null
    expression.filePath = null
    expression.fileName = null
    updateDebugInfo(`清除了表情 ${expression.name} 的文件关联`)
    saveExpressionConfig()
    return
  }
  
  const file = fileArray[0]
  
  // 验证文件类型
  if (!file.name.endsWith('.exp3.json')) {
    updateDebugInfo(`错误: 请选择 .exp3.json 格式的表情文件`)
    return
  }
  
  try {
    // 读取文件内容进行验证
    const fileContent = await readFileAsText(file)
    const expressionData = JSON.parse(fileContent)
    
    // 验证是否为有效的Live2D表情文件
    if (!expressionData.Type || expressionData.Type !== 'Live2D Expression') {
      updateDebugInfo(`错误: 不是有效的Live2D表情文件`)
      return
    }
    
    // 创建文件URL
    const fileUrl = URL.createObjectURL(file)
    
    // 更新表情配置
    expression.file = fileArray // 保存文件对象数组
    expression.filePath = fileUrl
    expression.fileName = file.name
    
    updateDebugInfo(`表情 ${expression.name} 已关联文件: ${file.name}`)
    saveExpressionConfig()
    
  } catch (error) {
    console.error('Failed to process expression file:', error)
    updateDebugInfo(`错误: 无法处理表情文件 - ${error.message}`)
  }
}

// 清除表情文件关联
const clearExpressionFile = (expressionId) => {
  const expression = expressions.value.find(exp => exp.id === expressionId)
  if (!expression) return
  
  // 释放文件URL
  if (expression.filePath) {
    URL.revokeObjectURL(expression.filePath)
  }
  
  expression.file = null
  expression.filePath = null
  expression.fileName = null
  
  updateDebugInfo(`清除了表情 ${expression.name} 的文件关联`)
  saveExpressionConfig()
}

// 读取文件为文本
const readFileAsText = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsText(file)
  })
}

// 切换模型
const changeModel = (modelPath) => {
  selectedModel.value = modelPath
  emit('model-change', modelPath)
  updateDebugInfo(`切换模型: ${modelPath}`)
  // 切换模型后自动加载可用表情文件
  setTimeout(() => {
    loadAvailableExpressions()
  }, 1000) // 等待模型加载完成
}

// 切换自动眨眼
const toggleAutoEyeBlink = (enabled) => {
  if (props.live2dViewer) {
    const manager = props.live2dViewer.getManager()
    if (manager) {
      manager.setAutoEyeBlinkEnable(enabled)
      console.log(`自动眨眼: ${enabled ? '开启' : '关闭'}`)
      updateDebugInfo(`自动眨眼: ${enabled ? '开启' : '关闭'}`)
    }
  }
}

// 切换自动呼吸
const toggleAutoBreath = (enabled) => {
  if (props.live2dViewer) {
    const manager = props.live2dViewer.getManager()
    if (manager) {
      manager.setAutoBreathEnable(enabled)
      console.log(`自动呼吸: ${enabled ? '开启' : '关闭'}`)
      updateDebugInfo(`自动呼吸: ${enabled ? '开启' : '关闭'}`)
    }
  }
}

// 切换眼神跟随
const toggleEyeTracking = (enabled) => {
  if (props.live2dViewer) {
    const manager = props.live2dViewer.getManager()
    if (manager && manager.isModelLoaded) {
      manager.setEyeTracking(enabled)
      console.log(`眼神跟随: ${enabled ? '开启' : '关闭'}`)
      updateDebugInfo(`眼神跟随: ${enabled ? '开启' : '关闭'}`)
    }
  }
}

// 更新模型大小
const updateModelScale = (scale) => {
  if (props.live2dViewer) {
    const manager = props.live2dViewer.getManager()
    if (manager && manager.isModelLoaded) {
      manager.setModelScale(scale)
      console.log(`模型大小: ${scale}`)
      updateDebugInfo(`模型大小调整为: ${scale}`)
      // 保存模型配置
      saveModelConfig()
    }
  }
}

// 重置模型
const resetModel = () => {
  if (props.live2dViewer) {
    // 重置到默认状态
    setExpression('f01')
    playMotion('Idle', 0)
    
    // 重置模型大小
    modelScale.value = 1.0
    updateModelScale(1.0)
    
    updateDebugInfo('模型已重置到默认状态')
    // 保存重置后的配置
    saveModelConfig()
  }
}

// 更新调试信息
const updateDebugInfo = (message) => {
  const timestamp = new Date().toLocaleTimeString()
  debugInfo.value = `[${timestamp}] ${message}\n${debugInfo.value}`
  
  // 限制调试信息长度
  const lines = debugInfo.value.split('\n')
  if (lines.length > 10) {
    debugInfo.value = lines.slice(0, 10).join('\n')
  }
}

// 本地存储工具函数
const CACHE_KEY = 'live2d_cached_backgrounds'
const EXPRESSION_CONFIG_KEY = 'live2d_expression_config'

// 保存缓存到本地存储
const saveCacheToStorage = () => {
  try {
    const cacheData = cachedBackgrounds.value.map(item => ({
      id: item.id,
      name: item.name,
      dataUrl: item.dataUrl,
      size: item.size,
      type: item.type,
      uploadTime: item.uploadTime
    }))
    localStorage.setItem(CACHE_KEY, JSON.stringify(cacheData))
    updateDebugInfo(`已保存 ${cacheData.length} 个缓存图片到本地存储`)
  } catch (error) {
    console.error('保存缓存失败:', error)
    updateDebugInfo(`保存缓存失败: ${error.message}`)
  }
}

// 从本地存储加载缓存
const loadCacheFromStorage = () => {
  try {
    const stored = localStorage.getItem(CACHE_KEY)
    if (stored) {
      const cacheData = JSON.parse(stored)
      cachedBackgrounds.value = cacheData
      updateDebugInfo(`从本地存储加载了 ${cacheData.length} 个缓存图片`)
    }
  } catch (error) {
    console.error('加载缓存失败:', error)
    updateDebugInfo(`加载缓存失败: ${error.message}`)
  }
}

// 将文件转换为Base64数据URL
const fileToDataUrl = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

// 从数据URL创建文件对象
const dataUrlToFile = (dataUrl, filename, mimeType) => {
  const arr = dataUrl.split(',')
  const bstr = atob(arr[1])
  let n = bstr.length
  const u8arr = new Uint8Array(n)
  while (n--) {
    u8arr[n] = bstr.charCodeAt(n)
  }
  return new File([u8arr], filename, { type: mimeType })
}

// 添加图片到缓存
const addToCache = async (file) => {
  try {
    // 检查是否已经存在相同的文件
    const existingIndex = cachedBackgrounds.value.findIndex(item => 
      item.name === file.name && item.size === file.size
    )
    
    if (existingIndex !== -1) {
      updateDebugInfo(`图片 ${file.name} 已存在于缓存中`)
      return
    }
    
    // 转换为Base64数据URL
    const dataUrl = await fileToDataUrl(file)
    
    // 创建缓存项
    const cacheItem = {
      id: Date.now().toString(), // 使用时间戳作为唯一ID
      name: file.name,
      dataUrl: dataUrl,
      size: file.size,
      type: file.type,
      uploadTime: new Date().toISOString()
    }
    
    // 添加到缓存数组
    cachedBackgrounds.value.push(cacheItem)
    
    // 保存到本地存储
    saveCacheToStorage()
    
    updateDebugInfo(`图片 ${file.name} 已添加到缓存`)
  } catch (error) {
    console.error('添加到缓存失败:', error)
    updateDebugInfo(`添加到缓存失败: ${error.message}`)
  }
}

// 从缓存中删除图片
const removeFromCache = (cacheId) => {
  const index = cachedBackgrounds.value.findIndex(item => item.id === cacheId)
  if (index !== -1) {
    const removedItem = cachedBackgrounds.value.splice(index, 1)[0]
    saveCacheToStorage()
    updateDebugInfo(`已从缓存中删除图片: ${removedItem.name}`)
  }
}

// 选择缓存的图片作为背景
const selectCachedBackground = async (cacheItem) => {
  try {
    // 从数据URL创建文件对象
    const file = dataUrlToFile(cacheItem.dataUrl, cacheItem.name, cacheItem.type)
    
    if (!props.live2dViewer) {
      updateDebugInfo('错误: Live2D Viewer 未传递')
      return
    }
    
    const manager = props.live2dViewer.getManager()
    if (!manager) {
      updateDebugInfo('错误: 无法获取 Live2D 管理器')
      return
    }
    
    if (!manager.isInitialized) {
      updateDebugInfo('错误: Live2D管理器未初始化')
      return
    }
    
    updateDebugInfo(`正在应用缓存背景: ${cacheItem.name}`)
    const success = await manager.loadBackgroundImage(file)
    
    if (success) {
      hasBackground.value = true
      backgroundImage.value = [file]
      updateDebugInfo(`缓存背景应用成功: ${cacheItem.name}`)
    } else {
      updateDebugInfo('缓存背景应用失败')
    }
  } catch (error) {
    console.error('应用缓存背景失败:', error)
    updateDebugInfo(`应用缓存背景失败: ${error.message}`)
  }
}

// 清空所有缓存
const clearAllCache = () => {
  cachedBackgrounds.value = []
  saveCacheToStorage()
  updateDebugInfo('已清空所有缓存图片')
}

// 保存表情配置到本地存储
const saveExpressionConfig = () => {
  try {
    const config = expressions.value.map(exp => ({
      id: exp.id,
      name: exp.name,
      fileName: exp.fileName,
      filePath: exp.filePath,
      clickAreas: exp.clickAreas || [],
      // 注意：不保存 file 对象，因为它包含对象引用，但保存 filePath 用于预设配置
    }))
    localStorage.setItem(EXPRESSION_CONFIG_KEY, JSON.stringify(config))
    updateDebugInfo(`已保存表情配置`)
    
    // 通知父组件表情数据已更新
    emit('expressions-update', expressions.value)
  } catch (error) {
    console.error('保存表情配置失败:', error)
    updateDebugInfo(`保存表情配置失败: ${error.message}`)
  }
}

// 从本地存储加载表情配置
const loadExpressionConfig = () => {
  try {
    const stored = localStorage.getItem(EXPRESSION_CONFIG_KEY)
    if (stored) {
      const config = JSON.parse(stored)
      // 只恢复文件名信息和点击区域关联，实际文件需要用户重新选择
      config.forEach(savedExp => {
        const expression = expressions.value.find(exp => exp.id === savedExp.id)
        if (expression) {
          // 恢复点击区域关联
          if (savedExp.clickAreas) {
            expression.clickAreas = savedExp.clickAreas
          }
          
          // 恢复文件关联信息
          if (savedExp.fileName) {
            expression.fileName = savedExp.fileName
          }
          if (savedExp.filePath) {
            expression.filePath = savedExp.filePath
            updateDebugInfo(`表情 ${expression.name} 已恢复文件关联: ${savedExp.fileName}`)
          }
         }
       })
       
       // 通知父组件表情数据已加载
       emit('expressions-update', expressions.value)
    }
  } catch (error) {
    console.error('加载表情配置失败:', error)
    updateDebugInfo(`加载表情配置失败: ${error.message}`)
  }
}

// 从本地存储加载动作配置
const loadMotionConfig = () => {
  try {
    const stored = localStorage.getItem('live2d-motion-config')
    if (stored) {
      const config = JSON.parse(stored)
      if (config.motions) {
        config.motions.forEach(savedMotion => {
          const motion = motions.value.find(m => m.id === savedMotion.id)
          if (motion) {
            // 恢复点击区域关联
            if (savedMotion.clickAreas) {
              motion.clickAreas = savedMotion.clickAreas
            }
            // 恢复文件关联信息
            if (savedMotion.fileName) {
              motion.fileName = savedMotion.fileName
            }
            if (savedMotion.filePath) {
              motion.filePath = savedMotion.filePath
              updateDebugInfo(`动作 ${motion.name} 已恢复文件关联: ${savedMotion.fileName}`)
            }
          }
        })
      }
    }
    
    // 通知父组件动作数据已加载
    emit('motions-update', motions.value)
    emit('expressions-update', expressions.value)
  } catch (error) {
    console.error('加载动作配置失败:', error)
    updateDebugInfo(`加载动作配置失败: ${error.message}`)
  }
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 上传背景图片
const uploadBackground = async (fileOrFiles) => {
  updateDebugInfo('开始处理背景图片上传...')
  updateDebugInfo(`接收到的参数类型: ${typeof fileOrFiles}, 值: ${JSON.stringify(fileOrFiles)}`)
  
  // v-file-input 可能传递单个文件或文件数组
  let file = null
  if (Array.isArray(fileOrFiles)) {
    if (fileOrFiles.length === 0) {
      updateDebugInfo('错误: 没有选择文件')
      return
    }
    file = fileOrFiles[0]
  } else {
    file = fileOrFiles
  }
  
  if (!file) {
    updateDebugInfo('错误: 文件为空')
    return
  }
  
  updateDebugInfo(`选择的文件: ${file.name}, 类型: ${file.type}, 大小: ${file.size} bytes`)
  
  // 验证文件类型
  if (!file.type.startsWith('image/')) {
    updateDebugInfo('错误: 请选择图片文件')
    return
  }
  
  try {
    if (!props.live2dViewer) {
      updateDebugInfo('错误: Live2D Viewer 未传递')
      return
    }
    
    const manager = props.live2dViewer.getManager()
    if (!manager) {
      updateDebugInfo('错误: 无法获取 Live2D 管理器')
      return
    }
    
    if (!manager.isInitialized) {
      updateDebugInfo('错误: Live2D管理器未初始化')
      return
    }
    
    updateDebugInfo('正在加载背景图片...')
    const success = await manager.loadBackgroundImage(file)
    
    if (success) {
      hasBackground.value = true
      // 保存文件信息，这样重新打开控制面板时可以看到上传的图片
      backgroundImage.value = [file]
      
      // 将图片添加到缓存
      await addToCache(file)
      
      updateDebugInfo(`背景图片上传成功: ${file.name}`)
    } else {
      updateDebugInfo('背景图片上传失败')
    }
  } catch (error) {
    console.error('Upload background error:', error)
    updateDebugInfo(`背景图片上传失败: ${error.message}`)
  }
}

// 更新背景透明度
const updateBackgroundOpacity = (opacity) => {
  if (props.live2dViewer) {
    const manager = props.live2dViewer.getManager()
    if (manager && manager.isInitialized) {
      manager.setBackgroundOpacity(opacity)
      updateDebugInfo(`背景透明度设置为: ${(opacity * 100).toFixed(0)}%`)
    }
  }
}

// 清除背景
const clearBackground = () => {
  if (props.live2dViewer) {
    const manager = props.live2dViewer.getManager()
    if (manager && manager.isInitialized) {
      manager.clearBackground()
      hasBackground.value = false
      backgroundImage.value = null
      updateDebugInfo('背景已清除')
    }
  }
}

// 清理模型文件关联
const clearModelFileAssociations = () => {
  // 清理动作文件关联
  motions.value.forEach(motion => {
    if (motion.filePath && motion.filePath.startsWith('blob:')) {
      URL.revokeObjectURL(motion.filePath)
    }
    motion.filePath = null
    motion.fileName = null
    motion.file = null
  })
  
  // 清理表情文件关联
  expressions.value.forEach(expression => {
    if (expression.filePath && expression.filePath.startsWith('blob:')) {
      URL.revokeObjectURL(expression.filePath)
    }
    expression.filePath = null
    expression.fileName = null
    expression.file = null
  })
  
  // 清理可用动作文件列表
  availableMotionFiles.value = []
  availableExpressionFiles.value = []
  
  updateDebugInfo('已清理旧模型的文件关联')
  
  // 保存配置
  saveMotionConfig()
  saveExpressionConfig()
}

// 监听模型加载状态
watch(() => props.modelLoaded, (loaded) => {
  if (loaded) {
    updateDebugInfo('模型加载完成')
  }
})

// 保存模型配置
const saveModelConfig = () => {
  const config = {
    modelScale: modelScale.value,
    autoEyeBlink: autoEyeBlink.value,
    autoBreath: autoBreath.value,
    eyeTracking: eyeTracking.value
  }
  localStorage.setItem('live2d-model-config', JSON.stringify(config))
}

// 加载模型配置
const loadModelConfig = () => {
  const stored = localStorage.getItem('live2d-model-config')
  if (stored) {
    try {
      const config = JSON.parse(stored)
      if (config.modelScale !== undefined) {
        modelScale.value = config.modelScale
      }
      if (config.autoEyeBlink !== undefined) {
        autoEyeBlink.value = config.autoEyeBlink
      }
      if (config.autoBreath !== undefined) {
        autoBreath.value = config.autoBreath
      }
      if (config.eyeTracking !== undefined) {
        eyeTracking.value = config.eyeTracking
      }
    } catch (error) {
      console.error('加载模型配置失败:', error)
    }
  }
}

// 组件挂载时加载缓存和表情配置
onMounted(() => {
  loadCacheFromStorage()
  loadExpressionConfig()
  loadMotionConfig()
  loadSavedPresets()
  loadModelConfig() // 加载模型配置
  
  // 加载可用表情文件
  setTimeout(() => {
    loadAvailableExpressions()
    // 更新可用的点击区域
    updateAvailableClickAreas()
  }, 1000)
})

// 监听Live2D模型加载状态变化
watch(() => props.modelLoaded, (isLoaded) => {
  if (isLoaded) {
    // 模型加载完成后应用初始设置
    setTimeout(() => {
      updateAvailableClickAreas()
      // 应用初始的模型缩放值
      console.log('模型加载完成，应用初始缩放值:', modelScale.value)
      updateModelScale(modelScale.value)
    }, 500)
  }
}, { immediate: true })

// 监听模型路径变化
watch(() => selectedModel.value, (newPath) => {
  if (newPath) {
    // 清理旧模型的动作和表情文件关联
    clearModelFileAssociations()
    
    setTimeout(() => {
      loadAvailableExpressions()
    }, 1000)
  }
})

// 预设文件相关函数
const generateDefaultPresetName = () => {
  const modelName = selectedModel.value ? selectedModel.value.split('/').pop().replace('.model3.json', '') : 'Unknown'
  const now = new Date()
  const timestamp = now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).replace(/[\/:]/g, '-')
  return `${modelName}_${timestamp}`
}

const savePreset = async () => {
  const presetName = newPresetName.value.trim() || generateDefaultPresetName()
  
  updateDebugInfo(`开始保存预设: ${presetName}`)
  
  // 保存动作文件内容
  const motionsWithFiles = await Promise.all(motions.value.map(async (motion) => {
    const motionData = {
      id: motion.id,
      name: motion.name,
      group: motion.group,
      index: motion.index,
      fileName: motion.fileName,
      filePath: motion.filePath,
      clickAreas: motion.clickAreas || []
    }
    
    // 如果有关联的文件，保存文件内容
    if (motion.file && motion.file.length > 0) {
      try {
        const file = motion.file[0]
        const fileContent = await file.text()
        motionData.fileContent = fileContent
        motionData.fileType = file.type
        motionData.fileName = file.name // 确保保存用户输入的文件名
        updateDebugInfo(`动作 ${motion.name} 文件内容已保存 (${file.size} bytes)`)
      } catch (error) {
        updateDebugInfo(`保存动作 ${motion.name} 文件内容失败: ${error.message}`)
      }
    } else if (motion.fileName) {
      updateDebugInfo(`动作 ${motion.name} 仅有文件名但无文件对象`)
    }
    
    return motionData
  }))
  
  // 保存表情文件内容
  const expressionsWithFiles = await Promise.all(expressions.value.map(async (exp) => {
    const expData = {
      id: exp.id,
      name: exp.name,
      fileName: exp.fileName,
      filePath: exp.filePath,
      clickAreas: exp.clickAreas || []
    }
    
    // 如果有关联的文件，保存文件内容
    if (exp.file && exp.file.length > 0) {
      try {
        const file = exp.file[0]
        const fileContent = await file.text()
        expData.fileContent = fileContent
        expData.fileType = file.type
        expData.fileName = file.name // 确保保存用户输入的文件名
        updateDebugInfo(`表情 ${exp.name} 文件内容已保存 (${file.size} bytes)`)
      } catch (error) {
        updateDebugInfo(`保存表情 ${exp.name} 文件内容失败: ${error.message}`)
      }
    } else if (exp.fileName) {
      updateDebugInfo(`表情 ${exp.name} 仅有文件名但无文件对象`)
    }
    
    return expData
  }))
  
  const presetData = {
    name: presetName,
    modelName: selectedModel.value || '未知模型',
    timestamp: new Date().toISOString(),
    createdAt: new Date().toLocaleString('zh-CN'),
    config: {
      selectedModel: selectedModel.value,
      autoEyeBlink: autoEyeBlink.value,
      autoBreath: autoBreath.value,
      eyeTracking: eyeTracking.value,
      modelScale: modelScale.value,
      backgroundImage: backgroundImage.value,
      backgroundOpacity: backgroundOpacity.value,
      hasBackground: hasBackground.value,
      motions: motionsWithFiles,
      expressions: expressionsWithFiles
    }
  }
  
  const existingPresets = JSON.parse(localStorage.getItem(PRESET_CONFIG_KEY) || '[]')
  const existingIndex = existingPresets.findIndex(preset => preset.name === presetName)
  
  if (existingIndex >= 0) {
    existingPresets[existingIndex] = presetData
    updateDebugInfo(`更新现有预设: ${presetName}`)
  } else {
    existingPresets.push(presetData)
    updateDebugInfo(`创建新预设: ${presetName}`)
  }
  
  localStorage.setItem(PRESET_CONFIG_KEY, JSON.stringify(existingPresets))
  loadSavedPresets()
  newPresetName.value = ''
  showPresetConfig.value = false
  
  updateDebugInfo(`预设 ${presetName} 保存完成`)
  console.log('预设已保存:', presetName)
}

const loadSavedPresets = () => {
  const presets = JSON.parse(localStorage.getItem(PRESET_CONFIG_KEY) || '[]')
  savedPresets.value = presets.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
}

const loadPreset = async (preset) => {
  const config = preset.config
  
  updateDebugInfo(`开始加载预设: ${preset.name}`)
  console.log('=== 开始加载预设 ===', preset.name, config)
  console.log('预设配置详情:', JSON.stringify(config, null, 2))
  
  // 直接应用配置
  updateModelScale(config.modelScale)
  toggleAutoEyeBlink(config.autoEyeBlink)
  toggleAutoBreath(config.autoBreath)
  toggleEyeTracking(config.eyeTracking)
  
  // 应用配置到界面
  selectedModel.value = config.selectedModel
  autoEyeBlink.value = config.autoEyeBlink
  autoBreath.value = config.autoBreath
  eyeTracking.value = config.eyeTracking
  modelScale.value = config.modelScale
  backgroundImage.value = config.backgroundImage
  backgroundOpacity.value = config.backgroundOpacity
  hasBackground.value = config.hasBackground
  
  // 获取当前模型目录
  const currentModelPath = selectedModel.value
  const modelDir = currentModelPath ? currentModelPath.substring(0, currentModelPath.lastIndexOf('/')) : ''
  
  // 恢复动作文件关联
  if (config.motions) {
    updateDebugInfo(`开始恢复 ${config.motions.length} 个动作文件关联`)
    
    for (const savedMotion of config.motions) {
      console.log('处理保存的动作:', savedMotion)
      const motion = motions.value.find(m => m.id === savedMotion.id)
      if (motion) {
        console.log('找到对应的动作对象:', motion.name, motion.id)
        
        // 恢复点击区域关联
        motion.clickAreas = savedMotion.clickAreas || []
        
        // 如果有保存的文件内容，重新创建文件对象并模拟用户输入
        if (savedMotion.fileContent) {
          try {
            // 创建新的文件对象
            const blob = new Blob([savedMotion.fileContent], { type: savedMotion.fileType || 'application/json' })
            const file = new File([blob], savedMotion.fileName, { type: savedMotion.fileType || 'application/json' })
            
            // 模拟用户手动输入文件，调用updateMotionFile函数
            await updateMotionFile(savedMotion.id, [file])
            
            updateDebugInfo(`动作 ${motion.name} 文件已恢复: ${savedMotion.fileName} (${blob.size} bytes)`)            
            console.log(`动作文件恢复成功:`, motion.name, motion.fileName, motion.filePath)
          } catch (error) {
            updateDebugInfo(`恢复动作 ${motion.name} 文件失败: ${error.message}`)
          }
        } else {
          // 如果有文件名但没有文件内容，根据文件名生成路径
          if (savedMotion.fileName) {
            motion.fileName = savedMotion.fileName
            // 根据文件名生成标准路径
            motion.filePath = `${modelDir}/motions/${savedMotion.fileName}`
            motion.file = null // 明确设置为null，表示没有实际文件对象
            updateDebugInfo(`动作 ${motion.name} 根据文件名恢复路径: ${savedMotion.fileName}`)
            console.log(`动作 ${motion.name} 根据文件名生成路径:`, motion.fileName, motion.filePath)
          } else {
            // 完全没有文件信息
            motion.filePath = null
            motion.fileName = null
            motion.file = null
            updateDebugInfo(`动作 ${motion.name} 无文件关联信息`)
            console.log(`动作 ${motion.name} 无文件关联:`, motion.fileName, motion.filePath)
          }
        }
      } else {
        updateDebugInfo(`未找到ID为 ${savedMotion.id} 的动作`)
      }
    }
  }
  
  // 恢复表情文件关联
  if (config.expressions) {
    updateDebugInfo(`开始恢复 ${config.expressions.length} 个表情文件关联`)
    
    for (const savedExp of config.expressions) {
      const expression = expressions.value.find(exp => exp.id === savedExp.id)
      if (expression) {
        // 恢复点击区域关联
        expression.clickAreas = savedExp.clickAreas || []
        
        // 如果有保存的文件内容，重新创建文件对象并模拟用户输入
        if (savedExp.fileContent) {
          try {
            // 创建新的文件对象
            const blob = new Blob([savedExp.fileContent], { type: savedExp.fileType || 'application/json' })
            const file = new File([blob], savedExp.fileName, { type: savedExp.fileType || 'application/json' })
            
            // 模拟用户手动输入文件，调用updateExpressionFile函数
            await updateExpressionFile(savedExp.id, [file])
            
            updateDebugInfo(`表情 ${expression.name} 文件已恢复: ${savedExp.fileName} (${blob.size} bytes)`)
            console.log(`表情文件恢复成功:`, expression.name, expression.fileName, expression.filePath)
          } catch (error) {
            updateDebugInfo(`恢复表情 ${expression.name} 文件失败: ${error.message}`)
          }
        } else {
          // 如果有文件名但没有文件内容，根据文件名生成路径
          if (savedExp.fileName) {
            expression.fileName = savedExp.fileName
            // 根据文件名生成标准路径
            expression.filePath = `${modelDir}/expressions/${savedExp.fileName}`
            expression.file = null // 明确设置为null，表示没有实际文件对象
            updateDebugInfo(`表情 ${expression.name} 根据文件名恢复路径: ${savedExp.fileName}`)
            console.log(`表情 ${expression.name} 根据文件名生成路径:`, expression.fileName, expression.filePath)
          } else {
            // 完全没有文件信息
            expression.filePath = null
            expression.fileName = null
            expression.file = null
            updateDebugInfo(`表情 ${expression.name} 无文件关联信息`)
            console.log(`表情 ${expression.name} 无文件关联:`, expression.fileName, expression.filePath)
          }
        }
      } else {
        updateDebugInfo(`未找到ID为 ${savedExp.id} 的表情`)
      }
    }
  }
  
  // 保存到localStorage
  saveMotionConfig()
  saveExpressionConfig()
  
  // 触发更新事件
  emit('model-change', selectedModel.value)
  emit('auto-eye-blink-change', autoEyeBlink.value)
  emit('auto-breath-change', autoBreath.value)
  emit('eye-tracking-change', eyeTracking.value)
  emit('model-scale-change', modelScale.value)
  emit('background-change', { image: backgroundImage.value, opacity: backgroundOpacity.value, hasBackground: hasBackground.value })
  emit('motions-update', motions.value)
  emit('expressions-update', expressions.value)
  
  updateDebugInfo(`预设 ${preset.name} 加载完成`)
  console.log('预设已加载:', preset.name)
}

const deletePreset = (presetName) => {
  if (confirm(`确定要删除预设 "${presetName}" 吗？`)) {
    const presets = JSON.parse(localStorage.getItem(PRESET_CONFIG_KEY) || '[]')
    const filteredPresets = presets.filter(preset => preset.name !== presetName)
    localStorage.setItem(PRESET_CONFIG_KEY, JSON.stringify(filteredPresets))
    loadSavedPresets()
    console.log('预设已删除:', presetName)
  }
}

const exportPreset = (preset) => {
  const dataStr = JSON.stringify(preset, null, 2)
  const dataBlob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(dataBlob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${preset.name}.json`
  link.click()
  URL.revokeObjectURL(url)
}

const importPreset = () => {
  presetFileInput.value.click()
}

const handlePresetFileImport = (event) => {
  const file = event.target.files[0]
  if (!file) return
  
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const presetData = JSON.parse(e.target.result)
      
      // 验证预设数据格式
      if (!presetData.name || !presetData.config) {
        alert('无效的预设文件格式')
        return
      }
      
      // 检查是否已存在同名预设
      const existingPresets = JSON.parse(localStorage.getItem(PRESET_CONFIG_KEY) || '[]')
      const existingIndex = existingPresets.findIndex(preset => preset.name === presetData.name)
      
      if (existingIndex >= 0) {
        if (!confirm(`预设 "${presetData.name}" 已存在，是否覆盖？`)) {
          return
        }
        existingPresets[existingIndex] = presetData
      } else {
        existingPresets.push(presetData)
      }
      
      localStorage.setItem(PRESET_CONFIG_KEY, JSON.stringify(existingPresets))
      loadSavedPresets()
      
      console.log('预设已导入:', presetData.name)
    } catch (error) {
      alert('预设文件格式错误')
      console.error('导入预设失败:', error)
    }
  }
  reader.readAsText(file)
  
  // 清空文件输入
  event.target.value = ''
}

// --- 测试功能方法 ---

/**
 * 测试口型同步动画
 */
const testLipSync = () => {
  if (!props.live2dViewer || !props.modelLoaded) {
    console.warn('Live2D模型未加载或viewer不可用')
    return
  }
  
  // 调用Live2DViewer的测试方法
  if (props.live2dViewer.testLipSyncAnimation) {
    props.live2dViewer.testLipSyncAnimation()
    
    // 更新测试状态
    isTestingLipSync.value = true
    
    // 5秒后重置状态
    setTimeout(() => {
      isTestingLipSync.value = false
    }, 5000)
    
    updateDebugInfo('🎭 开始测试口型同步动画 (5秒)')
  } else {
    console.error('Live2DViewer测试方法不可用')
    updateDebugInfo('❌ 测试方法不可用，请检查Live2DViewer组件')
  }
}

/**
 * 测试随机动作
 */
const testRandomMotion = () => {
  if (!props.live2dViewer || !props.modelLoaded) {
    console.warn('Live2D模型未加载或viewer不可用')
    return
  }
  
  // 调用Live2DViewer的测试方法
  if (props.live2dViewer.testRandomMotion) {
    props.live2dViewer.testRandomMotion()
    updateDebugInfo('🎪 播放随机动作')
  } else {
    console.error('Live2DViewer测试方法不可用')
    updateDebugInfo('❌ 测试方法不可用，请检查Live2DViewer组件')
  }
}


</script>

<style scoped>
.live2d-controls {
  max-height: 600px;
  overflow-y: auto;
}

.v-subheader {
  height: auto;
  min-height: 32px;
}

.text-caption {
  font-size: 0.75rem !important;
}

/* 缓存背景图片网格布局 */
.cached-backgrounds-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
  margin-top: 8px;
}

/* 缓存背景图片项 */
.cached-background-item {
  position: relative;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
  background: #f5f5f5;
  transition: all 0.2s ease;
}

.cached-background-item:hover {
  border-color: #1976d2;
  box-shadow: 0 2px 8px rgba(25, 118, 210, 0.2);
}

/* 图片预览区域 */
.image-preview {
  position: relative;
  width: 100%;
  height: 80px;
  cursor: pointer;
  overflow: hidden;
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.2s ease;
}

.image-preview:hover .preview-image {
  transform: scale(1.05);
}

/* 图片覆盖层 */
.image-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.image-preview:hover .image-overlay {
  opacity: 1;
}

/* 图片信息 */
.image-info {
  padding: 8px;
  background: white;
}

.image-name {
  font-size: 12px;
  font-weight: 500;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}

.image-size {
  font-size: 10px;
  color: #666;
}

/* 删除按钮 */
.delete-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  background: rgba(255, 255, 255, 0.9) !important;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.cached-background-item:hover .delete-btn {
  opacity: 1;
}

/* 表情按钮样式 */
.expression-btn.has-file {
  border-color: #4caf50 !important;
  background-color: rgba(76, 175, 80, 0.05) !important;
}

.expression-btn.has-file:hover {
  background-color: rgba(76, 175, 80, 0.1) !important;
}
</style>