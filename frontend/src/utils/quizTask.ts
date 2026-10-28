import Taro from '@tarojs/taro'

import { fetchQuizTask } from '@/services/api'
import { ApiError } from '@/services/request'
import type { QuizTask } from '@/types/quiz'

const STORAGE_KEY = 'xi-ai-learn-quiz-task'
const DEFAULT_POLL_INTERVAL_MS = 2000
const DEFAULT_TIMEOUT_MS = 10 * 60 * 1000

export class QuizTaskCancelledError extends Error {
  constructor() {
    super('已取消生成')
    this.name = 'QuizTaskCancelledError'
  }
}

export interface WaitQuizTaskOptions {
  onUpdate?: (task: QuizTask) => void
  shouldContinue?: () => boolean
  pollIntervalMs?: number
  timeoutMs?: number
  sleep?: (ms: number) => Promise<void>
}

export interface StoredQuizTask {
  task_id: string
  input: string
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

/**
 * 轮询任务直到完成：成功返回带题库的任务，失败抛出 ApiError。
 */
export async function waitForQuizTask(
  taskId: string,
  options: WaitQuizTaskOptions = {}
): Promise<QuizTask> {
  const {
    onUpdate,
    shouldContinue,
    pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    sleep = wait
  } = options
  const startedAt = Date.now()
  let consecutiveFailures = 0

  for (;;) {
    if (shouldContinue && !shouldContinue()) {
      throw new QuizTaskCancelledError()
    }

    let task: QuizTask
    try {
      task = await fetchQuizTask(taskId)
      consecutiveFailures = 0
    } catch (error) {
      // 网络抖动时任务仍在后台执行，容忍少量失败后再报错
      if (
        error instanceof ApiError &&
        error.code === -1 &&
        consecutiveFailures < 2 &&
        Date.now() - startedAt < timeoutMs
      ) {
        consecutiveFailures += 1
        await sleep(pollIntervalMs)
        continue
      }
      throw error
    }

    onUpdate?.(task)

    if (task.status === 'succeeded') {
      if (!task.quiz) {
        throw new ApiError('任务已完成但题库数据缺失，请重新生成', -1)
      }
      return task
    }
    if (task.status === 'failed') {
      throw new ApiError(
        task.error?.message || 'AI 出题失败，请稍后重试',
        task.error?.code ?? -1
      )
    }
    if (Date.now() - startedAt >= timeoutMs) {
      throw new ApiError('生成时间较长，请稍后重新查看', -1)
    }

    await sleep(Math.max(500, task.poll_interval_ms || pollIntervalMs))
  }
}

export function rememberQuizTask(task: StoredQuizTask): void {
  try {
    Taro.setStorageSync(STORAGE_KEY, task)
  } catch (error) {
    console.warn('remember quiz task failed', error)
  }
}

export function recallQuizTask(): StoredQuizTask | null {
  try {
    const value = Taro.getStorageSync(STORAGE_KEY)
    if (!value || typeof value !== 'object') {
      return null
    }
    const stored = value as Partial<StoredQuizTask>
    const taskId = String(stored.task_id || '')
    if (!taskId) {
      return null
    }
    return { task_id: taskId, input: String(stored.input || '') }
  } catch (error) {
    console.warn('recall quiz task failed', error)
    return null
  }
}

export function forgetQuizTask(): void {
  try {
    Taro.removeStorageSync(STORAGE_KEY)
  } catch (error) {
    console.warn('forget quiz task failed', error)
  }
}
