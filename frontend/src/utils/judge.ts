import type { Question, Quiz } from '@/types/quiz'

export function isAnswerCorrect(question: Question, selected: string[]): boolean {
  const normalizedSelected = Array.from(new Set(selected.map((item) => item.toUpperCase()))).sort()
  const normalizedAnswer = Array.from(new Set(question.answer.map((item) => item.toUpperCase()))).sort()

  return (
    normalizedSelected.length === normalizedAnswer.length &&
    normalizedSelected.every((key, index) => key === normalizedAnswer[index])
  )
}

export function correctAnswerLabel(question: Question): string {
  return question.answer
    .map((key) => {
      const option = question.options.find((item) => item.key === key)
      return option ? `${key}. ${option.text}` : key
    })
    .join(' / ')
}

export function optionText(question: Question, key: string): string {
  return question.options.find((item) => item.key === key)?.text ?? key
}

export function quizKeywords(quiz: Quiz, limit = 3): string[] {
  const keywords: string[] = []
  quiz.questions.forEach((question) => {
    const point = question.knowledge_point.trim()
    if (point && !keywords.includes(point)) {
      keywords.push(point)
    }
  })
  return keywords.slice(0, limit)
}

export function answeredCount(answers: Record<string, unknown>): number {
  return Object.keys(answers).length
}
