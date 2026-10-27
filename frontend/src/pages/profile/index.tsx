import { Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'

import EmptyState from '@/components/EmptyState'
import Icon from '@/components/Icon'
import RecordRow from '@/components/RecordRow'
import StatusBarSpacer from '@/components/StatusBarSpacer'
import TabBar from '@/components/TabBar'
import XpBadge from '@/components/XpBadge'
import { useUserStore } from '@/store/useUserStore'
import type { QuizHistoryItem } from '@/types/user'

import './index.scss'

export default function ProfilePage() {
  const profile = useUserStore((state) => state.profile)
  const history = useUserStore((state) => state.history)
  const loggedIn = useUserStore((state) => state.loggedIn)
  const error = useUserStore((state) => state.error)
  const ensureSession = useUserStore((state) => state.ensureSession)
  const rename = useUserStore((state) => state.rename)

  useDidShow(() => {
    void ensureSession()
  })

  const recent = history.slice(0, 5)

  const handleOpen = (item: QuizHistoryItem) => {
    Taro.navigateTo({ url: `/pages/report/index?quiz_id=${item.quiz_id}` })
  }

  const handleRename = async () => {
    if (!loggedIn) {
      Taro.showToast({ title: '登录后才能修改昵称', icon: 'none' })
      return
    }
    const option = {
      title: '修改昵称',
      editable: true,
      placeholderText: '请输入新的昵称',
      content: profile?.nickname ?? '',
      confirmText: '保存',
      cancelText: '取消'
    } as unknown as Taro.showModal.Option
    const result = (await Taro.showModal(option)) as unknown as { confirm: boolean; content?: string }
    if (!result.confirm) {
      return
    }
    const value = (result.content ?? '').trim()
    if (!value) {
      Taro.showToast({ title: '昵称不能为空', icon: 'none' })
      return
    }
    const ok = await rename(value)
    Taro.showToast({ title: ok ? '昵称已更新' : '修改失败，请重试', icon: 'none' })
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
            <Text className='hello-name'>你好，{profile?.nickname ?? '学习者'}</Text>
          </View>
          <XpBadge value={profile?.total_xp ?? 0} />
        </View>

        <Text className='profile-title'>我的学习</Text>
        <Text className='profile-subtitle'>
          {loggedIn ? '学习记录已同步到你的微信账号。' : '登录后可同步学习记录与经验值。'}
        </Text>

        <View className='profile-metrics'>
          <View className='metric-card'>
            <Text className='metric-card__value'>{profile?.total_xp ?? 0}</Text>
            <Text className='metric-card__label'>经验值</Text>
          </View>
          <View className='metric-card'>
            <Text className='metric-card__value'>{profile?.quiz_count ?? 0}</Text>
            <Text className='metric-card__label'>完成关卡</Text>
          </View>
          <View className='metric-card'>
            <Text className='metric-card__value'>{profile?.correct_count ?? 0}</Text>
            <Text className='metric-card__label'>答对题数</Text>
          </View>
          <View className='metric-card'>
            <Text className='metric-card__value'>{profile?.average_accuracy ?? 0}%</Text>
            <Text className='metric-card__label'>平均正确率</Text>
          </View>
        </View>

        <View className='profile-rename' onClick={handleRename}>
          <Icon name='edit' size={14} color='#cb6326' />
          <Text>修改昵称</Text>
        </View>

        {error ? <Text className='profile-error'>{error}</Text> : null}

        <Text className='profile-section'>最近记录</Text>

        {recent.length > 0 ? (
          recent.map((item, index) => (
            <RecordRow
              key={item.quiz_id}
              title={item.title}
              meta={`正确率 ${item.accuracy}% · 共 ${item.question_count} 题`}
              percent={item.accuracy}
              index={index}
              onTap={() => handleOpen(item)}
            />
          ))
        ) : (
          <EmptyState
            title='还没有学习记录'
            description='完成第一组闯关后，这里会展示你的经验值、正确率和历史关卡。'
            actionText='去闯一关'
            onAction={() => Taro.reLaunch({ url: '/pages/index/index' })}
          />
        )}
      </View>

      <TabBar active='profile' />
    </View>
  )
}