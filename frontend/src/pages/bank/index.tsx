import { Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'

import EmptyState from '@/components/EmptyState'
import RecordRow from '@/components/RecordRow'
import StatusBarSpacer from '@/components/StatusBarSpacer'
import TabBar from '@/components/TabBar'
import XpBadge from '@/components/XpBadge'
import { useStudyStore } from '@/store/useStudyStore'
import { useUserStore } from '@/store/useUserStore'
import type { QuizHistoryItem } from '@/types/user'

import './index.scss'

export default function BankPage() {
  const profile = useUserStore((state) => state.profile)
  const history = useUserStore((state) => state.history)
  const ensureSession = useUserStore((state) => state.ensureSession)
  const openQuiz = useStudyStore((state) => state.openQuiz)
  const demoRecords = useStudyStore((state) => state.demoRecords)

  useDidShow(() => {
    void ensureSession()
  })

  const inProgress = demoRecords.filter((record) => record.status === 'in_progress')

  const handleOpen = (item: QuizHistoryItem) => {
    Taro.navigateTo({ url: `/pages/report/index?quiz_id=${item.quiz_id}` })
  }

  const handleResume = (quizId: string) => {
    if (openQuiz(quizId)) {
      Taro.navigateTo({ url: '/pages/quiz/index' })
    }
  }

  return (
    <View className='bank-page app-page'>
      <StatusBarSpacer />

      <View className='bank-page__body'>
        <View className='bank-toolbar'>
          <Text className='bank-toolbar__title'>题库</Text>
          <XpBadge value={profile?.total_xp ?? 0} />
        </View>

        <Text className='bank-title'>我的知识关卡</Text>
        <Text className='bank-subtitle'>已完成和未完成的闯关都在这里，点开就能继续。</Text>

        {history.map((item, index) => (
          <RecordRow
            key={item.quiz_id}
            title={item.title}
            meta={`正确率 ${item.accuracy}% · 共 ${item.question_count} 题`}
            percent={item.accuracy}
            index={index}
            onTap={() => handleOpen(item)}
          />
        ))}

        {inProgress.map((record, index) => {
          const answered = Object.keys(record.answers).length
          const total = record.quiz.questions.length || 1
          return (
            <RecordRow
              key={record.quiz.quiz_id}
              title={record.quiz.title}
              meta={`已答 ${answered} / ${total} 题`}
              percent={Math.round((answered / total) * 100)}
              index={history.length + index}
              onTap={() => handleResume(record.quiz.quiz_id)}
            />
          )
        })}

        {history.length === 0 && inProgress.length === 0 ? (
          <EmptyState
            title='题库还是空的'
            description='回到首页输入一个想学的知识点，生成你的第一组闯关题。'
            actionText='去闯一关'
            onAction={() => Taro.reLaunch({ url: '/pages/index/index' })}
          />
        ) : null}
      </View>

      <TabBar active='bank' />
    </View>
  )
}