<template>
  <v-app :style="{ backgroundColor: $vuetify.theme.current.colors.background }"> <!-- Ensure app background uses theme -->
    <!-- Global App Bar Removed -->
    <!-- <v-app-bar app color="#FEF7FF" elevation="1"> ... </v-app-bar> -->

    <v-navigation-drawer v-model="drawer" temporary app>
      <!-- Navigation Drawer Content Here -->
      <v-list>
        <v-list-item title="导航项 1"></v-list-item>
        <v-list-item title="导航项 2"></v-list-item>
      </v-list>
    </v-navigation-drawer>

    <v-main>
      <!-- Container now mainly provides padding -->
      <v-container fluid class="pa-4 fill-height">
        <!-- Row without no-gutters to allow natural spacing -->
        <v-row class="fill-height">
          <!-- Left Column - adjusted padding -->
          <v-col cols="12" md="4" class="d-flex flex-column pa-0 pr-md-2">
            <!-- Toolbar directly in column, matches app background -->
            <v-toolbar density="compact" color="background" elevation="0">
              <v-app-bar-nav-icon @click="drawer = !drawer" icon="mdi-menu"></v-app-bar-nav-icon>
              <v-toolbar-title>桃汐</v-toolbar-title>
              <v-spacer></v-spacer>
              <v-btn 
                icon="mdi-robot-happy"
                @click="showConfigPanel = !showConfigPanel"
                :color="modelLoaded ? 'success' : 'grey'"
                variant="text"
              ></v-btn>
              <v-btn icon="mdi-account-circle"></v-btn>
            </v-toolbar>
            <!-- 聊天界面或配置面板 -->
            <v-sheet class="chat-area-sheet flex-grow-1 d-flex flex-column" color="surface" elevation="1">
              <!-- 聊天界面 -->
              <ChatInterface v-if="!showConfigPanel" class="flex-grow-1" />
              
              <!-- 配置面板 -->
              <div v-else class="config-panel-container flex-grow-1 d-flex flex-column">
                <!-- 配置面板标题栏 -->
                <v-toolbar density="compact" color="surface" elevation="0" class="config-header">
                  <v-btn 
                    icon="mdi-arrow-left" 
                    variant="text"
                    @click="showConfigPanel = false"
                    class="mr-2"
                  ></v-btn>
                  <v-icon class="mr-2">mdi-robot-happy</v-icon>
                  <v-toolbar-title>Live2D 控制面板</v-toolbar-title>
                </v-toolbar>
                
                <!-- 配置面板内容 -->
                <div class="config-content flex-grow-1">
                  <Live2DControls 
                    :live2d-viewer="live2dViewer"
                    :model-loaded="modelLoaded"
                    @model-change="handleModelChange"
                    @motions-update="handleMotionsUpdate"
                    @expressions-update="handleExpressionsUpdate"
                    @auto-eye-blink-change="handleAutoEyeBlinkChange"
                    @auto-breath-change="handleAutoBreathChange"
                    @eye-tracking-change="handleEyeTrackingChange"
                    @model-scale-change="handleModelScaleChange"
                    @background-change="handleBackgroundChange"
                    class="h-100"
                  />
                </div>
              </div>
            </v-sheet>
          </v-col>
          <!-- Right Column - adjusted padding -->
          <v-col cols="12" md="8" class="d-flex flex-column pa-0 pl-md-2">
            <!-- Live2D panel sheet with its own rounding -->
              <v-sheet class="rounded-panel d-flex flex-grow-1" color="panelBackground" elevation="1">
                 <Live2DViewer 
                   ref="live2dViewer"
                   :model-path="currentModelPath"
                   :motions="motions"
                   :expressions="expressions"
                   :width="400" 
                   :height="600" 
                   @model-loaded="handleModelLoaded"
                   @model-error="handleModelError"
                   class="flex-grow-1"
                 />
              </v-sheet>
          </v-col>
        </v-row>
      </v-container>
    </v-main>
    

  </v-app>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue';
import ChatInterface from './components/ChatInterface.vue';
import Live2DViewer from './components/Live2DViewer.vue';
import Live2DControls from './components/Live2DControls.vue';
import { useApi } from './composables/useApi';

const drawer = ref(false);
const live2dViewer = ref(null);
const modelLoaded = ref(false);
const currentModelPath = ref('/src/live2d/models/Haru/Haru.model3.json');
const showConfigPanel = ref(false); // 控制是否显示配置面板
const motions = ref([]); // 存储动作配置数据
const expressions = ref([]); // 存储表情配置数据

// API composable for audio playback
const { receivedText, receivedAudioUrl } = useApi();

// Watch for the received audio URL and trigger playback
watch(receivedAudioUrl, (newUrl) => {
  if (newUrl && live2dViewer.value) {
    console.log(`App.vue: Detected new audio URL, triggering playback: ${newUrl}`);
    // We pass the URL directly. The `text` parameter can be null.
    live2dViewer.value.playAudioWithLipSync(null, newUrl);
  }
});

// Handle model loaded event
const handleModelLoaded = (model) => {
  modelLoaded.value = true;
  console.log('Model loaded in App:', model);
  // Initialize AudioContext after the model is loaded and user has likely interacted
  if (live2dViewer.value && live2dViewer.value.initAudioContext) {
    live2dViewer.value.initAudioContext();
  }
};

// Handle model error event
const handleModelError = (error) => {
  modelLoaded.value = false;
  console.error('Model error in App:', error);
};

// Handle model change from controls
const handleModelChange = (newModelPath) => {
  currentModelPath.value = newModelPath;
  modelLoaded.value = false;
  // The Live2DViewer will automatically reload when modelPath changes
};

// Handle motions update from controls
const handleMotionsUpdate = (updatedMotions) => {
  motions.value = updatedMotions;
  console.log('Motions updated in App:', updatedMotions);
};

// Handle expressions update from controls
const handleExpressionsUpdate = (updatedExpressions) => {
  expressions.value = updatedExpressions;
  console.log('Expressions updated in App:', updatedExpressions);
};

// Handle auto eye blink change from controls
const handleAutoEyeBlinkChange = (enabled) => {
  if (live2dViewer.value) {
    const manager = live2dViewer.value.getManager();
    if (manager) {
      manager.setAutoEyeBlinkEnable(enabled);
      console.log('Auto eye blink changed in App:', enabled);
    }
  }
};

// Handle auto breath change from controls
const handleAutoBreathChange = (enabled) => {
  if (live2dViewer.value) {
    const manager = live2dViewer.value.getManager();
    if (manager) {
      manager.setAutoBreathEnable(enabled);
      console.log('Auto breath changed in App:', enabled);
    }
  }
};

// Handle eye tracking change from controls
const handleEyeTrackingChange = (enabled) => {
  if (live2dViewer.value) {
    const manager = live2dViewer.value.getManager();
    if (manager) {
      manager.setEyeTrackingEnable(enabled);
      console.log('Eye tracking changed in App:', enabled);
    }
  }
};

// Handle model scale change from controls
const handleModelScaleChange = (scale) => {
  if (live2dViewer.value) {
    const manager = live2dViewer.value.getManager();
    if (manager) {
      manager.setModelScale(scale);
      console.log('Model scale changed in App:', scale);
    }
  }
};

// Handle background change from controls
const handleBackgroundChange = (backgroundConfig) => {
  if (live2dViewer.value) {
    const manager = live2dViewer.value.getManager();
    if (manager) {
      manager.setBackground(backgroundConfig.image, backgroundConfig.opacity, backgroundConfig.hasBackground);
      console.log('Background changed in App:', backgroundConfig);
    }
  }
};
</script>

<style scoped>
/* Rounding for the right panel sheet */
.rounded-panel {
  border-radius: 28px;
  overflow: hidden;
}

/* Rounding specifically for the white chat area sheet */
.chat-area-sheet {
  border-radius: 28px;
  overflow: hidden;
}

/* Ensure row and container fill height */
.fill-height {
   height: 100%;
}

/* Ensure v-main takes up viewport height */
.v-main {
   min-height: 100vh;
}

/* Ensure ChatInterface fills the sheet space */
.v-sheet > .flex-grow-1 {
  min-height: 0; /* Allow shrinking if needed */
}

/* 配置面板样式 */
.config-panel-container {
  height: 100%;
}

.config-header {
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
  flex-shrink: 0;
}

.config-content {
  overflow-y: auto;
  padding: 16px;
}

/* 确保配置面板内容正确填充 */
.config-content .live2d-controls {
  height: 100%;
}

</style>
