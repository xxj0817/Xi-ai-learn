import { Text, View } from '@tarojs/components'

import './index.scss'

interface EmptyStateProps {
  title: string
  description: string
  actionText?: string
  onAction?: () => void
  compact?: boolean
}

export default function EmptyState({ title, description, actionText, onAction, compact }: EmptyStateProps) {
  return (
    <View className={compact ? 'empty-state empty-state--compact' : 'empty-state'}>
      <Text className='empty-state__title'>{title}</Text>
      <Text className='empty-state__desc'>{description}</Text>
      {actionText ? (
        <View className='empty-state__action' onClick={onAction}>
          <Text>{actionText}</Text>
        </View>
      ) : null}
    </View>
  )
}
