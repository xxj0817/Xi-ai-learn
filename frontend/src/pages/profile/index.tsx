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

export default function ProfilePage() {
  const nickname = useStudyStore((state) => state.nickname)
  const coins = useStudyStore((state) => state.coins)
  const xp = useStudyStore((state) => state.xp)
  const history = useStudyStore((state) => state.history)
  const openQuiz = useStudyStore((state) => state.openQuiz)
  const viewReport = useStudyStore((state) => state.viewReport)

  const completed = useMemo(() => history.filter((item) => item.status === 'completed'), [history])
  const averageAccuracy = useMemo(() => {
    const reports = completed.filter((item) => item.report)
    if (reports.length === 0) {
      return 0
    }
    const total = reports.reduce((sum, item) => sum + (item.report?.accuracy ?? 0), 0)
    return Math.round(total / reports.length)
  }, [completed])

  const recent = useMemo(
    () => [...history].sort((first, second) => second.updatedAt - first.updatedAt).slice(0, 5),
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
    <View className='profile-page app-page'>
      <StatusBarSpacer />

      <View className='profile-page__body'>
        <View className='profile-toolbar'>
          <View className='hello-user'>
            <View className='hello-avatar'>
              <Text>鱼</Text>
            </View>
            <Text className='hello-name'>你好，{nickname}</Text>
          </View>
          <CoinBadge value={coins} />
        </View>

        <Text className='profile-title'>我的学习</Text>
        <Text className='profile-subtitle'>
          学习记录保存在本机，后续接入账号后会自动同步。
        </Text>

        <View className='profile-metrics'>
          <View className='metric-card'>
            <Text className='metric-card__value'>{coins}</Text>
            <Text className='metric-card__label'>金币</Text>
          </View>
          <View className='metric-card'>
            <Text className='metric-card__value'>{xp}</Text>
            <Text className='metric-card__label'>经验值</Text>
          </View>
          <View className='metric-card'>
            <Text className='metric-card__value'>{completed.length}</Text>
            <Text className='metric-card__label'>完成关卡</Text>
          </View>
          <View className='metric-card'>
            <Text className='metric-card__value'>{averageAccuracy}%</Text>
            <Text className='metric-card__label'>平均正确率</Text>
          </View>
        </View>

        <Text className='profile-section'>最近记录</Text>

        {recent.length > 0 ? (
          recent.map((record, index) => (
            <RecordRow key={record.quiz.quiz_id} record={record} index={index} onTap={() => handleOpen(record)} />
          ))
        ) : (
          <EmptyState
            title='还没有学习记录'
            description='完成第一组闯关后，这里会展示你的金币、经验和正确率。'
            actionText='去闯一关'
            onAction={() => Taro.reLaunch({ url: '/pages/index/index' })}
          />
        )}
      </View>

      <TabBar active='profile' />
    </View>
  )
}
