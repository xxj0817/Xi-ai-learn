import { Image } from '@tarojs/components'
import Taro from '@tarojs/taro'

import { iconSvg, type IconName } from '@/utils/icons'
import { svgToDataUri } from '@/utils/svg'

import './index.scss'

interface IconProps {
  name: IconName
  size?: number
  color?: string
  className?: string
}

export default function Icon({ name, size = 16, color = '#cb6326', className }: IconProps) {
  return (
    <Image
      className={className ? `app-icon ${className}` : 'app-icon'}
      src={svgToDataUri(iconSvg(name, color))}
      style={{ width: Taro.pxTransform(size), height: Taro.pxTransform(size) }}
      mode='aspectFit'
    />
  )
}
