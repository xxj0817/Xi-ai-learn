import { request } from '@/services/request'
import type { GenerateQuizPayload, GenerateReportPayload } from '@/types/api'
import type { Quiz, Report } from '@/types/quiz'

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
