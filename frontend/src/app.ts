import { PropsWithChildren } from 'react'
import { useLaunch } from '@tarojs/taro'

import { useStudyStore } from '@/store/useStudyStore'
import { useUserStore } from '@/store/useUserStore'

import './app.scss'

function App({ children }: PropsWithChildren) {
  useLaunch(() => {
    const result = useStudyStore.persist.rehydrate() as unknown
    if (result && typeof (result as Promise<void>).then === 'function') {
      void (result as Promise<void>).catch(() => undefined)
    }
    void useUserStore.getState().ensureSession()
  })

  return children
}

export default App