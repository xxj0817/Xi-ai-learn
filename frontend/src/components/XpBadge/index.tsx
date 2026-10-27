import { Text, View } from '@tarojs/components'

import Icon from '@/components/Icon'

import './index.scss'

interface XpBadgeProps {
  value: number | string
  showIcon?: boolean
  className?: string
}

export default function XpBadge({ value, showIcon = true, className }: XpBadgeProps) {
  return (
    <View className={className ? `xp-badge ${className}` : 'xp-badge'}>
      <Text className='xp-badge__value'>{value}</Text>
      {showIcon ? <Icon name='coin' size={18} /> : null}
    </View>
  )
}