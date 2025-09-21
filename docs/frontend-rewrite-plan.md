# 前端重写实施计划

## 1. 项目目标与范围
- 完全删除现有 `front_end/` Vue 代码库，建立基于 React + Vite + TypeScript 的新前端项目。
- 根据 Figma 设计稿（AI聊天界面）完成主要页面：对话主界面、辅助面板、配置/设置区域等核心流。
- 建立可扩展的组件体系、状态管理、数据请求及测试框架，为后续功能迭代提供稳固基础。

## 2. 技术栈与基础设施
- **构建与框架**：React 18、Vite 5、TypeScript。
- **UI 与样式**：Tailwind CSS、shadcn/ui（Radix 基础组件）、自定义主题配置。
- **状态管理**：Zustand（模块化 store + slice 模式）。
- **数据层**：TanStack Query 5（数据缓存、请求与重试策略）。
- **表单与校验**：React Hook Form + Zod + @hookform/resolvers。
- **路由**：TanStack Router（优先）或 React Router v6+（若遇到阻塞切换方案）。
- **测试体系**：Vitest、@testing-library/react、@testing-library/user-event。
- **代码规范**：ESLint（带 React/TS 规则）、Prettier 或 Biome（二选一，默认 Prettier）、简单 tsconfig（严格模式 + 路径别名）。
- **开发工具链**：Husky + lint-staged（提交前校验）、Storybook (可选) 用于组件开发。

## 3. 项目初始化步骤
1. 删除现有 `front_end/` 目录（保留必要的文档或资源至 `docs/`）。
2. 使用 `npm create vite@latest` 或 `pnpm create vite` 初始化 React + TypeScript 项目，命名 `frontend`（或与现有后端路径一致）。
3. 配置包管理器（建议 pnpm，若团队已有共识可保持 npm）。
4. 安装核心依赖：
   - UI：`tailwindcss postcss autoprefixer`、`shadcn-ui` CLI、`@radix-ui/*`。
   - 状态与数据：`zustand`, `@tanstack/react-query`, `@tanstack/react-query-devtools`。
   - 路由：`@tanstack/react-router`（或 `react-router-dom`）。
   - 表单：`react-hook-form`, `zod`, `@hookform/resolvers`。
   - 测试：`vitest`, `@testing-library/react`, `@testing-library/user-event`, `jsdom`。
   - 代码规范：`eslint`, `@typescript-eslint/*`, `eslint-config-prettier`, `prettier`。
5. 生成 Tailwind 配置、设置 shadcn/ui 主题并导出全局样式（`globals.css`）。
6. 配置 Vite：路径别名（如 `@/` 指向 `src`）、环境变量约定、自动导入工具（可选）。
7. 设置 ESLint + Prettier、tsconfig（严格模式、引入 vite/client 类型）。
8. 配置 Husky + lint-staged（可选但推荐）。

## 4. 架构设计
- **目录结构（示例）**：
  ```text
  frontend/
    ├─ src/
    │   ├─ app/               # 根组件、路由、layout
    │   ├─ components/        # 通用 UI 组件（含 shadcn/ui wrappers）
    │   ├─ features/          # 功能域（按业务拆分）
    │   │   ├─ chat/
    │   │   ├─ profile/
    │   │   └─ settings/
    │   ├─ hooks/             # 自定义 hooks（含 Zustand store hooks）
    │   ├─ lib/               # 工具函数、API 客户端、常量
    │   ├─ stores/            # Zustand stores（可在 features 内再拆 slice）
    │   ├─ services/          # TanStack Query 封装（请求函数 + WebSocket 客户端）
    │   ├─ types/             # TypeScript 类型定义与 Zod schema
    │   ├─ assets/            # 静态资源
    │   └─ test-utils/        # 测试辅助（render helpers）
    ├─ public/
    ├─ index.html
    └─ ...
  ```
- **主题与样式**：统一配置颜色、字体、间距；根据 Figma 中 Material Design 风格调优 Tailwind 主题或使用 CSS 变量。
- **组件原则**：
  - 以 Figma 层级映射组件（如 `ConversationWindow`, `MessageBubble`, `TopBar`）。
  - shadcn/ui 用于基础交互组件（按钮、对话框、Tabs 等），保持原子化，可按需扩展。
  - 复合组件放入 `features/<domain>/components` 中便于复用。
- **状态策略**：
  - 即时 UI 状态、局部偏好使用 `useState` 或 `useReducer`。
  - 全局会话状态、用户配置使用 Zustand store（分片：`useChatStore`, `useUserPreferencesStore`）。
  - 服务器数据以 TanStack Query 管理，请求函数放在 `services/api`；流式数据通过专用 WebSocket 客户端并写入 Zustand。
- **数据契约**：以 `docs/frontend-backend-contract.md` 为准，拆分成 TS 类型模块与 Zod schema，保持前后端对齐。

## 5. 接口契约落地策略
- **网关配置**：
  - 在 `.env` / Vite 环境变量中提供 `VITE_GATEWAY_URL`，默认拼接 `window.location.hostname:8000`，允许本地与生产自定义。
  - 统一封装生成 `/ws/input`、`/ws/output/{taskId}`、`/control/stop`、`/health` 等 URL 的工具函数。
- **输入通道（`/ws/input`）**：
  - 定义 `InputChunkMetadata`、`UploadCompleteMessage`、`UploadProcessedMessage` 等类型对应文档中的字段。
  - 实现 `useInputChannel(taskHandlers)` hook，负责：
    1. 建立连接并等待初始 `task_id`。
    2. 提供 `sendTextChunk`、`sendAudioChunk`、`completeUpload` API。
    3. 将确认/错误消息写入 `useChatStore`。
  - 对 chunk 序号、`upload_complete`、错误处理进行单元测试，防止顺序或缺失问题。
- **输出通道（`/ws/output/{task_id}`）**：
  - 定义 `OutputTextMessage`、`AudioChunkMessage`、`AudioCompleteMessage`、`OutputErrorMessage` 类型。
  - 建立 `useOutputChannel(taskId, handlers)` hook，负责：
    1. 监听成功文本消息，推送到聊天消息列表。
    2. 汇总音频 chunk（内存或 MediaSource）并处理 `audio_complete`。
    3. 处理 control/timeout/errors，更新 UI 状态。
  - 规划音频缓存策略（内存 Blob + URL，失败则回退到提示）。
- **控制接口 `POST /control/stop`**：
  - 在 `services/api/control.ts` 内实现 `stopPlayback(taskId)`，对 409/503 等特定 code 显示对应 toast。
  - UI 中的“停止播放”按钮在 output store 中读取当前任务 ID。
- **诊断接口**：
  - `useGatewayHealthQuery`（TanStack Query）拉取 `/health`；`useOutputHealthQuery` 拉取 `/internal/output/health`，驱动状态徽标。
  - 仅在调试面板或设置页面展示，避免主流程阻塞。
- **ASR 任务（可选）**：
  - 若后续需要上传文件，提前预留 `enqueueAsrTask` API 与表单 schema，利用 React Hook Form + Zod 校验路径、语言参数。
- **错误与重连策略**：
  - 在 `lib/retry.ts` 定义指数退避规则；对 WebSocket 提供 1 次自动重连（仅在 server 未返回致命错误时）。
  - 将 `Processing timeout`、`Chunk ID mismatch` 等错误映射成用户可理解的提示文案。
- **契约变更流程**：
  - 所有接口类型集中于 `src/types/gateway/`，引用时只读类型；
  - 通过 Zod schema 直接与运行时消息做校验，遇到 schema 不符时记录 telemetry 并安全降级。

## 6. Figma 映射与页面交付
- **核心视图**：
  - 聊天会话主界面（对话列表、输入框、工具栏、Chrome shell 外框如需保留）。
  - 顶部导航栏（头像、菜单按钮）。
  - 右侧或底部辅助组件（轮播/功能快捷入口）。
- **设计落地步骤**：
  1. 导出设计标注：颜色、字体、spacing。
  2. 为主要布局建立 `Layout` 组件（网格/栅格）。
  3. 按 Figma 组件树分阶段实现：先骨架（布局 + 空状态），再细节（图标、渐层、阴影）。
  4. 校验不同屏幕尺寸（Figma 主要为桌面 + 移动示例）。
  5. 与设计稿进行视觉对齐（可使用 Figma Inspector 或对比截图）。

## 7. 开发迭代阶段
1. **准备阶段**（Day 0-1）
   - 备份/导出旧前端必要资源。
   - 清理仓库旧前端目录。
   - 初始化新项目与基础配置。
2. **基础框架搭建**（Day 2-4）
   - 配置 Tailwind + shadcn/ui。
   - 建立路由骨架、Layout、主题。
   - 搭建 Zustand store、TanStack Query Provider、WebSocket 客户端基础。
3. **核心界面实现**（Day 5-10）
   - 聊天窗口、消息气泡、输入框。
   - 顶部导航、底部工具栏。
   - 响应式适配。
4. **功能整合**（Day 11-14）
   - 与后端 API/WebSocket 对接（落实契约文档）。
   - 处理消息发送、历史记录、会话管理。
   - 表单（设置、偏好）引入 React Hook Form + Zod。
5. **测试 & 打磨**（Day 15-18）
   - 编写单元/组件测试（Vitest + Testing Library）。
   - 集成测试：MSW 模拟 WebSocket/HTTP。
   - 性能调优、可访问性检查。
6. **验收与交付**（Day 19+）
   - 与 UI/产品对齐。
   - 文档更新（README、运行指南）。
   - 预备部署脚本/CI 集成。

## 8. 与后端协作
- 建立双周或按需同步，评审 `frontend-backend-contract.md` 与实现是否一致。
- 若协议需调整，先更新契约文档，再同步实现（后端 + 前端），避免漂移。
- 在 `utils/` 或 `services/gateway` 下维护共享 DTO/类型（可生成 `.d.ts`，由前端消费）。
- 对接 Redis/任务状态时，确保 output-handler 行为变更及时同步。

## 9. 测试策略
- **组件测试**：对 `feature` 层主要组件编写交互测试（消息发送、错误提示）。
- **状态测试**：Zustand store 调用、选择器逻辑、WebSocket hook mocked 行为。
- **集成测试**：使用 MSW 模拟 HTTP；使用 WebSocket mock（如 `isomorphic-ws` + 自建 server）验证流式流程。
- **可选**：引入视觉回归工具（Storybook + Chromatic）或 Playwright 进行端到端测试。

## 10. 发布与运维
- 更新 `docker-compose` 或部署脚本以使用新前端构建产物（`frontend/dist`）。
- 调整 CI：增加 `pnpm install`, `pnpm build`, `pnpm test`，必要时加入 WebSocket 集成测试命令。
- 预留环境变量（API 基础地址、Feature Flags）。
- 编写迁移指南，指导团队本地运行、调试与测试新前端。

## 11. 风险与对策
- **Figma 交互差异**：提前确认交互说明，必要时补充 UX 文档。
- **时间风险**：按阶段完成可交付里程碑，记录阻塞项。
- **技术栈学习曲线**：为团队提供 Tailwind/shadcn/Zustand/TanStack Query 快速上手资料。
- **后端契约变动**：建立单一数据接口定义源，使用 Zod 校验保证运行时安全；出现 schema 失配及时回滚或补丁。
- **实时通信不稳定**：提前设计断线重连与错误提示，提供降级（仅文本模式）。

## 12. 输出成果
- 新的 `frontend/` React 项目目录及其依赖配置。
- 对齐 Figma 的 UI 定稿界面。
- 完整的状态管理、数据请求、表单处理框架。
- 至少覆盖核心流程的测试用例（含 WebSocket 行为）。
- 更新后的运行文档（README/开发指南）与接口契约对应说明。

