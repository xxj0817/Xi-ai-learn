import { Button, Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useEffect, useState } from 'react'

import Icon from '@/components/Icon'
import ProgressRing from '@/components/ProgressRing'
import StatusBarSpacer from '@/components/StatusBarSpacer'
import TabBar from '@/components/TabBar'
import XpBadge from '@/components/XpBadge'
import { fetchQuizDetail } from '@/services/api'
import { useStudyStore } from '@/store/useStudyStore'
import type { Report } from '@/types/quiz'

import './index.scss'

function resolveTitle(accuracy: number): string {
  if (accuracy >= 85) {
    return '你这局学得很稳'
  }
  if (accuracy >= 60) {
    return '这局稳中有进'
  }
  return '再来一轮就熟了'
}

export default function ReportPage() {
  const storeQuiz = useStudyStore((state) => state.quiz)
  const storeReport = useStudyStore((state) => state.report)

  const quizId = Taro.getCurrentInstance().router?.params?.quiz_id ?? ''
  const [title, setTitle] = useState(storeQuiz?.title ?? '')
  const [report, setReport] = useState<Report | null>(storeReport)
  const [loading, setLoading] = useState(Boolean(quizId))
  const [failed, setFailed] = useState('')

  useEffect(() => {
    if (!quizId) {
      if (!storeQuiz || !storeReport) {
        Taro.reLaunch({ url: '/pages/index/index' })
      }
      return
    }

    let alive = true
    setLoading(true)
    fetchQuizDetail(quizId)
      .then((detail) => {
        if (!alive) {
          return
        }
        setTitle(detail.title)
        setReport(detail.report)
      })
      .catch((error) => {
        if (alive) {
          setFailed(error instanceof Error ? error.message : '报告加载失败')
        }
      })
      .finally(() => {
        if (alive) {
          setLoading(false)
        }
      })

    return () => {
      alive = false
    }
  }, [quizId, storeQuiz, storeReport])

  const handleAgain = () => {
    Taro.reLaunch({ url: '/pages/index/index' })
  }

  const handlePoster = () => {
    Taro.showToast({ title: '分享海报功能将在后续版本开放', icon: 'none' })
  }

  if (loading) {
    return (
      <View className='report-page app-page'>
        <StatusBarSpacer />
        <View className='loading-mask'>
          <View className='loading-card'>
            <View className='loading-spinner' />
            <Text className='loading-card__text'>正在加载通关报告…</Text>
          </View>
        </View>
      </View>
    )
  }

  if (failed || !report) {
    return (
      <View className='report-page app-page'>
        <StatusBarSpacer />
        <View className='report-page__body'>
          <View className='report-nav'>
            <View className='report-nav__back' onClick={handleAgain}>
              <Icon name='arrowLeft' size={16} color='#7a8996' />
            </View>
            <Text className='report-nav__label'>通关报告</Text>
          </View>
          <Text className='report-title'>{failed || '这一关还没有通关报告'}</Text>
          <View className='report-actions'>
            <Button className='report-actions__again' onClick={handleAgain}>
              回到首页
            </Button>
          </View>
        </View>
        <TabBar active='profile' />
      </View>
    )
  }

  const wrongCount = report.total - report.correct
  const weakPoints = report.weak_points
  const focusPoints = (weakPoints.length > 0 ? weakPoints : report.advice).slice(0, 2)
  const masteryDesc =
    weakPoints.length > 0
      ? `${report.mastered_points[0] ? `「${report.mastered_points[0]}」掌握不错，` : ''}${
          weakPoints[0]
        }还要多练。`
      : '本关知识点全部掌握，保持这个节奏。'

  return (
    <View className='report-page app-page'>
      <StatusBarSpacer />

      <View className='report-page__body'>
        <View className='report-nav'>
          <View className='report-nav__back' onClick={handleAgain}>
            <Icon name='arrowLeft' size={16} color='#7a8996' />
          </View>
          <Text className='report-nav__label'>通关报告</Text>
        </View>

        <View className='report-toolbar'>
          <Text className='report-toolbar__topic'>{title}</Text>
          <XpBadge value={`+${report.xp_gained ?? 0} XP`} showIcon={false} />
        </View>

        <Text className='report-title'>{resolveTitle(report.accuracy)}</Text>
        <Text className='report-subtitle'>先看结果，再看错因，最后给你下一步建议。</Text>

        <View className='report-chips'>
          <View className='report-chip report-chip--orange'>
            <Icon name='star' size={12} color='#ca6329' />
            <Text>掌握度 +1</Text>
          </View>
          <View className='report-chip report-chip--green'>
            <Icon name='trendDown' size={12} color='#2b8c69' />
            <Text>{wrongCount > 0 ? `错题 -${wrongCount}` : '全对通关'}</Text>
          </View>
        </View>

        <View className='note-card'>
          <View className='note-card__title'>
            <Icon name='clock' size={14} color='#cb6326' />
            <Text>掌握度</Text>
          </View>
          <View className='mastery'>
            <ProgressRing percent={report.accuracy} size={88} stroke={12} color='#ff7a2f'>
              <Text
                className='mastery__value'
                style={{ fontSize: `${String(report.accuracy).length >= 3 ? 19 : 22}px` }}
              >
                {report.accuracy}%
              </Text>
            </ProgressRing>
            <View className='mastery__body'>
              <Text className='mastery__desc'>{masteryDesc}</Text>
              <View className='mastery__bar'>
                <View className='mastery__bar-fill' style={{ width: `${report.accuracy}%` }} />
              </View>
            </View>
          </View>
        </View>

        <View className='note-card'>
          <View className='note-card__title'>
            <Icon name='warning' size={14} color='#cb6326' />
            <Text>{weakPoints.length > 0 ? `最该补的 ${Math.min(2, weakPoints.length)} 点` : '本关掌握情况'}</Text>
          </View>
          {focusPoints.length > 0 ? (
            focusPoints.map((point, index) => (
              <Text className='note-card__line' key={`${index}-${point}`}>
                {index + 1}. {point}
              </Text>
            ))
          ) : (
            <Text className='note-card__line'>1. 本关全部掌握，继续保持。</Text>
          )}
        </View>

        <View className='sticker'>
          <View className='note-card__title'>
            <Icon name='share' size={14} color='#cb6326' />
            <Text>分享海报</Text>
          </View>
          <View className='sticker__canvas'>
            <Text className='sticker__quote'>{report.share_quote}</Text>
            <View className='sticker__qr' />
          </View>
        </View>

        <View className='report-actions'>
          <Button className='report-actions__again' onClick={handleAgain}>
            再来一组
          </Button>
          <Button className='report-actions__poster' onClick={handlePoster}>
            生成海报
          </Button>
        </View>
      </View>

      <TabBar active='profile' />
    </View>
  )
}