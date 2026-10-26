import { Image, Text, View } from '@tarojs/components'

import ProgressRing from '@/components/ProgressRing'
import type { QuizRecord } from '@/types/quiz'
import { levelAvatarSvg } from '@/utils/icons'
import { answeredCount } from '@/utils/judge'
import { svgToDataUri } from '@/utils/svg'

import './index.scss'

interface RecordRowProps {
  record: QuizRecord
  index: number
  onTap: () => void
}

export default function RecordRow({ record, index, onTap }: RecordRowProps) {
  const total = record.quiz.questions.length || 1
  const percent =
    record.status === 'completed' && record.report
      ? record.report.accuracy
      : Math.round((answeredCount(record.answers) / total) * 100)
  const color = index % 2 === 0 ? '#ff7a2f' : '#4e9fff'
  const meta =
    record.status === 'completed'
      ? `正确率 ${percent}% · 共 ${total} 题`
      : `已答 ${answeredCount(record.answers)} / ${total} 题`

  return (
    <View className='record-row' onClick={onTap}>
      <View className='record-row__avatar'>
        <Image className='record-row__avatar-image' src={svgToDataUri(levelAvatarSvg(index))} mode='aspectFit' />
      </View>
      <View className='record-row__body'>
        <Text className='record-row__name'>{record.quiz.title}</Text>
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
