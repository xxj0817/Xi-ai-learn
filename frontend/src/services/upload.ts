import Taro from '@tarojs/taro'

import { ApiError, apiUrl, currentAuthHeader } from '@/services/request'
import type { ApiEnvelope } from '@/types/api'
import type { KnowledgeDocument } from '@/types/knowledge'

const UPLOAD_TIMEOUT_MS = 120_000

/**
 * 小程序端通过 chooseMessageFile 拿到临时文件后走 multipart 上传。
 */
export async function uploadKnowledgeDocument(
  filePath: string,
  fileName: string
): Promise<KnowledgeDocument> {
  const response = await Taro.uploadFile({
    url: apiUrl('/knowledge/documents'),
    filePath,
    name: 'file',
    header: currentAuthHeader(),
    timeout: UPLOAD_TIMEOUT_MS
  })

  const raw = typeof response.data === 'string' ? response.data : ''
  let body: ApiEnvelope<KnowledgeDocument> | null = null
  try {
    body = JSON.parse(raw) as ApiEnvelope<KnowledgeDocument>
  } catch (error) {
    console.warn('上传响应解析失败', error, fileName)
  }

  if (!body || typeof body.code !== 'number') {
    throw new ApiError('上传失败，请确认后端服务已启动', -1)
  }
  if (body.code !== 0) {
    throw new ApiError(body.message || '上传失败，请稍后重试', body.code)
  }
  return body.data as KnowledgeDocument
}
