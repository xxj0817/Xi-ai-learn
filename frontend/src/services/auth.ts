import Taro from '@tarojs/taro'

const TOKEN_KEY = 'xi-ai-learn-token'
const USER_KEY = 'xi-ai-learn-user'

export interface CachedUser {
  id: number
  nickname: string
  avatar_url: string
  total_xp: number
}

export function getToken(): string {
  try {
    return String(Taro.getStorageSync(TOKEN_KEY) || '')
  } catch (error) {
    console.warn('读取 token 失败', error)
    return ''
  }
}

export function setToken(token: string): void {
  try {
    Taro.setStorageSync(TOKEN_KEY, token)
  } catch (error) {
    console.warn('写入 token 失败', error)
  }
}

export function clearToken(): void {
  try {
    Taro.removeStorageSync(TOKEN_KEY)
    Taro.removeStorageSync(USER_KEY)
  } catch (error) {
    console.warn('清除 token 失败', error)
  }
}

export function getCachedUser(): CachedUser | null {
  try {
    const raw = Taro.getStorageSync(USER_KEY)
    if (!raw) {
      return null
    }
    return typeof raw === 'string' ? (JSON.parse(raw) as CachedUser) : (raw as CachedUser)
  } catch (error) {
    console.warn('读取用户缓存失败', error)
    return null
  }
}

export function setCachedUser(user: CachedUser): void {
  try {
    Taro.setStorageSync(USER_KEY, JSON.stringify(user))
  } catch (error) {
    console.warn('写入用户缓存失败', error)
  }
}

export function isLoggedIn(): boolean {
  return Boolean(getToken())
}

export function canUseWeChatLogin(): boolean {
  const env = String(
    process.env.TARO_ENV || (typeof Taro.getEnv === 'function' ? Taro.getEnv() : '')
  )
  if (env === 'h5' || env === 'WEB') {
    return false
  }
  return typeof Taro.login === 'function'
}

export function fetchWeChatCode(): Promise<string> {
  return new Promise((resolve, reject) => {
    Taro.login({
      success: (result) => {
        if (result.code) {
          resolve(result.code)
        } else {
          reject(new Error('微信登录未返回 code'))
        }
      },
      fail: (error) => reject(new Error(error?.errMsg || '微信登录失败'))
    })
  })
}
