import Taro from '@tarojs/taro'
import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

import type { AnswerState, Quiz, Report } from '@/types/quiz'

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
  startQuiz: (quiz: Quiz) => void
  resumeQuiz: (quiz: Quiz, answers: Record<string, AnswerState>, index?: number) => void
  submitAnswer: (answer: AnswerState) => void
  setIndex: (index: number) => void
  completeQuiz: (report: Report) => void
  resetCurrent: () => void
}

export const useStudyStore = create<StudyState>()(
  persist(
    (set, get) => ({
      quiz: null,
      currentIndex: 0,
      answers: {},
      report: null,

      startQuiz: (quiz) => {
        const same = get().quiz?.quiz_id === quiz.quiz_id
        set({
          quiz,
          currentIndex: same ? get().currentIndex : 0,
          answers: same ? get().answers : {},
          report: null
        })
      },

      resumeQuiz: (quiz, answers, index = 0) =>
        set({
          quiz,
          answers,
          currentIndex: Math.max(0, Math.min(index, quiz.questions.length - 1)),
          report: null
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

      completeQuiz: (report) => set({ report }),

      resetCurrent: () => set({ quiz: null, currentIndex: 0, answers: {}, report: null })
    }),
    {
      name: 'xi-ai-learn-study',
      storage: createJSONStorage(() => taroStorage),
      version: 4,
      skipHydration: true,
      partialize: (state) => ({
        quiz: state.quiz,
        currentIndex: state.currentIndex,
        answers: state.answers,
        report: state.report
      })
    }
  )
)