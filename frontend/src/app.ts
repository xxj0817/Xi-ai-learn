import { PropsWithChildren } from 'react'
import { useLaunch } from '@tarojs/taro'
import { useStudyStore } from '@/store/useStudyStore'

import './app.scss'

function App({ children }: PropsWithChildren) {
  useLaunch(() => {
    const seed = () => useStudyStore.getState().seedDemoData()
    const result = useStudyStore.persist.rehydrate() as unknown
    if (result && typeof (result as Promise<void>).then === 'function') {
      ;(result as Promise<void>).then(seed, seed)
    } else {
      seed()
    }
  })

  return children
}

export default App
