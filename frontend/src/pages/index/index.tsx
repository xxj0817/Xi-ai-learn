import { Button, Image, Text, Textarea, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useMemo, useState } from 'react'

import CoinBadge from '@/components/CoinBadge'
import Icon from '@/components/Icon'
import ProgressRing from '@/components/ProgressRing'
import StatusBarSpacer from '@/components/StatusBarSpacer'
import TabBar from '@/components/TabBar'
import { generateQuiz } from '@/services/api'
import { useStudyStore } from '@/store/useStudyStore'
import type { QuizRecord } from '@/types/quiz'
import { levelAvatarSvg, mascotSvg } from '@/utils/icons'
import { answeredCount, quizKeywords } from '@/utils/judge'
import { svgToDataUri } from '@/utils/svg'

import './index.scss'

const TEXTAREA_PLACEHOLDER =
  '例如：RAG 和传统搜索有什么区别？\n我想顺便搞懂向量数据库是怎么配合工作的。\n最好通过闯关题帮我记住重点。'

export default function IndexPage() {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  const nickname = useStudyStore((state) => state.nickname)
  const coins = useStudyStore((state) => state.coins)
  const history = useStudyStore((state) => state.history)
  const startQuiz = useStudyStore((state) => state.startQuiz)
  const openQuiz = useStudyStore((state) => state.openQuiz)
  const viewReport = useStudyStore((state) => state.viewReport)

  const completedRecords = useMemo(
    () => history.filter((record) => record.status === 'completed'),
    [history]
  )
  const inProgressRecords = useMemo(
    () => history.filter((record) => record.status === 'in_progress'),
    [history]
  )

  const handleGenerate = async () => {
    const value = input.trim()
    if (loading) {
      return
    }
    if (value.length < 2) {
      Taro.showToast({ title: '先输入你想学的内容', icon: 'none' })
      return
    }

    setLoading(true)
    setErrorMessage('')
    try {
      const quiz = await generateQuiz({
        user_input: value,
        question_count: 5,
        difficulty: 'mixed'
      })
      startQuiz(quiz)
      Taro.navigateTo({ url: '/pages/quiz/index' })
    } catch (error) {
      const message = error instanceof Error ? error.message : '生成失败，请稍后重试'
      setErrorMessage(message)
      Taro.showToast({ title: message, icon: 'none' })
    } finally {
      setLoading(false)
    }
  }

  const handleResume = (record: QuizRecord) => {
    if (openQuiz(record.quiz.quiz_id)) {
      Taro.navigateTo({ url: '/pages/quiz/index' })
    }
  }

  const handleOpenReport = (record: QuizRecord) => {
    if (viewReport(record.quiz.quiz_id)) {
      Taro.navigateTo({ url: '/pages/report/index' })
    }
  }

  const progressOf = (record: QuizRecord): number => {
    const total = record.quiz.questions.length || 1
    return Math.round((answeredCount(record.answers) / total) * 100)
  }

  return (
    <View className='home-page app-page'>
      <StatusBarSpacer />

      <View className='home-page__body'>
        <View className='home-toolbar'>
          <View className='hello-user'>
            <View className='hello-avatar'>
              <Text>鱼</Text>
            </View>
            <Text className='hello-name'>你好，{nickname}</Text>
          </View>
          <CoinBadge value={coins} />
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
              onClick={handleGenerate}
            >
              <Icon name='arrowRight' size={16} color='#ffffff' />
              <Text>{loading ? 'AI 正在出题…' : '开始生成题目'}</Text>
            </Button>
          </View>

          {loading ? (
            <View className='home-loading'>
              <View className='home-loading__dot' />
              <Text className='home-loading__text'>正在整理知识并生成闯关题，请稍候</Text>
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
            {completedRecords.slice(0, 4).map((record) => (
              <View
                className='quiz-card'
                key={record.quiz.quiz_id}
                onClick={() => handleOpenReport(record)}
              >
                <View className='quiz-card__dot'>
                  <Text>✓</Text>
                </View>
                <View className='quiz-card__body'>
                  <Text className='quiz-card__name'>{record.quiz.title}</Text>
                  <Text className='quiz-card__meta'>
                    关键词：{quizKeywords(record.quiz).join(' / ') || '核心概念'}
                  </Text>
                </View>
              </View>
            ))}
          </View>
        ) : null}

        {inProgressRecords.length > 0 ? (
          <View className='level-list'>
            <Text className='level-list__title'>未完成关卡</Text>
            {inProgressRecords.map((record, index) => {
              const percent = progressOf(record)
              const color = index % 2 === 0 ? '#ff7a2f' : '#4e9fff'
              return (
                <View className='level-item' key={record.quiz.quiz_id} onClick={() => handleResume(record)}>
                  <View className='level-item__avatar'>
                    <Image
                      className='level-item__avatar-image'
                      src={svgToDataUri(levelAvatarSvg(index))}
                      mode='aspectFit'
                    />
                  </View>
                  <View className='level-item__body'>
                    <Text className='level-item__name'>{record.quiz.title}</Text>
                    <Text className='level-item__meta'>{record.quiz.questions.length} 题</Text>
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
      </View>

      <TabBar active='home' />
    </View>
  )
}
