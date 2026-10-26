export interface ApiEnvelope<T> {
  code: number
  message: string
  data: T | null
}

export interface GenerateQuizPayload {
  user_input: string
  question_count?: number
  difficulty?: 'mixed' | 'easy' | 'medium' | 'hard'
}

export interface AnswerRecordPayload {
  question_id: string
  selected_answers: string[]
  is_correct: boolean
  duration_ms: number
}

export interface GenerateReportPayload {
  quiz_id: string
  topic: string
  questions: unknown[]
  answer_records: AnswerRecordPayload[]
}
