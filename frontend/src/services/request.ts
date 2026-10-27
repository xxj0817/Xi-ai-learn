import Taro from '@tarojs/taro'

import {
  canUseWeChatLogin,
  fetchWeChatCode,
  getToken,
  setCachedUser,
  setToken
} from '@/services/auth'
import type { ApiEnvelope } from '@/types/api'
import type { LoginResponse } from '@/types/user'

const API_PREFIX = '/api/v1'
const MINI_PROGRAM_HOST = 'http://127.0.0.1:8000'
const BASE_URL = process.env.TARO_ENV === 'h5' ? '' : MINI_PROGRAM_HOST

const UNAUTHORIZED = 4010

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
  method?: 'GET' | 'POST' | 'PUT'
  data?: unknown
  auth?: boolean
}

let loginTask: Promise<LoginResponse> | null = null

async function send<T>(options: RequestOptions, token: string): Promise<ApiEnvelope<T>> {
  const header: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) {
    header.Authorization = `Bearer ${token}`
  }

  const response = await Taro.request<ApiEnvelope<T>>({
    url: `${BASE_URL}${API_PREFIX}${options.url}`,
    method: options.method ?? 'GET',
    data: options.data as Taro.request.Option<ApiEnvelope<T>>['data'],
    timeout: 45_000,
    header
  })

  const body = response.data
  if (!body || typeof body.code !== 'number') {
    throw new ApiError('服务返回数据异常，请稍后重试', -1)
  }
  return body
}

export function loginWithWeChat(): Promise<LoginResponse> {
  if (loginTask) {
    return loginTask
  }

  const task = (async () => {
    const code = await fetchWeChatCode()
    const body = await send<LoginResponse>({ url: '/user/login', method: 'POST', data: { code } }, '')
    if (body.code !== 0) {
      throw new ApiError(body.message || '登录失败', body.code)
    }
    const payload = body.data as LoginResponse
    setToken(payload.token)
    setCachedUser(payload.user)
    return payload
  })()

  loginTask = task
  task
    .catch(() => undefined)
    .then(() => {
      loginTask = null
    })

  return task
}

/**
 * token 失效时静默重登一次；无法登录时返回 false，由调用方降级为匿名。
 */
async function reLogin(): Promise<boolean> {
  if (!canUseWeChatLogin()) {
    return false
  }
  try {
    await loginWithWeChat()
    return true
  } catch (error) {
    console.warn('静默重登失败', error)
    return false
  }
}

export async function request<T>(options: RequestOptions): Promise<T> {
  let body: ApiEnvelope<T>

  try {
    body = await send<T>(options, getToken())
    if (body.code === UNAUTHORIZED && options.auth !== false && (await reLogin())) {
      body = await send<T>(options, getToken())
    }
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }
    console.warn('request failed', error)
    throw new ApiError('网络连接失败，请确认后端服务已启动', -1)
  }

  if (body.code !== 0) {
    throw new ApiError(body.message || '请求失败，请稍后重试', body.code)
  }
  return body.data as T
}