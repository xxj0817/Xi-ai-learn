import Taro from '@tarojs/taro'
import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

import { DEMO_COINS, DEMO_XP, buildDemoRecords } from '@/data/demoQuizzes'
import type { AnswerState, Quiz, QuizRecord, Report } from '@/types/quiz'

const MAX_HISTORY = 20
export const COIN_PER_CORRECT = 10
export const XP_PER_CORRECT = 10
export const XP_PER_COMPLETION = 20

const taroStorage = {
  getItem: (name: string): string | null => {
    try {
      const value = Taro.getStorageSync(name)
      return value ? String(value) : null
    } catch (error) {
      console.warn('read storage failed', error)
      return null
    }
  },
  setItem: (name: string, value: string): void => {
    try {
      Taro.setStorageSync(name, value)
    } catch (error) {
      console.warn('write storage failed', error)
    }
  },
  removeItem: (name: string): void => {
    try {
      Taro.removeStorageSync(name)
    } catch (error) {
      console.warn('remove storage failed', error)
    }
  }
}

interface StudyState {
  nickname: string
  coins: number
  xp: number
  quiz: Quiz | null
  currentIndex: number
  answers: Record<string, AnswerState>
  report: Report | null
  history: QuizRecord[]
  seeded: boolean
  seedDemoData: () => void
  startQuiz: (quiz: Quiz) => void
  submitAnswer: (answer: AnswerState) => void
  setIndex: (index: number) => void
  completeQuiz: (report: Report) => void
  openQuiz: (quizId: string) => boolean
  viewReport: (quizId: string) => boolean
  resetCurrent: () => void
  rename: (nickname: string) => void
}

export const useStudyStore = create<StudyState>()(
  persist(
    (set, get) => ({
      nickname: '小皮',
      coins: 0,
      xp: 0,
      quiz: null,
      currentIndex: 0,
      answers: {},
      report: null,
      history: [],
      seeded: false,

      seedDemoData: () =>
        set((state) => {
          if (state.seeded) {
            return {}
          }
          const hasHistory = state.history.length > 0
          return {
            seeded: true,
            coins: hasHistory ? state.coins : DEMO_COINS,
            xp: hasHistory ? state.xp : DEMO_XP,
            history: [...buildDemoRecords(), ...state.history]
          }
        }),

      startQuiz: (quiz) =>
        set((state) => {
          const existing = state.history.find((item) => item.quiz.quiz_id === quiz.quiz_id)
          const record: QuizRecord = existing
            ? { ...existing, quiz, updatedAt: Date.now() }
            : {
                quiz,
                answers: {},
                currentIndex: 0,
                status: 'in_progress',
                createdAt: Date.now(),
                updatedAt: Date.now(),
                coinsEarned: 0,
                xpEarned: 0
              }

          return {
            quiz,
            currentIndex: existing?.currentIndex ?? 0,
            answers: existing?.answers ?? {},
            report: existing?.report ?? null,
            history: [record, ...state.history.filter((item) => item.quiz.quiz_id !== quiz.quiz_id)].slice(
              0,
              MAX_HISTORY
            )
          }
        }),

      submitAnswer: (answer) =>
        set((state) => {
          if (!state.quiz || state.answers[answer.questionId]) {
            return {}
          }

          const answers = { ...state.answers, [answer.questionId]: answer }
          const gainedCoins = answer.isCorrect ? COIN_PER_CORRECT : 0
          const gainedXp = answer.isCorrect ? XP_PER_CORRECT : 0
          const quizId = state.quiz.quiz_id

          return {
            answers,
            coins: state.coins + gainedCoins,
            xp: state.xp + gainedXp,
            history: state.history.map((item) =>
              item.quiz.quiz_id === quizId
                ? {
                    ...item,
                    answers,
                    updatedAt: Date.now(),
                    coinsEarned: item.coinsEarned + gainedCoins,
                    xpEarned: item.xpEarned + gainedXp
                  }
                : item
            )
          }
        }),

      setIndex: (index) =>
        set((state) => {
          if (!state.quiz) {
            return {}
          }
          const nextIndex = Math.max(0, Math.min(index, state.quiz.questions.length - 1))
          const quizId = state.quiz.quiz_id

          return {
            currentIndex: nextIndex,
            history: state.history.map((item) =>
              item.quiz.quiz_id === quizId ? { ...item, currentIndex: nextIndex, updatedAt: Date.now() } : item
            )
          }
        }),

      completeQuiz: (report) =>
        set((state) => {
          if (!state.quiz) {
            return {}
          }
          const quizId = state.quiz.quiz_id

          return {
            report,
            xp: state.xp + XP_PER_COMPLETION,
            history: state.history.map((item) =>
              item.quiz.quiz_id === quizId
                ? {
                    ...item,
                    status: 'completed' as const,
                    report,
                    xpEarned: item.xpEarned + XP_PER_COMPLETION,
                    updatedAt: Date.now()
                  }
                : item
            )
          }
        }),

      openQuiz: (quizId) => {
        const record = get().history.find((item) => item.quiz.quiz_id === quizId)
        if (!record) {
          return false
        }
        set({
          quiz: record.quiz,
          currentIndex: record.currentIndex,
          answers: record.answers,
          report: record.report ?? null
        })
        return true
      },

      viewReport: (quizId) => {
        const record = get().history.find((item) => item.quiz.quiz_id === quizId)
        if (!record || !record.report) {
          return false
        }
        set({ quiz: record.quiz, answers: record.answers, report: record.report })
        return true
      },

      resetCurrent: () => set({ quiz: null, currentIndex: 0, answers: {}, report: null }),

      rename: (nickname) => set({ nickname: nickname.trim() || '小皮' })
    }),
    {
      name: 'xi-ai-learn-study',
      storage: createJSONStorage(() => taroStorage),
      version: 2,
      skipHydration: true
    }
  )
)
