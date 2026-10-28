-- AI 出题异步任务
-- 任务状态与结果独立存放，避免出题请求长时间占用连接
-- 注意：progress 由 stage 推导，不单独落库，保持与既有表结构兼容

CREATE TABLE IF NOT EXISTS quiz_tasks (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  task_id VARCHAR(64) NOT NULL,
  user_id BIGINT UNSIGNED NULL COMMENT '匿名任务为 NULL',
  status VARCHAR(16) NOT NULL DEFAULT 'queued' COMMENT 'pending/running/succeeded/failed',
  stage VARCHAR(32) NOT NULL DEFAULT 'queued' COMMENT 'queued/researching/generating/validating/saving/completed/failed',
  request_json JSON NOT NULL,
  result_json JSON NULL COMMENT '成功后返回给前端的完整题库',
  quiz_id VARCHAR(64) NULL,
  error_code VARCHAR(32) NULL,
  error_message VARCHAR(255) NULL,
  retryable TINYINT(1) NOT NULL DEFAULT 1,
  idempotency_key VARCHAR(160) NULL,
  expires_at DATETIME NOT NULL COMMENT '过期后可清理',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  started_at DATETIME NULL,
  finished_at DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_quiz_tasks_task_id (task_id),
  UNIQUE KEY uk_quiz_tasks_idempotency (idempotency_key),
  KEY idx_quiz_tasks_user_created (user_id, created_at),
  KEY idx_quiz_tasks_status_created (status, created_at),
  KEY idx_quiz_tasks_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 出题异步任务';

-- 兼容早期版本的 quiz_tasks（缺少过期时间列），重复执行时忽略 1060
ALTER TABLE quiz_tasks ADD COLUMN expires_at DATETIME NULL COMMENT '过期后可清理';
