import { Button, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useEffect, useRef, useState } from 'react'

import XpBadge from '@/components/XpBadge'
import Icon from '@/components/Icon'
import OptionCard, { type OptionState } from '@/components/OptionCard'
import { generateReport, saveQuizProgress } from '@/services/api'
import { useStudyStore } from '@/store/useStudyStore'
import { useUserStore } from '@/store/useUserStore'
import { isAnswerCorrect } from '@/utils/judge'
import { toAnswerRecords } from '@/utils/progress'

import './index.scss'

const XP_PER_CORRECT = 2
const NAV_TITLE_MAX = 10

export default function QuizPage() {
  const quiz = useStudyStore((state) => state.quiz)
  const currentIndex = useStudyStore((state) => state.currentIndex)
  const answers = useStudyStore((state) => state.answers)
  const totalXp = useUserStore((state) => state.profile?.total_xp ?? 0)
  const submitAnswer = useStudyStore((state) => state.submitAnswer)
  const setIndex = useStudyStore((state) => state.setIndex)
  const completeQuiz = useStudyStore((state) => state.completeQuiz)

  const [pending, setPending] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)
  const startTimeRef = useRef<number>(Date.now())

  useEffect(() => {
    if (!quiz) {
      Taro.reLaunch({ url: '/pages/index/index' })
    }
  }, [quiz])

  useEffect(() => {
    setPending([])
    startTimeRef.current = Date.now()
  }, [currentIndex])

  useEffect(() => {
    if (!quiz) {
      return
    }
    const title = quiz.title.trim()
    Taro.setNavigationBarTitle({
      title: title ? title.slice(0, NAV_TITLE_MAX) : '闯关答题'
    })
  }, [quiz])

  useEffect(() => {
    if (!quiz || Object.keys(answers).length === 0) {
      return
    }
    void saveQuizProgress(quiz.quiz_id, toAnswerRecords(answers)).catch((error) => {
      console.warn('同步答题进度失败', error)
    })
  }, [answers, quiz])

  if (!quiz) {
    return null
  }

  const total = quiz.questions.length
  const safeIndex = Math.min(currentIndex, total - 1)
  const question = quiz.questions[safeIndex]
  const answered = answers[question.id]
  const isCorrect = Boolean(answered?.isCorrect)
  const isLast = safeIndex === total - 1
  const correctCount = Object.values(answers).filter((item) => item.isCorrect).length
  const progress = Math.round(((safeIndex + 1) / total) * 100)

  const recordAnswer = (selected: string[]) => {
    submitAnswer({
      questionId: question.id,
      selected,
      isCorrect: isAnswerCorrect(question, selected),
      durationMs: Date.now() - startTimeRef.current
    })
  }

  const handleOptionTap = (key: string) => {
    if (answered) {
      return
    }
    if (question.type === 'multiple') {
      setPending((previous) =>
        previous.includes(key) ? previous.filter((item) => item !== key) : [...previous, key]
      )
      return
    }
    recordAnswer([key])
  }

  const handleSubmitMultiple = () => {
    if (pending.length === 0) {
      Taro.showToast({ title: '至少选择一个选项', icon: 'none' })
      return
    }
    recordAnswer(pending)
  }

  const finishQuiz = async () => {
    setSubmitting(true)
    try {
      const report = await generateReport({
        quiz_id: quiz.quiz_id,
        topic: quiz.title,
        questions: quiz.questions,
        answer_records: quiz.questions.map((item) => {
          const answer = answers[item.id]
          return {
            question_id: item.id,
            selected_answers: answer?.selected ?? [],
            is_correct: Boolean(answer?.isCorrect),
            duration_ms: answer?.durationMs ?? 0
          }
        })
      })
      completeQuiz(report)
      const userState = useUserStore.getState()
      void userState.loadProfile()
      void userState.loadHistory(1)
      void userState.loadInProgress()
      Taro.redirectTo({ url: '/pages/report/index' })
    } catch (error) {
      const message = error instanceof Error ? error.message : '报告生成失败，请重试'
      Taro.showToast({ title: message, icon: 'none' })
    } finally {
      setSubmitting(false)
    }
  }

  const handleNext = () => {
    if (!answered || submitting) {
      return
    }
    if (!isLast) {
      setIndex(safeIndex + 1)
      return
    }
    void finishQuiz()
  }

  const handlePrev = () => {
    if (safeIndex > 0) {
      setIndex(safeIndex - 1)
    }
  }

  const handleClose = async () => {
    const result = await Taro.showModal({
      title: '退出本关？',
      content: '当前进度会保留，可以随时从首页继续。',
      confirmText: '退出',
      cancelText: '继续答题'
    })
    if (result.confirm) {
      Taro.reLaunch({ url: '/pages/index/index' })
    }
  }

  const optionState = (key: string): OptionState => {
    if (!answered) {
      if (question.type === 'multiple' && pending.includes(key)) {
        return 'selected'
      }
      return 'idle'
    }
    if (question.answer.includes(key)) {
      return 'correct'
    }
    if (answered.selected.includes(key)) {
      return 'wrong'
    }
    return 'muted'
  }

  return (
    <View className='quiz-page'>

      <View className='quiz-page__body'>
        <View className='quiz-nav'>
          <View className='quiz-nav__close' onClick={handleClose}>
            <Icon name='close' size={16} color='#5b6b78' />
          </View>
          <Text className='quiz-nav__counter'>
            第 {safeIndex + 1} / {total} 题
          </Text>
          <XpBadge value={totalXp} />
        </View>

        <View className='quiz-progress'>
          <View className='quiz-progress__track'>
            <View className='quiz-progress__fill' style={{ width: `${progress}%` }} />
          </View>
          <View className='quiz-progress__meta'>
            <Text>
              第 {safeIndex + 1} 题 / 共 {total} 题
            </Text>
            <Text>答对 {correctCount} 题</Text>
          </View>
        </View>

        <Text className='quiz-title'>{question.stem}</Text>

        <View className='quiz-options'>
          {question.options.map((option) => (
            <OptionCard
              key={option.key}
              option={option}
              mode={question.type === 'multiple' ? 'multi' : 'choice'}
              state={optionState(option.key)}
              disabled={Boolean(answered) || submitting}
              onTap={() => handleOptionTap(option.key)}
            />
          ))}
        </View>

        {question.type === 'multiple' && !answered ? (
          <Button className='quiz-submit' onClick={handleSubmitMultiple}>
            提交答案
          </Button>
        ) : null}

        {answered ? (
          <View className={isCorrect ? 'result-tip result-tip--correct' : 'result-tip result-tip--wrong'}>
            <View className='result-tip__left'>
              <Icon
                name={isCorrect ? 'checkCircle' : 'closeCircle'}
                size={14}
                color={isCorrect ? '#217f5b' : '#b64f40'}
              />
              <Text>{isCorrect ? '答对啦' : '答错了'}</Text>
            </View>
            <Text className='result-tip__right'>
              {isCorrect ? `+${XP_PER_CORRECT} XP` : '+0 XP'}
            </Text>
          </View>
        ) : null}

        {answered ? (
          <View className='explain-box'>
            <Text className='explain-box__label'>解析：</Text>
            <Text>{question.explanation}</Text>
          </View>
        ) : null}

        <View className='quiz-actions'>
          <Button
            className={
              safeIndex === 0
                ? 'quiz-actions__prev quiz-actions__prev--disabled'
                : 'quiz-actions__prev'
            }
            onClick={handlePrev}
          >
            上一题
          </Button>
          <Button
            className={
              !answered || submitting
                ? 'quiz-actions__next quiz-actions__next--disabled'
                : 'quiz-actions__next'
            }
            onClick={handleNext}
          >
            {isLast ? '生成报告' : '继续 →'}
          </Button>
        </View>
      </View>

      {submitting ? (
        <View className='loading-mask'>
          <View className='loading-card'>
            <View className='loading-spinner' />
            <Text className='loading-card__text'>AI 正在生成复盘报告…</Text>
          </View>
        </View>
      ) : null}
    </View>
  )
}
