import { Button, Text, View } from '@tarojs/components'

import Icon from '@/components/Icon'
import type { QuestionOption } from '@/types/quiz'

import './index.scss'

export type OptionState = 'idle' | 'selected' | 'correct' | 'wrong' | 'muted'

interface OptionCardProps {
  option: QuestionOption
  state: OptionState
  mode?: 'choice' | 'multi'
  onTap?: () => void
  disabled?: boolean
}

export default function OptionCard({ option, state, mode = 'choice', onTap, disabled }: OptionCardProps) {
  const className = [
    'option-card',
    `option-card--${state}`,
    mode === 'multi' ? 'option-card--multi' : '',
    disabled ? 'option-card--locked' : ''
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <Button className={className} hoverClass='option-card--pressed' onClick={disabled ? undefined : onTap}>
      {mode === 'multi' ? (
        <View className={state === 'selected' ? 'option-card__tick option-card__tick--on' : 'option-card__tick'}>
          {state === 'selected' ? <Icon name='checkBadgeOrange' size={18} /> : null}
        </View>
      ) : null}

      {state === 'correct' ? <Icon name='checkBadge' size={30} /> : null}
      {state === 'wrong' ? <Icon name='closeBadge' size={30} /> : null}

      {mode === 'multi' ? <Text className='option-card__key'>{option.key}</Text> : null}
      <Text className='option-card__text'>{option.text}</Text>
    </Button>
  )
}
