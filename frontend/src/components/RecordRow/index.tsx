import { Image, Text, View } from '@tarojs/components'

import ProgressRing from '@/components/ProgressRing'
import { levelAvatarSvg } from '@/utils/icons'
import { svgToDataUri } from '@/utils/svg'

import './index.scss'

interface RecordRowProps {
  title: string
  meta: string
  percent: number
  index: number
  onTap: () => void
}

export default function RecordRow({ title, meta, percent, index, onTap }: RecordRowProps) {
  const color = index % 2 === 0 ? '#ff7a2f' : '#4e9fff'

  return (
    <View className='record-row' onClick={onTap}>
      <View className='record-row__avatar'>
        <Image className='record-row__avatar-image' src={svgToDataUri(levelAvatarSvg(index))} mode='aspectFit' />
      </View>
      <View className='record-row__body'>
        <Text className='record-row__name'>{title}</Text>
        <Text className='record-row__meta'>{meta}</Text>
      </View>
      <ProgressRing percent={percent} size={52} stroke={6} color={color}>
        <Text className='record-row__percent' style={{ color }}>
          {percent}%
        </Text>
      </ProgressRing>
    </View>
  )
}