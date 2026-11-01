import { Button, Input, Text, Textarea, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import EmptyState from '@/components/EmptyState'
import Icon from '@/components/Icon'
import { createKnowledgeText, deleteKnowledgeDocument } from '@/services/api'
import { uploadKnowledgeDocument } from '@/services/upload'
import { useUserStore } from '@/store/useUserStore'
import type { KnowledgeDocument, KnowledgeSourceType } from '@/types/knowledge'

import './index.scss'

const SUPPORTED_EXTENSIONS = ['pdf', 'docx', 'md', 'markdown', 'txt']

const TYPE_LABEL: Record<KnowledgeSourceType, string> = {
  pdf: 'PDF',
  docx: 'Word',
  md: 'Markdown',
  txt: '文本'
}

const isWeapp = process.env.TARO_ENV === 'weapp'

function formatSize(bytes: number): string {
  if (!bytes) {
    return '0 KB'
  }
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }
  return `${Math.max(1, Math.round(bytes / 1024))} KB`
}

export default function KnowledgePage() {
  const knowledge = useUserStore((state) => state.knowledge)
  const knowledgeEnabled = useUserStore((state) => state.knowledgeEnabled)
  const loadKnowledge = useUserStore((state) => state.loadKnowledge)
  const ensureSession = useUserStore((state) => state.ensureSession)

  const [uploading, setUploading] = useState(false)
  const [deletingId, setDeletingId] = useState('')
  const [saving, setSaving] = useState(false)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [errorMessage, setErrorMessage] = useState('')

  useDidShow(() => {
    void ensureSession()
  })

  const handlePickFile = async () => {
    if (uploading) {
      return
    }
    if (!isWeapp) {
      Taro.showToast({ title: '当前端暂不支持文件上传，可改用下方粘贴文本', icon: 'none' })
      return
    }
    try {
      const picked = await Taro.chooseMessageFile({
        count: 1,
        type: 'file',
        extension: SUPPORTED_EXTENSIONS
      })
      const file = picked.tempFiles?.[0]
      if (!file) {
        return
      }
      const lowerName = (file.name || '').toLowerCase()
      if (!SUPPORTED_EXTENSIONS.some((ext) => lowerName.endsWith(`.${ext}`))) {
        Taro.showToast({ title: '仅支持 PDF / Word / Markdown / TXT', icon: 'none' })
        return
      }

      setUploading(true)
      setErrorMessage('')
      Taro.showLoading({ title: '解析并入库…', mask: true })
      await uploadKnowledgeDocument(file.path, file.name)
      await loadKnowledge()
      Taro.hideLoading()
      Taro.showToast({ title: '已加入知识库', icon: 'success' })
    } catch (error) {
      Taro.hideLoading()
      const message = error instanceof Error ? error.message : '上传失败，请稍后重试'
      setErrorMessage(message)
      Taro.showToast({ title: message, icon: 'none' })
    } finally {
      setUploading(false)
    }
  }

  const handleSaveText = async () => {
    const trimmedTitle = title.trim()
    const trimmedContent = content.trim()
    if (saving) {
      return
    }
    if (!trimmedTitle) {
      Taro.showToast({ title: '先给这段资料起个标题', icon: 'none' })
      return
    }
    if (trimmedContent.length < 20) {
      Taro.showToast({ title: '正文太短，至少 20 个字', icon: 'none' })
      return
    }

    setSaving(true)
    setErrorMessage('')
    try {
      await createKnowledgeText({ title: trimmedTitle, content: trimmedContent })
      setTitle('')
      setContent('')
      await loadKnowledge()
      Taro.showToast({ title: '已保存到知识库', icon: 'success' })
    } catch (error) {
      const message = error instanceof Error ? error.message : '保存失败，请稍后重试'
      setErrorMessage(message)
      Taro.showToast({ title: message, icon: 'none' })
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (item: KnowledgeDocument) => {
    if (deletingId) {
      return
    }
    const confirmed = await Taro.showModal({
      title: '删除文档',
      content: `确定删除「${item.title}」吗？删除后无法恢复。`
    })
    if (!confirmed.confirm) {
      return
    }
    setDeletingId(item.doc_id)
    try {
      await deleteKnowledgeDocument(item.doc_id)
      await loadKnowledge()
      Taro.showToast({ title: '已删除', icon: 'success' })
    } catch (error) {
      const message = error instanceof Error ? error.message : '删除失败，请稍后重试'
      Taro.showToast({ title: message, icon: 'none' })
    } finally {
      setDeletingId('')
    }
  }

  return (
    <View className='knowledge-page app-page'>
      <View className='knowledge-page__body'>
        <Text className='knowledge-title'>我的知识库</Text>
        <Text className='knowledge-subtitle'>
          上传内部资料后，AI 会优先基于你的私有内容出题，不再依赖公开资料。
        </Text>

        {!knowledgeEnabled ? (
          <View className='knowledge-notice'>
            <Icon name='warning' size={14} color='#b64f40' />
            <Text className='knowledge-notice__text'>
              知识库暂未启用，请先在服务端配置百炼嵌入模型后重试。
            </Text>
          </View>
        ) : null}

        <View className='knowledge-card'>
          <Text className='knowledge-card__title'>上传文档</Text>
          <Text className='knowledge-card__desc'>
            支持 PDF / Word / Markdown / TXT，单文件不超过 10MB。
            {isWeapp ? '点击下方按钮从聊天记录中选择文件。' : '当前端请使用下方粘贴文本。'}
          </Text>
          <Button
            className={uploading ? 'knowledge-btn knowledge-btn--loading' : 'knowledge-btn'}
            disabled={uploading || !knowledgeEnabled}
            onClick={handlePickFile}
          >
            <Icon name='book' size={15} color='#ffffff' />
            <Text>{uploading ? '正在解析…' : '选择文件上传'}</Text>
          </Button>
        </View>

        <View className='knowledge-card'>
          <Text className='knowledge-card__title'>粘贴文本</Text>
          <Text className='knowledge-card__desc'>
            适合把聊天记录、内部 FAQ、考题片段直接存成资料。
          </Text>
          <Input
            className='knowledge-input'
            value={title}
            maxlength={60}
            placeholder='资料标题，例如「客服售后话术」'
            onInput={(event) => setTitle(event.detail.value)}
          />
          <Textarea
            className='knowledge-textarea'
            value={content}
            maxlength={20000}
            placeholder='把要学习的正文粘贴到这里…'
            onInput={(event) => setContent(event.detail.value)}
          />
          <Button
            className={
              saving
                ? 'knowledge-btn knowledge-btn--ghost knowledge-btn--loading'
                : 'knowledge-btn knowledge-btn--ghost'
            }
            disabled={saving || !knowledgeEnabled}
            onClick={handleSaveText}
          >
            <Icon name='edit' size={15} color='#df5f1f' />
            <Text>{saving ? '保存中…' : '保存为知识库文档'}</Text>
          </Button>
        </View>

        {errorMessage ? (
          <View className='knowledge-error'>
            <Text>{errorMessage}</Text>
          </View>
        ) : null}

        <Text className='knowledge-list__title'>已上传 {knowledge.length} 份资料</Text>

        {knowledge.map((item) => (
          <View className='knowledge-item' key={item.doc_id}>
            <View className='knowledge-item__body'>
              <Text className='knowledge-item__name'>{item.title}</Text>
              <Text className='knowledge-item__meta'>
                {TYPE_LABEL[item.source_type] ?? item.source_type} · {item.chunk_count} 段 ·{' '}
                {formatSize(item.size_bytes)}
              </Text>
            </View>
            <View className='knowledge-item__delete' onClick={() => void handleDelete(item)}>
              <Icon name='close' size={14} color='#b64f40' />
              <Text>{deletingId === item.doc_id ? '删除中' : '删除'}</Text>
            </View>
          </View>
        ))}

        {knowledge.length === 0 && knowledgeEnabled ? (
          <EmptyState
            title='知识库还是空的'
            description='上传一份内部资料，回到首页勾选它，就能生成专属闯关题。'
          />
        ) : null}
      </View>
    </View>
  )
}
