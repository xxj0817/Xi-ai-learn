-- 答题进度：保存未完成关卡的已答题目，支持跨设备续答。
-- 使用独立表而非修改 quiz_sessions，保证迁移脚本可重复执行。

CREATE TABLE IF NOT EXISTS quiz_progress (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  quiz_id VARCHAR(64) NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  records_json JSON NOT NULL,
  answered_count INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_quiz_progress_quiz_id (quiz_id),
  KEY idx_quiz_progress_user_updated (user_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='闯关答题进度';
