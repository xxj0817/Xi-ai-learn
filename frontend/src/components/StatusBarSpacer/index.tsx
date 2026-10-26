import { View } from '@tarojs/components'
import Taro from '@tarojs/taro'

import { getStatusBarHeight } from '@/utils/device'

export default function StatusBarSpacer() {
  const height = getStatusBarHeight()
  if (!height) {
    return null
  }
  return <View style={{ height: Taro.pxTransform(height), flexShrink: 0 }} />
}
