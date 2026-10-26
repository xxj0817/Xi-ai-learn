import type { AnswerState, Question, Quiz, QuizRecord, Report } from '@/types/quiz'

/**
 * 示例关卡：首次进入时写入本地，让首页与 UI 原型保持一致（已完成卡片 + 未完成进度环）。
 * 数据可正常打开作答，不是纯静态占位。
 */

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
const NOW = Date.now()

function single(
  id: string,
  stem: string,
  options: [string, string, string, string],
  answerKey: string,
  explanation: string,
  knowledgePoint: string
): Question {
  return {
    id,
    type: 'single',
    stem,
    options: [
      { key: 'A', text: options[0] },
      { key: 'B', text: options[1] },
      { key: 'C', text: options[2] },
      { key: 'D', text: options[3] }
    ],
    answer: [answerKey],
    explanation,
    knowledge_point: knowledgePoint,
    difficulty: 'easy'
  }
}

function makeQuiz(
  quizId: string,
  title: string,
  summary: string,
  keywords: string[],
  questions: Question[]
): Quiz {
  return {
    quiz_id: quizId,
    title,
    summary,
    source_type: 'demo',
    user_input: keywords.join('、'),
    questions
  }
}

const RAG_QUESTIONS: Question[] = [
  single(
    'q1',
    'RAG 里的「检索」这一步，主要作用是什么？',
    ['把问题翻译成多国语言', '从外部知识库中找出与问题相关的片段', '重新训练模型全部参数', '压缩用户输入'],
    'B',
    '检索会把问题转成向量或关键词，在知识库中找出最相关的片段，再交给模型组织答案。它不会改动模型参数。',
    '检索'
  ),
  single(
    'q2',
    '向量数据库在 RAG 中承担的核心角色是？',
    ['存放模型权重', '按语义相似度召回相关片段', '负责生成最终答案', '记录用户操作日志'],
    'B',
    '向量库把文本转成向量后按相似度检索，让「质保多久」和「保修期限」这类同义表达也能匹配上。',
    '向量库'
  ),
  single(
    'q3',
    'RAG 中「生成」阶段的输入通常包括哪些内容？',
    ['只有用户问题', '用户问题 + 检索到的参考资料', '只有检索结果', '模型参数本身'],
    'B',
    '生成阶段会把检索到的片段和用户问题一起拼进提示词，让模型「开卷作答」，从而降低幻觉。',
    '生成'
  ),
  single(
    'q4',
    '关于 RAG 的说法，哪一项是正确的？',
    ['有检索就一定不会有幻觉', '知识更新只需更新知识库，无需重训模型', 'RAG 只能处理图片', 'RAG 会固定模型的知识截止时间'],
    'B',
    'RAG 的优势之一是把知识外置：换文档即可更新知识。但检索质量差时模型仍可能答错，幻觉只是降低而非消除。',
    '检索'
  ),
  single(
    'q5',
    'RAG 相比传统关键词搜索，最直观的差别是？',
    ['返回结果更少', '直接给出整合好的自然语言答案', '不需要任何索引', '只能回答英文问题'],
    'B',
    '传统搜索返回链接列表让用户自己找；RAG 会整合检索内容，直接给出自然语言答案。',
    '生成'
  )
]

const PROMPT_QUESTIONS: Question[] = [
  single(
    'q1',
    '给模型设定「角色」的主要作用是？',
    ['缩短提示词长度', '约束回答的专业视角与语气', '提升模型参数规模', '关闭模型的思考过程'],
    'B',
    '角色设定相当于给模型一个稳定的身份上下文，让输出视角和语气更符合预期，例如「你是一名教研老师」。',
    '角色'
  ),
  single(
    'q2',
    '在提示词里写「不超过 100 字」，属于哪类要素？',
    ['角色', '约束', '示例', '输出格式'],
    'B',
    '长度、语气、禁止项等都属于约束，用来收窄输出空间，减少跑题。',
    '约束'
  ),
  single(
    'q3',
    '要求模型「严格输出 JSON，不要 Markdown」，属于哪类要素？',
    ['角色', '约束', '输出格式', '上下文'],
    'C',
    '明确输出结构（JSON 字段、层级）属于输出格式约束，能让下游程序稳定解析。',
    '输出格式'
  ),
  single(
    'q4',
    '给模型一两个「输入 → 输出」示范，最直接的价值是？',
    ['减少 token 消耗', '让模型模仿期望的回答结构', '让模型记住知识', '关闭随机性'],
    'B',
    '示例（few-shot）能让模型照着样例的结构与颗粒度作答，是提升稳定性的高性价比手段。',
    '示例'
  ),
  single(
    'q5',
    '提示词过长导致模型忽略中间内容，比较合理的优化是？',
    ['继续堆叠更多要求', '把关键约束前置并分点表达', '删除所有示例', '改用更长的句子'],
    'B',
    '关键信息前置、结构化分点、精简冗余，能显著降低长提示词被忽略的概率。',
    '约束'
  )
]

const MATH_QUESTIONS: Question[] = [
  single('q1', '计算：7 × 8 = ?', ['54', '56', '58', '64'], 'B', '7 × 8 = 56，可拆成 7×8 = 7×10 − 7×2 = 70 − 14 = 56。', '四则运算'),
  single('q2', '一个长方形长 6cm、宽 4cm，面积是多少？', ['10 平方厘米', '20 平方厘米', '24 平方厘米', '28 平方厘米'], 'C', '长方形面积 = 长 × 宽 = 6 × 4 = 24 平方厘米。注意区分周长 20cm。', '几何'),
  single('q3', '小明有 15 元，买了 3 支笔，每支 2 元，还剩多少元？', ['6 元', '9 元', '11 元', '13 元'], 'B', '先算花掉 3 × 2 = 6 元，再算剩余 15 − 6 = 9 元。两步应用题先乘后减。', '应用题'),
  single('q4', '计算：1/2 + 1/4 = ?', ['2/6', '3/4', '1/6', '2/4'], 'B', '异分母相加先通分：1/2 = 2/4，2/4 + 1/4 = 3/4。', '分数'),
  single('q5', '一个数的 25% 是 12，这个数是多少？', ['24', '36', '48', '60'], 'C', '设这个数为 x，0.25x = 12，x = 12 ÷ 0.25 = 48。', '百分数')
]

const SCIENCE_QUESTIONS: Question[] = [
  single('q1', '标准大气压下，水的沸点是多少摄氏度？', ['50℃', '80℃', '100℃', '120℃'], 'C', '标准大气压（1 atm）下纯水沸点为 100℃。气压降低时沸点会下降，这是高原煮饭不易熟的原因。', '物理'),
  single('q2', '植物进行光合作用主要吸收哪种气体？', ['氧气', '氮气', '二氧化碳', '氢气'], 'C', '光合作用吸收二氧化碳并释放氧气，所以森林被称为「地球之肺」。', '生物'),
  single('q3', '水的化学式是？', ['CO₂', 'H₂O', 'O₂', 'NaCl'], 'B', '一个水分子由两个氢原子和一个氧原子构成，化学式为 H₂O。', '化学'),
  single('q4', '地球自转一周大约需要多长时间？', ['12 小时', '24 小时', '30 天', '365 天'], 'B', '地球自转一周约 24 小时，形成昼夜交替；公转一周约 365 天，形成四季。', '天文'),
  single('q5', '声音不能在哪种环境中传播？', ['空气', '水', '钢铁', '真空'], 'D', '声音是机械波，需要介质传播。真空中没有介质，所以无法传声。', '物理')
]

function allAnswers(quiz: Quiz): Record<string, AnswerState> {
  return quiz.questions.reduce<Record<string, AnswerState>>((acc, question) => {
    acc[question.id] = {
      questionId: question.id,
      selected: [...question.answer],
      isCorrect: true,
      durationMs: 2600
    }
    return acc
  }, {})
}

function partialAnswers(quiz: Quiz, answered: number): Record<string, AnswerState> {
  return quiz.questions.slice(0, answered).reduce<Record<string, AnswerState>>((acc, question, index) => {
    acc[question.id] = {
      questionId: question.id,
      selected: [...question.answer],
      isCorrect: true,
      durationMs: 2400 + index * 300
    }
    return acc
  }, {})
}

function demoReport(quiz: Quiz, accuracy: number): Report {
  return {
    accuracy,
    total: quiz.questions.length,
    correct: Math.round((accuracy / 100) * quiz.questions.length),
    mastered_points: quiz.questions.slice(0, 3).map((question) => question.knowledge_point),
    weak_points: [],
    three_line_summary: [
      `${quiz.title} 的核心概念已经掌握，能说清各环节的作用。`,
      '遇到同类题时，先判断它考的是哪一步，再选答案。',
      '想更稳，可以试着把这一关讲给同学听一遍。'
    ],
    advice: ['把关键概念用自己的话复述一遍，确认不是背下来的。', '隔天再刷一次同类题目，检验长期记忆。'],
    share_quote: '把知识做成关卡，记忆会更深。'
  }
}

export function buildDemoRecords(): QuizRecord[] {
  const rag = makeQuiz(
    'demo_rag_basics',
    'RAG 基础概念',
    '围绕检索、向量库与生成三个环节的入门题库',
    ['检索', '向量库', '生成'],
    RAG_QUESTIONS
  )
  const prompt = makeQuiz(
    'demo_prompt_engineering',
    '提示词工程',
    '围绕角色、约束与输出格式的实战题库',
    ['角色', '约束', '输出格式'],
    PROMPT_QUESTIONS
  )
  const math = makeQuiz('demo_math', '数学闯关', '四则运算、几何与应用题混合练习', ['四则运算', '几何', '应用题'], MATH_QUESTIONS)
  const science = makeQuiz('demo_science', '科学闯关', '物理、化学、生物与天文常识', ['物理', '生物', '化学'], SCIENCE_QUESTIONS)

  return [
    {
      quiz: rag,
      answers: allAnswers(rag),
      currentIndex: rag.questions.length - 1,
      status: 'completed',
      createdAt: NOW - 3 * DAY,
      updatedAt: NOW - 3 * DAY,
      coinsEarned: 50,
      xpEarned: 70,
      report: demoReport(rag, 100)
    },
    {
      quiz: prompt,
      answers: allAnswers(prompt),
      currentIndex: prompt.questions.length - 1,
      status: 'completed',
      createdAt: NOW - 2 * DAY,
      updatedAt: NOW - 2 * DAY,
      coinsEarned: 50,
      xpEarned: 70,
      report: demoReport(prompt, 100)
    },
    {
      quiz: math,
      answers: partialAnswers(math, 3),
      currentIndex: 3,
      status: 'in_progress',
      createdAt: NOW - 6 * HOUR,
      updatedAt: NOW - 5 * HOUR,
      coinsEarned: 30,
      xpEarned: 30
    },
    {
      quiz: science,
      answers: partialAnswers(science, 2),
      currentIndex: 2,
      status: 'in_progress',
      createdAt: NOW - 2 * HOUR,
      updatedAt: NOW - 90 * MINUTE,
      coinsEarned: 20,
      xpEarned: 20
    }
  ]
}

export const DEMO_COINS = 602
export const DEMO_XP = 240
