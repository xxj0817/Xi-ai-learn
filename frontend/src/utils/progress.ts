import type { AnswerRecordPayload } from '@/types/api'
import type { AnswerState } from '@/types/quiz'

interface ProgressRecord {
  question_id?: string
  questionId?: string
  selected?: string[]
  selected_answers?: string[]
  is_correct?: boolean
  isCorrect?: boolean
  duration_ms?: number
  durationMs?: number
}

export function toAnswerRecords(answers: Record<string, AnswerState>): AnswerRecordPayload[] {
  return Object.values(answers).map((answer) => ({
    question_id: answer.questionId,
    selected_answers: [...answer.selected],
    is_correct: answer.isCorrect,
    duration_ms: answer.durationMs
  }))
}

/** 把服务端保存的进度还原成前端作答状态，兼容历史字段命名。 */
export function fromProgressRecords(records: unknown[]): Record<string, AnswerState> {
  const restored: Record<string, AnswerState> = {}
  records.forEach((raw) => {
    const record = raw as ProgressRecord
    const questionId = record.question_id ?? record.questionId
    const selected = [...(record.selected ?? record.selected_answers ?? [])]
    if (!questionId || selected.length === 0) {
      // 早期进度缺少作答内容时视为未作答，允许重新选择
      return
    }
    restored[questionId] = {
      questionId,
      selected,
      isCorrect: Boolean(record.is_correct ?? record.isCorrect),
      durationMs: record.duration_ms ?? record.durationMs ?? 0
    }
  })
  return restored
}
