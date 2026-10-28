import { fetchQuizDetail } from '@/services/api'
import { useStudyStore } from '@/store/useStudyStore'
import type { AnswerState, Quiz } from '@/types/quiz'
import type { QuizDetail } from '@/types/user'
import { fromProgressRecords } from '@/utils/progress'

export function quizFromDetail(detail: QuizDetail): {
  quiz: Quiz
  answers: Record<string, AnswerState>
} {
  return {
    quiz: {
      quiz_id: detail.quiz_id,
      title: detail.title,
      summary: detail.summary,
      source_type: 'resume',
      user_input: detail.user_input,
      questions: detail.questions
    },
    answers: fromProgressRecords(detail.progress)
  }
}

/** 拉取服务端保存的答题进度并恢复到答题页。 */
export async function resumeQuizById(quizId: string): Promise<void> {
  const detail = await fetchQuizDetail(quizId)
  const restored = quizFromDetail(detail)
  const answered = Object.keys(restored.answers).length
  const total = restored.quiz.questions.length
  // 回到第一道未作答的题，全部答完则停在最后一题
  const index = Math.min(answered, Math.max(0, total - 1))
  useStudyStore.getState().resumeQuiz(restored.quiz, restored.answers, index)
}