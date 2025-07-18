# Live2D 集成说明

本目录包含Live2D Cubism SDK for Web的集成文件。

## 目录结构

```
live2d/
├── README.md           # 本文件
├── core/              # Live2D Core 文件
├── framework/         # Live2D Framework 文件
├── models/            # Live2D 模型文件
├── utils/             # 工具类和辅助函数
└── types/             # TypeScript 类型定义
```

## 安装步骤

1. 从 Live2D 官网下载 Cubism SDK for Web
2. 将以下文件复制到对应目录：
   - `Core/*` → `src/live2d/core/`
   - `Framework/*` → `src/live2d/framework/`
   - `Samples/Resources/*` → `src/live2d/models/`
   - `Samples/TypeScript/Demo/src/*` → `src/live2d/utils/`

## 使用方法

```vue
<template>
  <Live2DViewer 
    :model-path="'/live2d/models/sample/sample.model3.json'"
    :width="400"
    :height="600"
    @model-loaded="onModelLoaded"
  />
</template>
```

## 注意事项

- 请确保遵守 Live2D 的许可协议
- 示例模型仅供开发测试使用
- 生产环境请使用自己的模型文件