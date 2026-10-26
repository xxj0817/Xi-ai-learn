import Taro from '@tarojs/taro'

import type { ApiEnvelope } from '@/types/api'

const API_PREFIX = '/api/v1'
const MINI_PROGRAM_HOST = 'http://127.0.0.1:8000'

const BASE_URL = process.env.TARO_ENV === 'h5' ? '' : MINI_PROGRAM_HOST

export class ApiError extends Error {
  code: number

  constructor(message: string, code: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
  }
}

interface RequestOptions {
  url: string
  method?: 'GET' | 'POST'
  data?: unknown
}

export async function request<T>(options: RequestOptions): Promise<T> {
  let response: Taro.request.SuccessCallbackResult<ApiEnvelope<T>>

  try {
    response = await Taro.request<ApiEnvelope<T>>({
      url: `${BASE_URL}${API_PREFIX}${options.url}`,
      method: options.method ?? 'GET',
      data: options.data as Taro.request.Option<ApiEnvelope<T>>['data'],
      timeout: 45_000,
      header: {
        'Content-Type': 'application/json'
      }
    })
  } catch (error) {
    console.warn('request failed', error)
    throw new ApiError('网络连接失败，请确认后端服务已启动', -1)
  }

  const body = response.data
  if (!body || typeof body.code !== 'number') {
    throw new ApiError('服务返回数据异常，请稍后重试', -1)
  }
  if (body.code !== 0) {
    throw new ApiError(body.message || '请求失败，请稍后重试', body.code)
  }
  return body.data as T
}
