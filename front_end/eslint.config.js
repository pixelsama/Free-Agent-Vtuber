import vue from 'eslint-plugin-vue';

export default [
  {
    files: ['**/*.{js,vue}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
    },
    plugins: {
      vue,
    },
    rules: {
      ...vue.configs['vue3-essential'].rules,
    },
  },
];

