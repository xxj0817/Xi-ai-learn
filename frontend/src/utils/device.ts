import Taro from '@tarojs/taro'

export function getStatusBarHeight(): number {
  try {
    if (typeof Taro.getWindowInfo === 'function') {
      return Taro.getWindowInfo().statusBarHeight ?? 0
    }
    return Taro.getSystemInfoSync().statusBarHeight ?? 0
  } catch (error) {
    console.warn('getStatusBarHeight failed', error)
    return 0
  }
}
