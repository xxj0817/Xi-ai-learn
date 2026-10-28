import { Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import EmptyState from '@/components/EmptyState'
import RecordRow from '@/components/RecordRow'
import TabBar from '@/components/TabBar'
import XpBadge from '@/components/XpBadge'
import { useUserStore } from '@/store/useUserStore'
import type { InProgressQuizItem, QuizHistoryItem } from '@/types/user'
import { resumeQuizById } from '@/utils/resume'

import './index.scss'

export default function BankPage() {
  const profile = useUserStore((state) => state.profile)
  const history = useUserStore((state) => state.history)
  const inProgress = useUserStore((state) => state.inProgress)
  const ensureSession = useUserStore((state) => state.ensureSession)
  const [resumingId, setResumingId] = useState('')

  useDidShow(() => {
    void ensureSession()
  })

  const handleOpen = (item: QuizHistoryItem) => {
    Taro.navigateTo({ url: `/pages/report/index?quiz_id=${item.quiz_id}` })
  }

  const handleResume = async (item: InProgressQuizItem) => {
    if (resumingId) {
      return
    }
    setResumingId(item.quiz_id)
    try {
      await resumeQuizById(item.quiz_id)
      Taro.navigateTo({ url: '/pages/quiz/index' })
    } catch (error) {
      const message = error instanceof Error ? error.message : '加载闯关进度失败'
      Taro.showToast({ title: message, icon: 'none' })
    } finally {
      setResumingId('')
    }
  }

  return (
    <View className='bank-page app-page'>
      <View className='bank-page__body'>
        <View className='bank-toolbar'>
          <Text className='bank-toolbar__title'>题库</Text>
          <XpBadge value={profile?.total_xp ?? 0} />
        </View>

        <Text className='bank-title'>我的知识关卡</Text>
        <Text className='bank-subtitle'>已完成和未完成的闯关都在这里，点开就能继续。</Text>

        {inProgress.map((item, index) => {
          const total = item.question_count || 1
          const percent = Math.min(100, Math.round((item.answered_count / total) * 100))
          return (
            <RecordRow
              key={item.quiz_id}
              title={item.title}
              meta={`进行中 · 已答 ${item.answered_count} / ${item.question_count} 题`}
              percent={percent}
              index={index}
              onTap={() => void handleResume(item)}
            />
          )
        })}

        {history.map((item, index) => (
          <RecordRow
            key={item.quiz_id}
            title={item.title}
            meta={`正确率 ${item.accuracy}% · 共 ${item.question_count} 题`}
            percent={item.accuracy}
            index={inProgress.length + index}
            onTap={() => handleOpen(item)}
          />
        ))}

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