import { createApp } from 'vue'
import App from './App.vue'

// Vuetify
import 'vuetify/styles' // 基础样式
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components' // 导入所有组件
import * as directives from 'vuetify/directives' // 导入所有指令
import '@mdi/font/css/materialdesignicons.css' // Material Design Icons

const vuetify = createVuetify({
  components,
  directives,
  icons: {
    defaultSet: 'mdi', // 设置默认图标库为 MDI
  },
  theme: {
    themes: {
      light: {
        dark: false,
        colors: {
          background: '#FEF7FF', // 应用背景色
          surface: '#FFFFFF',    // 聊天面板背景
          panelBackground: '#F3EDF7', // 工具栏和右侧面板背景
          // 你可以根据需要添加更多颜色，例如 primary, secondary 等
          // primary: '#6200EE',
          // secondary: '#03DAC6',
        },
      },
      // 你可以在这里定义 dark 主题
      // dark: { ... }
    },
  },
})

createApp(App)
  .use(vuetify) // 使用 Vuetify 插件
  .mount('#app') 