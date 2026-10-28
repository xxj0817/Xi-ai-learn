import { request } from '@/services/request'
import type { AnswerRecordPayload, GenerateQuizPayload, GenerateReportPayload } from '@/types/api'
import type { Quiz, Report } from '@/types/quiz'
import type {
  InProgressQuizList,
  QuizDetail,
  QuizHistoryPage,
  UserProfile
} from '@/types/user'

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

export function fetchInProgress(): Promise<InProgressQuizList> {
  return request<InProgressQuizList>({ url: '/user/quizzes/in-progress' })
}

export function saveQuizProgress(
  quizId: string,
  records: AnswerRecordPayload[]
): Promise<{ quiz_id: string; answered_count: number }> {
  return request<{ quiz_id: string; answered_count: number }>({
    url: `/user/quizzes/${quizId}/progress`,
    method: 'PUT',
    data: { records }
  })
}

export function uploadAvatar(
  data: string,
  contentType: string
): Promise<UserProfile> {
  return request<UserProfile>({
    url: '/user/avatar',
    method: 'POST',
    data: { data, content_type: contentType }
  })
}