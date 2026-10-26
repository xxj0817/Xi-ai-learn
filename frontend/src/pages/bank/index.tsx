import { Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useMemo } from 'react'

import CoinBadge from '@/components/CoinBadge'
import EmptyState from '@/components/EmptyState'
import RecordRow from '@/components/RecordRow'
import StatusBarSpacer from '@/components/StatusBarSpacer'
import TabBar from '@/components/TabBar'
import { useStudyStore } from '@/store/useStudyStore'
import type { QuizRecord } from '@/types/quiz'

import './index.scss'

export default function BankPage() {
  const coins = useStudyStore((state) => state.coins)
  const history = useStudyStore((state) => state.history)
  const openQuiz = useStudyStore((state) => state.openQuiz)
  const viewReport = useStudyStore((state) => state.viewReport)

  const records = useMemo(
    () => [...history].sort((first, second) => second.updatedAt - first.updatedAt),
    [history]
  )

  const handleOpen = (record: QuizRecord) => {
    if (record.status === 'completed') {
      if (viewReport(record.quiz.quiz_id)) {
        Taro.navigateTo({ url: '/pages/report/index' })
      }
      return
    }
    if (openQuiz(record.quiz.quiz_id)) {
      Taro.navigateTo({ url: '/pages/quiz/index' })
    }
  }

  return (
    <View className='bank-page app-page'>
      <StatusBarSpacer />

      <View className='bank-page__body'>
        <View className='bank-toolbar'>
          <Text className='bank-toolbar__title'>题库</Text>
          <CoinBadge value={coins} />
        </View>

        <Text className='bank-title'>我的知识关卡</Text>
        <Text className='bank-subtitle'>已完成和未完成的闯关都在这里，点开就能继续。</Text>

        {records.length > 0 ? (
          records.map((record, index) => (
            <RecordRow key={record.quiz.quiz_id} record={record} index={index} onTap={() => handleOpen(record)} />
          ))
        ) : (
          <EmptyState
            title='题库还是空的'
            description='回到首页输入一个想学的知识点，生成你的第一组闯关题。'
            actionText='去闯一关'
            onAction={() => Taro.reLaunch({ url: '/pages/index/index' })}
          />
        )}
      </View>

      <TabBar active='bank' />
    </View>
  )
}
