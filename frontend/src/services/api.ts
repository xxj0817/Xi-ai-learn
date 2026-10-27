import { request } from '@/services/request'
import type { GenerateQuizPayload, GenerateReportPayload } from '@/types/api'
import type { Quiz, Report } from '@/types/quiz'
import type { QuizDetail, QuizHistoryPage, UserProfile } from '@/types/user'

export function generateQuiz(payload: GenerateQuizPayload): Promise<Quiz> {
  return request<Quiz>({
    url: '/quiz/generate',
    method: 'POST',
    data: payload
  })
}

export function generateReport(payload: GenerateReportPayload): Promise<Report> {
  return request<Report>({
    url: '/report/generate',
    method: 'POST',
    data: payload
  })
}

export function fetchProfile(): Promise<UserProfile> {
  return request<UserProfile>({ url: '/user/profile' })
}

export function updateNickname(nickname: string): Promise<UserProfile> {
  return request<UserProfile>({ url: '/user/profile', method: 'PUT', data: { nickname } })
}

export function fetchHistory(page = 1, pageSize = 20): Promise<QuizHistoryPage> {
  return request<QuizHistoryPage>({
    url: `/user/quizzes?page=${page}&page_size=${pageSize}`
  })
}

export function fetchQuizDetail(quizId: string): Promise<QuizDetail> {
  return request<QuizDetail>({ url: `/user/quizzes/${quizId}` })
}