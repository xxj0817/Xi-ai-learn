import type { AnswerState, Question, Report } from './quiz'

export interface UserPublic {
  id: number
  nickname: string
  avatar_url: string
  total_xp: number
}

export interface LoginResponse {
  token: string
  user: UserPublic
}

export interface UserProfile {
  id: number
  nickname: string
  avatar_url: string
  total_xp: number
  quiz_count: number
  correct_count: number
  average_accuracy: number
}

export interface QuizHistoryItem {
  quiz_id: string
  title: string
  accuracy: number
  question_count: number
  created_at: string
}

export interface QuizHistoryPage {
  items: QuizHistoryItem[]
  total: number
  page: number
  page_size: number
}

export interface InProgressQuizItem {
  quiz_id: string
  title: string
  question_count: number
  answered_count: number
  updated_at: string
}

export interface InProgressQuizList {
  items: InProgressQuizItem[]
}

export interface QuizDetail {
  quiz_id: string
  title: string
  summary: string
  user_input: string
  questions: Question[]
  answer_records: AnswerState[] | unknown[]
  progress: AnswerState[] | unknown[]
  status: 'completed' | 'in_progress'
  report: Report | null
  created_at: string
}