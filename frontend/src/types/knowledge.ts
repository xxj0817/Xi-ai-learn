export type KnowledgeSourceType = 'pdf' | 'docx' | 'md' | 'txt'

export type KnowledgeDocumentStatus = 'ready' | 'processing' | 'failed'

export interface KnowledgeDocument {
  doc_id: string
  title: string
  source_type: KnowledgeSourceType
  size_bytes: number
  chunk_count: number
  status: KnowledgeDocumentStatus
  created_at: string
}

export interface KnowledgeDocumentList {
  items: KnowledgeDocument[]
  total: number
  enabled: boolean
}

export interface KnowledgeTextPayload {
  title: string
  content: string
}

export interface KnowledgeDeleteResult {
  doc_id: string
  deleted: boolean
}
