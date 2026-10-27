import Taro from '@tarojs/taro'
import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

import { buildDemoRecords } from '@/data/demoQuizzes'
import type { AnswerState, Quiz, QuizRecord, Report } from '@/types/quiz'

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
  quiz: Quiz | null
  currentIndex: number
  answers: Record<string, AnswerState>
  report: Report | null
  demoRecords: QuizRecord[]
  seeded: boolean
  seedDemoData: () => void
  startQuiz: (quiz: Quiz) => void
  submitAnswer: (answer: AnswerState) => void
  setIndex: (index: number) => void
  completeQuiz: (report: Report) => void
  openQuiz: (quizId: string) => boolean
  resetCurrent: () => void
}

export const useStudyStore = create<StudyState>()(
  persist(
    (set, get) => ({
      quiz: null,
      currentIndex: 0,
      answers: {},
      report: null,
      demoRecords: [],
      seeded: false,

      seedDemoData: () =>
        set((state) => (state.seeded ? {} : { seeded: true, demoRecords: buildDemoRecords() })),

      startQuiz: (quiz) =>
        set((state) => {
          const existing = state.demoRecords.find((item) => item.quiz.quiz_id === quiz.quiz_id)
          const record: QuizRecord = existing
            ? { ...existing, quiz, updatedAt: Date.now() }
            : {
                quiz,
                answers: {},
                currentIndex: 0,
                status: 'in_progress',
                createdAt: Date.now(),
                updatedAt: Date.now()
              }

          return {
            quiz,
            currentIndex: existing?.currentIndex ?? 0,
            answers: existing?.answers ?? {},
            report: null,
            demoRecords: state.demoRecords.some((item) => item.quiz.quiz_id === quiz.quiz_id)
              ? state.demoRecords.map((item) => (item.quiz.quiz_id === quiz.quiz_id ? record : item))
              : [record, ...state.demoRecords]
          }
        }),

      submitAnswer: (answer) =>
        set((state) => {
          if (!state.quiz || state.answers[answer.questionId]) {
            return {}
          }
          return { answers: { ...state.answers, [answer.questionId]: answer } }
        }),

      setIndex: (index) =>
        set((state) => {
          if (!state.quiz) {
            return {}
          }
          return { currentIndex: Math.max(0, Math.min(index, state.quiz.questions.length - 1)) }
        }),

      completeQuiz: (report) =>
        set((state) => {
          if (!state.quiz) {
            return {}
          }
          const quizId = state.quiz.quiz_id
          return {
            report,
            demoRecords: state.demoRecords.map((item) =>
              item.quiz.quiz_id === quizId
                ? { ...item, answers: state.answers, status: 'completed' as const, report, updatedAt: Date.now() }
                : item
            )
          }
        }),

      openQuiz: (quizId) => {
        const state = get()
        const record = state.demoRecords.find((item) => item.quiz.quiz_id === quizId)
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

      resetCurrent: () => set({ quiz: null, currentIndex: 0, answers: {}, report: null })
    }),
    {
      name: 'xi-ai-learn-study',
      storage: createJSONStorage(() => taroStorage),
      version: 3,
      skipHydration: true,
      partialize: (state) => ({
        demoRecords: state.demoRecords,
        seeded: state.seeded,
        quiz: state.quiz,
        currentIndex: state.currentIndex,
        answers: state.answers,
        report: state.report
      })
    }
  )
)