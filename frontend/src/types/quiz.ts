export type QuestionType = 'single' | 'multiple' | 'judge'

export type Difficulty = 'easy' | 'medium' | 'hard'

export interface QuestionOption {
  key: string
  text: string
}

export interface Question {
  id: string
  type: QuestionType
  stem: string
  options: QuestionOption[]
  answer: string[]
  explanation: string
  knowledge_point: string
  difficulty: Difficulty
}

export interface Quiz {
  quiz_id: string
  title: string
  summary: string
  source_type: string
  user_input: string
  questions: Question[]
}

export type QuizTaskStatus = 'pending' | 'running' | 'succeeded' | 'failed'

export type QuizTaskStage =
  | 'queued'
  | 'researching'
  | 'generating'
  | 'validating'
  | 'saving'
  | 'completed'
  | 'failed'

export interface QuizTaskError {
  code: number
  message: string
}

export interface QuizTask {
  task_id: string
  status: QuizTaskStatus
  stage: QuizTaskStage
  progress: number
  quiz_id: string | null
  quiz: Quiz | null
  error: QuizTaskError | null
  poll_interval_ms: number
  created_at: string
  updated_at: string
}

export interface AnswerState {
  questionId: string
  selected: string[]
  isCorrect: boolean
  durationMs: number
}

export interface Report {
  accuracy: number
  total: number
  correct: number
  mastered_points: string[]
  weak_points: string[]
  three_line_summary: string[]
  advice: string[]
  share_quote: string
  xp_gained?: number
}

export interface QuizRecord {
  quiz: Quiz
  answers: Record<string, AnswerState>
  currentIndex: number
  status: 'in_progress' | 'completed'
  createdAt: number
  updatedAt: number
  report?: Report
}
