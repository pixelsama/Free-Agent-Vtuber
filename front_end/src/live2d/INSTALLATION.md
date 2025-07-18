# Live2D Cubism SDK for Web 集成指南

## 概述

本项目已经为Live2D Cubism SDK for Web的集成做好了准备。您需要下载官方SDK并按照以下步骤完成集成。

## 前置要求

- Node.js 16+
- Vue 3
- Vite
- 支持WebGL的现代浏览器

## 安装步骤

### 1. 下载Live2D Cubism SDK for Web

1. 访问 [Live2D官网](https://www.live2d.com/en/sdk/download/web/)
2. 阅读并同意软件许可协议
3. 下载最新版本的SDK

### 2. 复制SDK文件

将下载的SDK文件按以下结构复制到项目中：

```
# 从SDK复制到项目
CubismSdkForWeb/Core/*                    → src/live2d/core/
CubismSdkForWeb/Framework/*               → src/live2d/framework/
CubismSdkForWeb/Samples/Resources/*       → src/live2d/models/
CubismSdkForWeb/Samples/TypeScript/Demo/src/* → src/live2d/utils/
```

### 3. 更新index.html

在 `index.html` 的 `<head>` 部分添加Live2D Core脚本：

```html
<script src="/src/live2d/core/live2dcubismcore.js"></script>
```

### 4. 更新Vite配置

在 `vite.config.js` 中添加TypeScript支持：

```javascript
export default defineConfig({
  // ... 现有配置
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    extensions: [
      '.js',
      '.json',
      '.jsx',
      '.mjs',
      '.ts',    // 添加TypeScript支持
      '.tsx',
      '.vue',
    ],
  },
})
```

### 5. 更新Live2DManager

替换 `src/live2d/utils/Live2DManager.js` 中的模拟代码为真实的Live2D SDK调用：

```javascript
// 导入Live2D Framework
import { Live2DCubismFramework } from '../framework/live2dcubismframework'
import { CubismDefaultParameterId } from '../framework/cubismdefaultparameterid'
import { CubismModelSettingJson } from '../framework/cubismmodelsettingjson'
// ... 其他必要的导入

// 在initialize方法中
Live2DCubismFramework.startUp()
Live2DCubismFramework.initialize()
```

### 6. 添加模型文件

将您的Live2D模型文件放置在 `src/live2d/models/` 目录中，或使用SDK提供的示例模型。

## 目录结构

完成安装后，您的Live2D目录结构应该如下：

```
src/live2d/
├── README.md
├── INSTALLATION.md
├── core/
│   ├── live2dcubismcore.js
│   └── live2dcubismcore.d.ts
├── framework/
│   ├── live2dcubismframework.ts
│   ├── cubismmodel.ts
│   ├── cubismrenderer.ts
│   └── ... (其他framework文件)
├── models/
│   ├── sample/
│   │   ├── sample.model3.json
│   │   ├── sample.moc3
│   │   ├── textures/
│   │   ├── motions/
│   │   └── expressions/
│   └── ... (其他模型)
├── utils/
│   ├── Live2DManager.js
│   ├── lappdefine.ts
│   ├── lappmodel.ts
│   └── ... (其他工具文件)
└── types/
    └── ... (TypeScript类型定义)
```

## 使用方法

### 基本使用

```vue
<template>
  <Live2DViewer 
    :model-path="'/live2d/models/sample/sample.model3.json'"
    :width="400"
    :height="600"
    @model-loaded="onModelLoaded"
    @model-error="onModelError"
  />
</template>

<script setup>
import Live2DViewer from '@/components/Live2DViewer.vue'

const onModelLoaded = (model) => {
  console.log('模型加载成功:', model)
}

const onModelError = (error) => {
  console.error('模型加载失败:', error)
}
</script>
```

### 控制模型

```vue
<script setup>
import { ref } from 'vue'

const live2dViewer = ref(null)

// 播放动作
const playMotion = () => {
  live2dViewer.value?.playMotion('TapBody', 0)
}

// 设置表情
const setExpression = () => {
  live2dViewer.value?.setExpression('f01')
}
</script>
```

## 许可证注意事项

- Live2D Cubism SDK有特定的许可证要求
- 示例模型仅供开发和测试使用
- 商业使用请确保遵守Live2D的许可协议
- 发布前请仔细阅读Live2D的发布指南

## 故障排除

### 常见问题

1. **WebGL不支持**
   - 确保浏览器支持WebGL
   - 检查硬件加速是否启用

2. **模型加载失败**
   - 检查模型文件路径是否正确
   - 确保所有相关文件都已复制

3. **TypeScript错误**
   - 确保Vite配置包含TypeScript支持
   - 检查类型定义文件是否正确导入

### 调试技巧

- 打开浏览器开发者工具查看控制台错误
- 检查网络面板确认文件加载状态
- 使用Live2D的调试功能

## 更多资源

- [Live2D官方文档](https://docs.live2d.com/)
- [Live2D SDK教程](https://docs.live2d.com/en/cubism-sdk-tutorials/top/)
- [Live2D社区](https://community.live2d.com/)