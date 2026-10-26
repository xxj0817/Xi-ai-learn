import { Image, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import type { ReactNode } from 'react'

import { ringDataUri } from '@/utils/svg'

import './index.scss'

interface ProgressRingProps {
  percent: number
  size?: number
  stroke?: number
  color?: string
  children?: ReactNode
}

export default function ProgressRing({
  percent,
  size = 52,
  stroke = 6,
  color = '#ff7a2f',
  children
}: ProgressRingProps) {
  const svgSize = 120
  const svgStroke = (stroke / size) * svgSize

  return (
    <View className='progress-ring' style={{ width: Taro.pxTransform(size), height: Taro.pxTransform(size) }}>
      <Image
        className='progress-ring__image'
        src={ringDataUri(percent, color, svgSize, svgStroke)}
        style={{ width: Taro.pxTransform(size), height: Taro.pxTransform(size) }}
        mode='aspectFit'
      />
      <View
        className='progress-ring__inner'
        style={{ top: Taro.pxTransform(stroke), right: Taro.pxTransform(stroke), bottom: Taro.pxTransform(stroke), left: Taro.pxTransform(stroke) }}
      />
      {children ? <View className='progress-ring__content'>{children}</View> : null}
    </View>
  )
}
