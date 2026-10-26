export default defineAppConfig({
  pages: [
    'pages/index/index',
    'pages/quiz/index',
    'pages/report/index',
    'pages/bank/index',
    'pages/profile/index'
  ],
  window: {
    backgroundTextStyle: 'light',
    backgroundColor: '#f6f4ef',
    navigationStyle: 'custom',
    navigationBarTitleText: '鱼皮 AI 闯关学习',
    navigationBarTextStyle: 'black'
  }
})
