import { Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'

import Icon from '@/components/Icon'

import './index.scss'

export type TabKey = 'home' | 'bank' | 'profile'

interface TabItem {
  key: TabKey
  label: string
  icon: 'home' | 'book' | 'user'
  url: string
}

const TABS: TabItem[] = [
  { key: 'home', label: '闯关', icon: 'home', url: '/pages/index/index' },
  { key: 'bank', label: '题库', icon: 'book', url: '/pages/bank/index' },
  { key: 'profile', label: '我的', icon: 'user', url: '/pages/profile/index' }
]

interface TabBarProps {
  active: TabKey
}

export default function TabBar({ active }: TabBarProps) {
  const handleSwitch = (tab: TabItem) => {
    if (tab.key === active) {
      return
    }
    Taro.reLaunch({ url: tab.url })
  }

  return (
    <View className='tab-bar'>
      <View className='tab-bar__inner'>
        {TABS.map((tab) => {
          const isActive = tab.key === active
          return (
            <View
              key={tab.key}
              className={isActive ? 'tab-bar__item tab-bar__item--active' : 'tab-bar__item'}
              onClick={() => handleSwitch(tab)}
            >
              <Icon name={tab.icon} size={16} color={isActive ? '#df5f1f' : '#9b7d60'} />
              <Text className='tab-bar__label'>{tab.label}</Text>
            </View>
          )
        })}
      </View>
    </View>
  )
}
