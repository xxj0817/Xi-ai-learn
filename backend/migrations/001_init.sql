-- 用户系统初始化表结构
-- 说明：题目/答题记录/报告保存完整 JSON，核心统计字段冗余存储便于列表与聚合查询。

CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  openid VARCHAR(64) NOT NULL COMMENT '微信 openid',
  nickname VARCHAR(100) NOT NULL DEFAULT '学习者',
  avatar_url VARCHAR(500) NOT NULL DEFAULT '',
  total_xp INT NOT NULL DEFAULT 0 COMMENT '累计经验值',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_users_openid (openid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户';

CREATE TABLE IF NOT EXISTS quiz_sessions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  quiz_id VARCHAR(64) NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  title VARCHAR(255) NOT NULL DEFAULT '',
  summary TEXT,
  user_input TEXT,
  questions_json JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_quiz_sessions_quiz_id (quiz_id),
  KEY idx_quiz_sessions_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='闯关题库';

CREATE TABLE IF NOT EXISTS answer_records (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  quiz_id VARCHAR(64) NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  records_json JSON NOT NULL,
  total_questions INT NOT NULL DEFAULT 0,
  correct_count INT NOT NULL DEFAULT 0,
  accuracy DECIMAL(5,2) NOT NULL DEFAULT 0.00,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_answer_records_quiz_id (quiz_id),
  KEY idx_answer_records_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='答题记录';

CREATE TABLE IF NOT EXISTS reports (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  quiz_id VARCHAR(64) NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  report_json JSON NOT NULL,
  xp_gained INT NOT NULL DEFAULT 0 COMMENT '本次获得经验值',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_reports_quiz_id (quiz_id),
  KEY idx_reports_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='复盘报告';
