-- 题库来源与核实状态
-- 使用独立表而非修改 quiz_sessions，保证迁移脚本可重复执行。

CREATE TABLE IF NOT EXISTS quiz_grounding (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  quiz_id VARCHAR(64) NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  sources_json JSON NOT NULL,
  grounding_json JSON NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'model_only',
  provider VARCHAR(32) NOT NULL DEFAULT 'none',
  searched_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_quiz_grounding_quiz_id (quiz_id),
  KEY idx_quiz_grounding_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='题库来源与核实状态';
