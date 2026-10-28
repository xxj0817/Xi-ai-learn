import { Button, Image, Text, Textarea, View } from '@tarojs/components'
import Taro, { useDidHide, useDidShow } from '@tarojs/taro'
import { useCallback, useMemo, useRef, useState } from 'react'

import Icon from '@/components/Icon'
import ProgressRing from '@/components/ProgressRing'
import TabBar from '@/components/TabBar'
import XpBadge from '@/components/XpBadge'
import { createQuizTask } from '@/services/api'
import { useStudyStore } from '@/store/useStudyStore'
import { useUserStore } from '@/store/useUserStore'
import type { QuizTask, QuizTaskStage } from '@/types/quiz'
import type { InProgressQuizItem, QuizHistoryItem } from '@/types/user'
import { levelAvatarSvg, mascotSvg } from '@/utils/icons'
import {
  QuizTaskCancelledError,
  forgetQuizTask,
  recallQuizTask,
  rememberQuizTask,
  waitForQuizTask
} from '@/utils/quizTask'
import { resumeQuizById } from '@/utils/resume'
import { svgToDataUri } from '@/utils/svg'

import './index.scss'

const TEXTAREA_PLACEHOLDER =
  '例如：RAG 和传统搜索有什么区别？\n我想顺便搞懂向量数据库是怎么配合工作的。\n最好通过闯关题帮我记住重点。'

const STAGE_TEXT: Record<QuizTaskStage, string> = {
  queued: '任务已创建，正在排队…',
  researching: '正在联网检索最新资料…',
  generating: 'AI 正在组织闯关题目…',
  validating: '正在校验答案与来源引证…',
  saving: '正在保存题库…',
  completed: '生成完成，即将进入闯关…',
  failed: '生成失败'
}

export default function IndexPage() {
  const [input, setInput] = useState('')
  const [task, setTask] = useState<QuizTask | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [resumingId, setResumingId] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const activeRef = useRef(false)
  const loading = submitting || task !== null

  const profile = useUserStore((state) => state.profile)
  const history = useUserStore((state) => state.history)
  const inProgress = useUserStore((state) => state.inProgress)
  const ensureSession = useUserStore((state) => state.ensureSession)
  const startQuiz = useStudyStore((state) => state.startQuiz)

  const runTask = useCallback(
    async (taskId: string) => {
      activeRef.current = true
      try {
        const finished = await waitForQuizTask(taskId, {
          onUpdate: (next) => setTask(next),
          shouldContinue: () => activeRef.current
        })
        forgetQuizTask()
        setTask(null)
        if (finished.quiz) {
          startQuiz(finished.quiz)
          Taro.navigateTo({ url: '/pages/quiz/index' })
        }
      } catch (error) {
        if (error instanceof QuizTaskCancelledError) {
          return
        }
        forgetQuizTask()
        setTask(null)
        const message = error instanceof Error ? error.message : '生成失败，请稍后重试'
        setErrorMessage(message)
        Taro.showToast({ title: message, icon: 'none' })
      } finally {
        activeRef.current = false
      }
    },
    [startQuiz]
  )

  useDidShow(() => {
    void ensureSession()
    const stored = recallQuizTask()
    if (!stored || activeRef.current) {
      return
    }
    if (stored.input) {
      setInput((current) => current || stored.input)
    }
    setErrorMessage('')
    setSubmitting(true)
    void runTask(stored.task_id).finally(() => setSubmitting(false))
  })

  useDidHide(() => {
    activeRef.current = false
  })

  const completedRecords = useMemo(() => history.slice(0, 4), [history])

  const handleGenerate = async () => {
    const value = input.trim()
    if (loading) {
      return
    }
    if (value.length < 2) {
      Taro.showToast({ title: '先输入你想学的内容', icon: 'none' })
      return
    }

    setSubmitting(true)
    setErrorMessage('')
    try {
      const created = await createQuizTask({
        user_input: value,
        question_count: 5,
        difficulty: 'mixed'
      })
      rememberQuizTask({ task_id: created.task_id, input: value })
      setTask(created)
      await runTask(created.task_id)
    } catch (error) {
      const message = error instanceof Error ? error.message : '生成失败，请稍后重试'
      setErrorMessage(message)
      Taro.showToast({ title: message, icon: 'none' })
    } finally {
      setSubmitting(false)
    }
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

  const handleOpenReport = (item: QuizHistoryItem) => {
    Taro.navigateTo({ url: `/pages/report/index?quiz_id=${item.quiz_id}` })
  }

  const percentOf = (item: InProgressQuizItem): number => {
    const total = item.question_count || 1
    return Math.min(100, Math.round((item.answered_count / total) * 100))
  }

  return (
    <View className='home-page app-page'>
      <View className='home-page__body'>
        <View className='home-toolbar'>
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

        <Text className='home-title'>今天想闯哪一关？</Text>

        <View className='quick-input'>
          <View className='quick-input__head'>
            <View className='quick-input__label'>
              <Text>输入你想学的内容</Text>
            </View>
            <View className='mini-mascot'>
              <Image className='mini-mascot__image' src={svgToDataUri(mascotSvg())} mode='aspectFit' />
            </View>
          </View>

          <Textarea
            className='quick-input__textarea'
            value={input}
            onInput={(event) => setInput(event.detail.value)}
            placeholder={TEXTAREA_PLACEHOLDER}
            maxlength={2000}
            autoHeight={false}
          />

          <View className='home-actions'>
            <Button
              className={loading ? 'home-btn home-btn--primary home-btn--loading' : 'home-btn home-btn--primary'}
              disabled={loading}
              onClick={handleGenerate}
            >
              <Icon name='arrowRight' size={16} color='#ffffff' />
              <Text>{loading ? 'AI 正在出题…' : '开始生成题目'}</Text>
            </Button>
          </View>

          {task ? (
            <View className='home-task'>
              <View className='home-task__bar'>
                <View
                  className='home-task__fill'
                  style={{ width: `${Math.max(task.progress, 4)}%` }}
                />
              </View>
              <View className='home-task__meta'>
                <Text className='home-task__text'>
                  {STAGE_TEXT[task.stage] ?? '正在生成，请稍候…'}
                </Text>
                <Text className='home-task__percent'>{task.progress}%</Text>
              </View>
            </View>
          ) : null}

          {errorMessage ? (
            <View className='home-error'>
              <Text>{errorMessage}</Text>
            </View>
          ) : null}
        </View>

        {completedRecords.length > 0 ? (
          <View className='quiz-cards'>
            {completedRecords.map((item) => (
              <View className='quiz-card' key={item.quiz_id} onClick={() => handleOpenReport(item)}>
                <View className='quiz-card__dot'>
                  <Text>✓</Text>
                </View>
                <View className='quiz-card__body'>
                  <Text className='quiz-card__name'>{item.title}</Text>
                  <Text className='quiz-card__meta'>
                    正确率 {item.accuracy}% · 共 {item.question_count} 题
                  </Text>
                </View>
              </View>
            ))}
          </View>
        ) : null}

        {inProgress.length > 0 ? (
          <View className='level-list'>
            <Text className='level-list__title'>未完成关卡</Text>
            {inProgress.map((item, index) => {
              const percent = percentOf(item)
              const color = index % 2 === 0 ? '#ff7a2f' : '#4e9fff'
              return (
                <View className='level-item' key={item.quiz_id} onClick={() => void handleResume(item)}>
                  <View className='level-item__avatar'>
                    <Image
                      className='level-item__avatar-image'
                      src={svgToDataUri(levelAvatarSvg(index))}
                      mode='aspectFit'
                    />
                  </View>
                  <View className='level-item__body'>
                    <Text className='level-item__name'>{item.title}</Text>
                    <Text className='level-item__meta'>
                      已答 {item.answered_count} / {item.question_count} 题
                    </Text>
                  </View>
                  <ProgressRing percent={percent} size={52} stroke={6} color={color}>
                    <Text className='level-item__percent' style={{ color }}>
                      {percent}%
                    </Text>
                  </ProgressRing>
                </View>
              )
            })}
          </View>
        ) : null}

        {completedRecords.length === 0 && inProgress.length === 0 ? (
          <View className='home-empty'>
            <Text className='home-empty__title'>还没有闯关记录</Text>
            <Text className='home-empty__desc'>输入一个想学的知识点，生成第一组闯关题就能开始了。</Text>
          </View>
        ) : null}
      </View>

      <TabBar active='home' />
    </View>
  )
}