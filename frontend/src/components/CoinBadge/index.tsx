import { Text, View } from '@tarojs/components'

import Icon from '@/components/Icon'

import './index.scss'

interface CoinBadgeProps {
  value: number | string
  showIcon?: boolean
  className?: string
}

export default function CoinBadge({ value, showIcon = true, className }: CoinBadgeProps) {
  return (
    <View className={className ? `coin-badge ${className}` : 'coin-badge'}>
      <Text className='coin-badge__value'>{value}</Text>
      {showIcon ? <Icon name='coin' size={18} /> : null}
    </View>
  )
}
