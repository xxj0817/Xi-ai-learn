import { Button, Image, Input, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useEffect, useState } from 'react'

import EmptyState from '@/components/EmptyState'
import RecordRow from '@/components/RecordRow'
import TabBar from '@/components/TabBar'
import XpBadge from '@/components/XpBadge'
import { useUserStore } from '@/store/useUserStore'
import type { QuizHistoryItem } from '@/types/user'

import './index.scss'

function readAsBase64(filePath: string): Promise<string> {
  return new Promise((resolve, reject) => {
    Taro.getFileSystemManager().readFile({
      filePath,
      encoding: 'base64',
      success: (result) => resolve(String(result.data)),
      fail: () => reject(new Error('读取头像文件失败'))
    })
  })
}

function contentTypeOf(filePath: string): string {
  return /\.png$/i.test(filePath) ? 'image/png' : 'image/jpeg'
}

export default function ProfilePage() {
  const profile = useUserStore((state) => state.profile)
  const history = useUserStore((state) => state.history)
  const loggedIn = useUserStore((state) => state.loggedIn)
  const error = useUserStore((state) => state.error)
  const ensureSession = useUserStore((state) => state.ensureSession)
  const rename = useUserStore((state) => state.rename)
  const changeAvatar = useUserStore((state) => state.changeAvatar)

  const [nicknameDraft, setNicknameDraft] = useState('')
  const [avatarUploading, setAvatarUploading] = useState(false)
  const [savingNickname, setSavingNickname] = useState(false)

  useDidShow(() => {
    void ensureSession()
  })

  useEffect(() => {
    setNicknameDraft(profile?.nickname ?? '')
  }, [profile?.nickname])

  const recent = history.slice(0, 5)

  const handleOpen = (item: QuizHistoryItem) => {
    Taro.navigateTo({ url: `/pages/report/index?quiz_id=${item.quiz_id}` })
  }

  const handleChooseAvatar = async (tempPath: string) => {
    if (!tempPath || avatarUploading) {
      return
    }
    if (!loggedIn) {
      Taro.showToast({ title: '登录后才能设置头像', icon: 'none' })
      return
    }
    setAvatarUploading(true)
    try {
      const base64 = await readAsBase64(tempPath)
      const ok = await changeAvatar(base64, contentTypeOf(tempPath))
      Taro.showToast({ title: ok ? '头像已更新' : '头像更新失败', icon: 'none' })
    } catch (uploadError) {
      const message = uploadError instanceof Error ? uploadError.message : '头像更新失败'
      Taro.showToast({ title: message, icon: 'none' })
    } finally {
      setAvatarUploading(false)
    }
  }

  const handleSaveNickname = async () => {
    const value = nicknameDraft.trim()
    if (!loggedIn) {
      Taro.showToast({ title: '登录后才能修改昵称', icon: 'none' })
      return
    }
    if (!value) {
      Taro.showToast({ title: '昵称不能为空', icon: 'none' })
      return
    }
    if (value === profile?.nickname) {
      Taro.showToast({ title: '昵称没有变化', icon: 'none' })
      return
    }
    setSavingNickname(true)
    try {
      const ok = await rename(value)
      Taro.showToast({ title: ok ? '昵称已更新' : '修改失败，请重试', icon: 'none' })
    } finally {
      setSavingNickname(false)
    }
  }

  return (
    <View className='profile-page app-page'>
      <View className='profile-page__body'>
        <View className='profile-toolbar'>
          <View className='hello-user'>
            <View className='hello-avatar'>
              {profile?.avatar_url ? (
                <Image className='hello-avatar__image' src={profile.avatar_url} mode='aspectFill' />
              ) : (
                <Text>鱼</Text>
              )}
            </View>
            <Text className='hello-name'>你好，{profile?.nickname ?? '学习者'}</Text>
          </View>
          <XpBadge value={profile?.total_xp ?? 0} />
        </View>

        <Text className='profile-title'>我的学习</Text>
        <Text className='profile-subtitle'>
          {loggedIn ? '学习记录已同步到你的微信账号。' : '登录后可同步学习记录与经验值。'}
        </Text>

        <View className='profile-account'>
          <Button
            className='profile-account__avatar'
            openType='chooseAvatar'
            onChooseAvatar={(event) => {
              void handleChooseAvatar(event.detail.avatarUrl)
            }}
          >
            {profile?.avatar_url ? (
              <Image className='profile-account__avatar-image' src={profile.avatar_url} mode='aspectFill' />
            ) : (
              <Text className='profile-account__avatar-text'>{avatarUploading ? '…' : '鱼'}</Text>
            )}
          </Button>

          <View className='profile-account__form'>
            <Text className='profile-account__label'>头像与昵称</Text>
            <Input
              className='profile-account__input'
              type='nickname'
              value={nicknameDraft}
              placeholder='点击获取微信昵称'
              maxlength={20}
              onInput={(event) => setNicknameDraft(event.detail.value)}
            />
            <View className='profile-account__actions'>
              <Button className='profile-account__save' onClick={() => void handleSaveNickname()}>
                {savingNickname ? '保存中…' : '保存昵称'}
              </Button>
              <Text className='profile-account__hint'>点击左侧头像可从微信选择</Text>
            </View>
          </View>
        </View>

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