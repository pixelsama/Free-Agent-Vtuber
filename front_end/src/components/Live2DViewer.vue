<template>
  <div class="live2d-container" ref="live2dContainer">
    <canvas 
      ref="live2dCanvas" 
      class="live2d-canvas"
      @mousemove="handlePointerMove"
      @click="handleCanvasClick"
      @touchmove="handlePointerMove"
    ></canvas>
    <div v-if="loading" class="loading-overlay">
      <v-progress-circular indeterminate color="primary" size="50"></v-progress-circular>
      <p class="mt-2">加载Live2D模型中...</p>
    </div>
    <div v-if="error" class="error-overlay">
      <v-icon color="error" size="48">mdi-alert-circle</v-icon>
      <p class="mt-2 text-error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch, shallowRef } from 'vue'
import Live2DManager from '../live2d/utils/Live2DManager.js'
import { useApi } from '@/composables/useApi.js' // 引入 useApi

// Props
const props = defineProps({
  modelPath: {
    type: String,
    default: '/live2d/models/Haru/Haru.model3.json'
  },
  width: {
    type: Number,
    default: 400
  },
  height: {
    type: Number,
    default: 600
  },
  motions: {
    type: Array,
    default: () => []
  },
  expressions: {
    type: Array,
    default: () => []
  }
})

// Emits
const emit = defineEmits(['model-loaded', 'model-error'])

// Reactive data
const live2dContainer = ref(null)
const live2dCanvas = ref(null)
const loading = ref(true)
const error = ref('')

// --- Web Audio API State ---
const audioContext = shallowRef(null)
const analyserNode = shallowRef(null)
const audioSource = shallowRef(null)
const audioBuffer = shallowRef(null)
const isPlayingAudio = ref(false)
const audioContextReady = ref(false) // 标记AudioContext是否已准备好
const userInteracted = ref(false) // 标记用户是否已交互
const isTestingLipSync = ref(false) // 标记是否正在测试口型同步
let animationFrameId = null

// --- 测试功能 (需要在模板使用前定义) ---

/**
 * 测试口型同步动画 - 模拟音频驱动的口型变化
 */
const testLipSyncAnimation = () => {
  if (!live2dManager || !live2dManager.isModelLoaded) {
    console.warn('Live2D模型未加载完成');
    return;
  }
  
  if (isTestingLipSync.value) {
    console.warn('口型同步测试已在进行中');
    return;
  }
  
  // 标记用户已交互
  if (!userInteracted.value) {
    userInteracted.value = true;
    console.log('User interaction detected during lip sync test.');
  }
  
  isTestingLipSync.value = true;
  console.log('🎭 开始测试口型同步动画...');
  
  const startTime = Date.now();
  const duration = 5000; // 5秒测试时长
  
  const animateLipSync = () => {
    const elapsed = Date.now() - startTime;
    const progress = elapsed / duration;
    
    if (progress >= 1.0) {
      // 测试结束，重置口型
      if (live2dManager) {
        live2dManager.setLipSyncValue(0.0);
      }
      isTestingLipSync.value = false;
      console.log('✅ 口型同步测试完成');
      return;
    }
    
    // 生成模拟的音频波形 - 多种波形的组合
    const time = elapsed / 1000;
    const wave1 = Math.sin(time * 2) * 0.3; // 低频波
    const wave2 = Math.sin(time * 8) * 0.4; // 中频波  
    const wave3 = Math.sin(time * 15) * 0.2; // 高频波
    const noise = (Math.random() - 0.5) * 0.1; // 随机噪声
    
    // 组合波形并归一化到0-1范围
    let lipValue = (wave1 + wave2 + wave3 + noise + 1) / 2;
    lipValue = Math.max(0, Math.min(1, lipValue));
    
    // 添加一些"说话"的节奏感
    const speechPattern = Math.sin(time * 3) * 0.5 + 0.5;
    lipValue *= speechPattern;
    
    // 设置口型值
    if (live2dManager) {
      live2dManager.setLipSyncValue(lipValue);
    }
    
    // 继续动画
    requestAnimationFrame(animateLipSync);
  };
  
  // 开始动画
  animateLipSync();
};

/**
 * 测试随机动作
 */
const testRandomMotion = () => {
  if (!live2dManager || !live2dManager.isModelLoaded) {
    console.warn('Live2D模型未加载完成');
    return;
  }
  
  // 标记用户已交互
  if (!userInteracted.value) {
    userInteracted.value = true;
    console.log('User interaction detected during motion test.');
  }
  
  // 播放随机动作
  live2dManager.playRandomMotion('Idle', 3);
  console.log('🎪 播放随机动作');
};

// --- Composables ---
const { processingError } = useApi()

// Live2D Manager instance
let live2dManager = null

// Initialize Live2D
const initLive2D = async () => {
  try {
    loading.value = true
    error.value = ''
    
    // Wait for next tick to ensure DOM is ready
    await nextTick()
    
    if (!live2dCanvas.value) {
      throw new Error('Canvas element not found')
    }
    
    // Set canvas size with high DPI support - 使用容器的实际尺寸
    const devicePixelRatio = window.devicePixelRatio || 1
    const containerRect = live2dContainer.value.getBoundingClientRect()
    const displayWidth = containerRect.width || props.width
    const displayHeight = containerRect.height || props.height
    
    // Set actual canvas size (high resolution)
    live2dCanvas.value.width = displayWidth * devicePixelRatio
    live2dCanvas.value.height = displayHeight * devicePixelRatio
    
    // Set display size (CSS pixels) - 让canvas占满整个容器
    live2dCanvas.value.style.width = '100%'
    live2dCanvas.value.style.height = '100%'
    
    // Create Live2D Manager
    live2dManager = new Live2DManager()
    
    // Initialize framework
    await live2dManager.initialize(live2dCanvas.value)
    
    // Load model
    const model = await live2dManager.loadModel(props.modelPath)
    
    // Start rendering
    live2dManager.startRendering()
    
    loading.value = false
    
    // 获取模型的HitAreas信息
    updateModelHitAreas()
    
    emit('model-loaded', model)
    console.log('Live2D model loaded successfully')
    
  } catch (err) {
    console.error('Failed to initialize Live2D:', err)
    error.value = `初始化失败: ${err.message}`
    loading.value = false
    emit('model-error', err)
  }
}

// Handle mouse/touch events
const handlePointerMove = (event) => {
  if (!live2dManager || !live2dCanvas.value) return
  
  // 标记用户已交互
  if (!userInteracted.value) {
    userInteracted.value = true
    console.log('User interaction detected, audio features enabled.')
  }
  
  const rect = live2dCanvas.value.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  
  live2dManager.onPointerMove(x, y)
}

// Handle canvas click for interactions
const handleCanvasClick = (event) => {
  if (!live2dManager) return
  
  // 标记用户已交互并尝试初始化AudioContext
  if (!userInteracted.value) {
    userInteracted.value = true
    console.log('User interaction detected, attempting to initialize AudioContext.')
    initAudioContext()
  }
  
  console.log('=== 点击事件调试信息 ===')
  console.log('props.motions:', props.motions)
  console.log('motions数量:', props.motions.length)
  
  const rect = live2dCanvas.value.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  
  // 将点击坐标转换为相对于canvas的比例坐标
  const relativeX = x / rect.width
  const relativeY = y / rect.height
  
  // 检查是否点击了关联的区域
  const clickedResult = findMotionByClickArea(relativeX, relativeY)
  
  if (clickedResult) {
    if (clickedResult.type === 'expression') {
      // 表情已在findMotionByClickArea中执行
      console.log(`点击触发表情: ${clickedResult.item.name}`)
    } else if (clickedResult.type === 'motion') {
      // 动作已在findMotionByClickArea中执行
      console.log(`点击触发动作: ${clickedResult.item.name}`)
    }
  } else {
    // 默认行为：播放随机动作
    console.log('未匹配到关联动作或表情，播放随机动作')
    randomMotion()
  }
  console.log('=== 点击事件调试结束 ===')
}

// 根据点击坐标查找关联的动作
const findMotionByClickArea = (x, y) => {
  if (!live2dManager || !live2dManager.isModelLoaded) {
    return null
  }
  
  // 获取canvas的显示尺寸
  const canvas = live2dCanvas.value
  if (!canvas) return null
  
  const canvasWidth = canvas.clientWidth
  const canvasHeight = canvas.clientHeight
  
  // 转换屏幕坐标
  const screenX = x * canvasWidth
  const screenY = y * canvasHeight
  
  // 使用Live2D的hitTest方法检测命中的区域
  const hitAreaName = live2dManager.hitTestAtScreenCoordinate(screenX, screenY)
  
  if (!hitAreaName) {
    console.log(`点击坐标: (${x.toFixed(3)}, ${y.toFixed(3)}), 未命中任何HitArea`)
    return null
  }
  
  console.log(`点击坐标: (${x.toFixed(3)}, ${y.toFixed(3)}), 命中HitArea: ${hitAreaName}`)
  
  // 查找与命中区域关联的动作和表情
  const matchedMotions = []
  const matchedExpressions = []
  
  for (const motion of props.motions) {
    if (motion.clickAreas && motion.clickAreas.includes(hitAreaName)) {
      matchedMotions.push(motion)
    }
  }
  
  for (const expression of props.expressions) {
    if (expression.clickAreas && expression.clickAreas.includes(hitAreaName)) {
      matchedExpressions.push(expression)
    }
  }
  
  console.log(`匹配到 ${matchedMotions.length} 个动作:`, matchedMotions.map(m => m.name))
  console.log(`匹配到 ${matchedExpressions.length} 个表情:`, matchedExpressions.map(e => e.name))
  
  // 优先处理表情，如果有匹配的表情且能成功执行就返回
  if (matchedExpressions.length > 0) {
    const randomIndex = Math.floor(Math.random() * matchedExpressions.length)
    const selectedExpression = matchedExpressions[randomIndex]
    console.log(`随机选择表情: ${selectedExpression.name} (索引: ${randomIndex}/${matchedExpressions.length - 1})`)
    
    // 执行表情 - 支持fileName和filePath两种方式
    if (live2dManager) {
      if (selectedExpression.filePath) {
        // 如果有filePath，使用文件路径执行表情
        live2dManager.setExpressionFromFile(selectedExpression.filePath)
        console.log(`通过文件路径执行表情: ${selectedExpression.filePath}`)
        return { type: 'expression', item: selectedExpression }
      } else if (selectedExpression.fileName) {
        // 如果只有fileName，使用文件名执行表情
        live2dManager.startExpression(selectedExpression.fileName)
        console.log(`通过文件名执行表情: ${selectedExpression.fileName}`)
        return { type: 'expression', item: selectedExpression }
      } else {
        console.log(`表情 ${selectedExpression.name} 没有关联文件，无法执行`)
        // 表情执行失败，继续尝试动作
      }
    }
  }
  
  // 如果没有匹配的表情，再处理动作
  if (matchedMotions.length > 0) {
    const randomIndex = Math.floor(Math.random() * matchedMotions.length)
    const selectedMotion = matchedMotions[randomIndex]
    console.log(`随机选择动作: ${selectedMotion.name} (索引: ${randomIndex}/${matchedMotions.length - 1})`)
    
    // 执行动作 - 使用与动作选项相同的逻辑
    if (live2dManager) {
      if (selectedMotion.filePath) {
        // 如果有关联的文件，使用自定义动作文件
        live2dManager.setMotionFromFile(selectedMotion.filePath)
        console.log(`通过文件路径执行动作: ${selectedMotion.name} (使用文件: ${selectedMotion.fileName})`)
      } else {
        // 使用默认动作
        live2dManager.startMotion(selectedMotion.group, selectedMotion.index, 2)
        console.log(`通过组和索引执行动作: ${selectedMotion.group}[${selectedMotion.index}] (默认)`)
      }
    }
    
    return { type: 'motion', item: selectedMotion }
  }
  
  // 如果没有找到关联的动作，触发area-clicked事件让父组件处理
  emit('area-clicked', hitAreaName)
  
  return null
}

// 模型的真实HitAreas信息
const modelHitAreas = ref([])

// 检查点击是否命中模型的HitArea
const isPointInClickArea = (x, y, areaId) => {
  if (!live2dManager || !live2dManager.isModelLoaded) {
    return false
  }
  
  // 获取canvas的显示尺寸
  const canvas = live2dCanvas.value
  if (!canvas) return false
  
  const canvasWidth = canvas.clientWidth
  const canvasHeight = canvas.clientHeight
  
  // 转换屏幕坐标到标准化坐标
  const screenX = x * canvasWidth
  const screenY = y * canvasHeight
  
  // 使用Live2D的hitTest方法检测
  const hitArea = live2dManager.hitTestAtScreenCoordinate(screenX, screenY)
  
  // 检查命中的区域是否匹配指定的areaId
  return hitArea === areaId
}

// 获取模型HitAreas信息
const updateModelHitAreas = () => {
  if (live2dManager && live2dManager.isModelLoaded) {
    modelHitAreas.value = live2dManager.getModelHitAreas()
    console.log('Model HitAreas:', modelHitAreas.value)
  }
}

const randomMotion = () => {
  if (!live2dManager || !live2dManager.isModelLoaded) {
    console.warn('Model not loaded yet')
    return
  }
  
  // 尝试播放 Idle 组的随机动作
  live2dManager.startMotion('Idle', 0, 2)
}

// Cleanup
const cleanup = () => {
  if (live2dManager) {
    live2dManager.dispose()
    live2dManager = null
  }
  // Stop audio and disconnect nodes
  if (audioSource.value) {
    audioSource.value.disconnect()
  }
  if (analyserNode.value) {
    analyserNode.value.disconnect()
  }
  if (audioContext.value && audioContext.value.state !== 'closed') {
    audioContext.value.close()
  }
  cancelAnimationFrame(animationFrameId)
}

// Watch for model path changes
watch(() => props.modelPath, (newPath) => {
  if (newPath && live2dManager) {
    initLive2D()
  }
})

// Handle window resize
const handleResize = () => {
  if (live2dManager && live2dContainer.value && live2dCanvas.value) {
    const containerRect = live2dContainer.value.getBoundingClientRect()
    const devicePixelRatio = window.devicePixelRatio || 1
    const displayWidth = containerRect.width
    const displayHeight = containerRect.height
    
    // Update canvas size
    live2dCanvas.value.width = displayWidth * devicePixelRatio
    live2dCanvas.value.height = displayHeight * devicePixelRatio
    
    // Update WebGL viewport
    if (live2dManager.gl) {
      live2dManager.gl.viewport(0, 0, live2dCanvas.value.width, live2dCanvas.value.height)
      live2dManager.updateViewMatrix()
    }
  }
}

// Lifecycle hooks
onMounted(() => {
  initLive2D()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  cleanup()
  window.removeEventListener('resize', handleResize)
})

// --- Audio & Lip Sync Functions ---

/**
 * 初始化Web Audio API AudioContext
 * 必须在用户交互后调用以符合浏览器自动播放策略
 */
const initAudioContext = async () => {
  if (audioContext.value && audioContext.value.state !== 'closed') {
    // AudioContext已存在且未关闭
    if (audioContext.value.state === 'suspended') {
      try {
        await audioContext.value.resume();
        console.log('AudioContext resumed successfully.');
      } catch (e) {
        console.error('Failed to resume AudioContext:', e);
        return false;
      }
    }
    audioContextReady.value = true;
    return true;
  }

  try {
    audioContext.value = new (window.AudioContext || window.webkitAudioContext)();
    analyserNode.value = audioContext.value.createAnalyser();
    analyserNode.value.fftSize = 256;
    
    // 检查AudioContext状态
    if (audioContext.value.state === 'suspended') {
      // 如果被挂起，尝试恢复（需要用户交互）
      try {
        await audioContext.value.resume();
        console.log('AudioContext initialized and resumed successfully.');
      } catch (e) {
        console.warn('AudioContext suspended, waiting for user interaction:', e);
        audioContextReady.value = false;
        return false;
      }
    }
    
    audioContextReady.value = true;
    console.log('AudioContext initialized successfully.');
    return true;
    
  } catch (e) {
    console.error('Failed to initialize AudioContext:', e);
    error.value = '无法初始化音频，语音功能将不可用。请检查浏览器音频权限。';
    audioContextReady.value = false;
    return false;
  }
};

/**
 * 确保AudioContext准备就绪
 * 如果需要用户交互，会等待下一次交互
 */
const ensureAudioContextReady = async () => {
  if (audioContextReady.value) {
    return true;
  }
  
  if (!userInteracted.value) {
    console.warn('Audio playback requires user interaction. Please click or tap first.');
    return false;
  }
  
  return await initAudioContext();
};

/**
 * 播放音频并启动口型同步
 * @param {string} text - 要转换为语音的文本
 * @param {string} audioUrl - 可选的音频URL，如果提供则直接播放
 */
const playAudioWithLipSync = async (text, audioUrl = null) => {
  // 确保AudioContext准备就绪
  const ready = await ensureAudioContextReady();
  if (!ready) {
    console.warn('AudioContext not ready. Audio playback requires user interaction.');
    processingError.value = '音频播放需要用户交互，请先点击Live2D模型或页面其他位置。';
    return;
  }
  
  if (isPlayingAudio.value) {
    console.log('Already playing audio, stopping previous playback.');
    stopAudioAndLipSync();
  }

  try {
    let audioData;
    
    // 1. 获取音频数据
    if (audioUrl) {
      // 使用提供的音频URL
      console.log('Playing audio from URL:', audioUrl);
      const response = await fetch(audioUrl);
      if (!response.ok) {
        throw new Error(`Failed to fetch audio: ${response.status}`);
      }
      audioData = await response.arrayBuffer();
    } else {
      // 仅保留双 WS 模式：不再通过 HTTP 拉取 TTS。
      // 若未提供 audioUrl（应来自 WS 重组），则提示用户或上层逻辑确保提供。
      throw new Error('未提供可播放的音频URL（当前仅支持通过 WebSocket 获取的音频）。');
    }

    // 2. 解码音频数据
    audioBuffer.value = await audioContext.value.decodeAudioData(audioData);

    // 3. 设置音频源节点
    audioSource.value = audioContext.value.createBufferSource();
    audioSource.value.buffer = audioBuffer.value;
    audioSource.value.connect(analyserNode.value);
    analyserNode.value.connect(audioContext.value.destination);

    // 4. 处理播放结束事件
    audioSource.value.onended = () => {
      isPlayingAudio.value = false;
      if (live2dManager) {
        live2dManager.setLipSyncValue(0.0); // 重置嘴巴到关闭状态
      }
      cancelAnimationFrame(animationFrameId);
      console.log('Audio playback finished.');
    };

    // 5. 开始播放和口型同步
    audioSource.value.start(0);
    isPlayingAudio.value = true;
    startLipSyncLoop();
    console.log('Started audio playback and lip sync.');

  } catch (err) {
    console.error('Error during audio playback:', err);
    processingError.value = `音频播放失败: ${err.message}`;
    isPlayingAudio.value = false;
  }
};

/**
 * 停止音频播放和口型同步
 */
const stopAudioAndLipSync = () => {
  if (audioSource.value && isPlayingAudio.value) {
    audioSource.value.stop();
    console.log("Audio playback stopped by user.");
  }
  
  // 显式取消动画帧
  cancelAnimationFrame(animationFrameId);
  isPlayingAudio.value = false;
  
  if (live2dManager) {
    live2dManager.setLipSyncValue(0.0);
  }
};

/**
 * Fetches audio for the given text, plays it, and syncs lip movement.
 * @param {string} text - The text to be spoken.
 * @deprecated 使用 playAudioWithLipSync 代替
 */
const speak = async (text) => {
  console.warn('speak() method is deprecated. Use playAudioWithLipSync() instead.');
  return playAudioWithLipSync(text);
};

/**
 * Stops the current audio playback and lip sync animation.
 * @deprecated 使用 stopAudioAndLipSync 代替
 */
const stopSpeaking = () => {
  console.warn('stopSpeaking() method is deprecated. Use stopAudioAndLipSync() instead.');
  return stopAudioAndLipSync();
};


// Expose methods for parent component
defineExpose({
  // Method to get the manager instance
  getManager: () => live2dManager,
  
  // Audio methods (new unified API)
  initAudioContext,
  playAudioWithLipSync,
  stopAudioAndLipSync,
  ensureAudioContextReady,
  
  // Audio methods (deprecated but kept for compatibility)
  speak,
  stopSpeaking,
  
  // Audio status getters
  getAudioContextReady: () => audioContextReady.value,
  getUserInteracted: () => userInteracted.value,
  getIsPlayingAudio: () => isPlayingAudio.value,
  
  // Test methods
  testLipSyncAnimation,
  testRandomMotion,

  // Existing exposed methods
  playMotion: (motionGroup, motionIndex = 0) => {
    if (live2dManager) {
      live2dManager.playMotion(motionGroup, motionIndex)
    }
  },
  setExpression: (expressionId) => {
    if (live2dManager) {
      live2dManager.setExpression(expressionId)
    }
  },
  setExpressionFromFile: async (fileUrl) => {
    if (live2dManager) {
      try {
        await live2dManager.setExpressionFromFile(fileUrl)
      } catch (error) {
        console.error('Failed to set expression from file:', error)
        throw error
      }
    }
  },
  setMotionFromFile: async (fileUrl) => {
    if (live2dManager) {
      try {
        await live2dManager.setMotionFromFile(fileUrl)
      } catch (error) {
        console.error('Failed to set motion from file:', error)
        throw error
      }
    }
  }
})

// --- Helper Functions ---

/**
 * 开始口型同步的动画循环
 */
const startLipSyncLoop = () => {
  if (!analyserNode.value || !live2dManager) return;

  const bufferLength = analyserNode.value.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);

  const updateLipSync = () => {
    analyserNode.value.getByteFrequencyData(dataArray);

    // 计算音量 - 一个简单的实现
    let sum = 0;
    for (let i = 0; i < bufferLength; i++) {
      sum += dataArray[i];
    }
    const average = sum / bufferLength;

    // 将音量映射到嘴部开合参数 (0.0 - 1.0)
    // 这个映射关系可能需要根据你的模型和音频进行微调
    const volume = Math.min(Math.max(average / 100, 0), 1.0);
    
    // 将值传递给Live2D模型
    live2dManager.setLipSyncValue(volume);

    // 如果还在播放，继续下一帧
    if (isPlayingAudio.value) {
      animationFrameId = requestAnimationFrame(updateLipSync);
    }
  };

  // 启动循环
  animationFrameId = requestAnimationFrame(updateLipSync);
};
</script>

<style scoped>
.live2d-container {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  /* 移除背景渐变，让Live2D的WebGL背景占满整个区域 */
  background: transparent;
  border-radius: 12px;
  overflow: hidden;
}

.live2d-canvas {
  display: block;
  /* 让canvas占满整个容器 */
  width: 100%;
  height: 100%;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  /* 确保canvas不会被CSS拉伸变形 */
  object-fit: cover;
  /* 启用硬件加速 */
  transform: translateZ(0);
  /* 优化渲染质量 */
  image-rendering: -webkit-optimize-contrast;
  image-rendering: crisp-edges;
}

.loading-overlay,
.error-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(4px);
  border-radius: 12px;
}

.loading-overlay p,
.error-overlay p {
  margin: 0;
  font-size: 14px;
  color: #666;
}

.error-overlay p {
  color: #d32f2f;
}
</style>
