import { create } from 'zustand'

import { fetchHistory, fetchProfile, updateNickname } from '@/services/api'
import { getCachedUser, isLoggedIn, setCachedUser } from '@/services/auth'
import { loginWithWeChat } from '@/services/request'
import type { QuizHistoryItem, UserProfile } from '@/types/user'

const PAGE_SIZE = 20

interface UserState {
  loggedIn: boolean
  profile: UserProfile | null
  history: QuizHistoryItem[]
  historyTotal: number
  historyPage: number
  loading: boolean
  historyLoading: boolean
  error: string
  login: () => Promise<boolean>
  ensureSession: () => Promise<void>
  loadProfile: () => Promise<void>
  loadHistory: (page?: number, append?: boolean) => Promise<void>
  rename: (nickname: string) => Promise<boolean>
  reset: () => void
}

const cachedUser = getCachedUser()
let lastLoginFailAt = 0
const LOGIN_RETRY_INTERVAL = 30_000

export const useUserStore = create<UserState>()((set, get) => ({
  loggedIn: isLoggedIn(),
  profile: cachedUser
    ? {
        id: cachedUser.id,
        nickname: cachedUser.nickname,
        avatar_url: cachedUser.avatar_url,
        total_xp: cachedUser.total_xp,
        quiz_count: 0,
        correct_count: 0,
        average_accuracy: 0
      }
    : null,
  history: [],
  historyTotal: 0,
  historyPage: 1,
  loading: false,
  historyLoading: false,
  error: '',

  login: async () => {
    if (Date.now() - lastLoginFailAt < LOGIN_RETRY_INTERVAL) {
      return false
    }
    try {
      const payload = await loginWithWeChat()
      set((state) => ({
        loggedIn: true,
        error: '',
        profile: state.profile
          ? { ...state.profile, ...payload.user, quiz_count: state.profile.quiz_count }
          : {
              ...payload.user,
              quiz_count: 0,
              correct_count: 0,
              average_accuracy: 0
            }
      }))
      return true
    } catch (error) {
      const message = error instanceof Error ? error.message : '登录失败'
      console.warn('登录失败', error)
      lastLoginFailAt = Date.now()
      set({ loggedIn: false, error: message })
      return false
    }
  },

  ensureSession: async () => {
    if (!get().loggedIn) {
      const ok = await get().login()
      if (!ok) {
        return
      }
    }
    await get().loadProfile()
    await get().loadHistory(1)
  },

  loadProfile: async () => {
    if (!get().loggedIn) {
      return
    }
    set({ loading: true })
    try {
      const profile = await fetchProfile()
      setCachedUser({
        id: profile.id,
        nickname: profile.nickname,
        avatar_url: profile.avatar_url,
        total_xp: profile.total_xp
      })
      set({ profile, loading: false, error: '' })
    } catch (error) {
      const message = error instanceof Error ? error.message : '加载档案失败'
      console.warn('加载档案失败', error)
      set({ loading: false, error: message })
    }
  },

  loadHistory: async (page = 1, append = false) => {
    if (!get().loggedIn) {
      return
    }
    set({ historyLoading: true })
    try {
      const result = await fetchHistory(page, PAGE_SIZE)
      set((state) => ({
        history: append ? [...state.history, ...result.items] : result.items,
        historyTotal: result.total,
        historyPage: result.page,
        historyLoading: false
      }))
    } catch (error) {
      console.warn('加载历史失败', error)
      set({ historyLoading: false })
    }
  },

  rename: async (nickname) => {
    const trimmed = nickname.trim()
    if (!trimmed) {
      return false
    }
    try {
      const profile = await updateNickname(trimmed)
      setCachedUser({
        id: profile.id,
        nickname: profile.nickname,
        avatar_url: profile.avatar_url,
        total_xp: profile.total_xp
      })
      set({ profile, error: '' })
      return true
    } catch (error) {
      const message = error instanceof Error ? error.message : '修改昵称失败'
      console.warn('修改昵称失败', error)
      set({ error: message })
      return false
    }
  },

  reset: () =>
    set({
      loggedIn: false,
      profile: null,
      history: [],
      historyTotal: 0,
      historyPage: 1,
      error: ''
    })
}))