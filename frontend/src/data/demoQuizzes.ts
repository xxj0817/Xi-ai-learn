import type { AnswerState, Question, Quiz, QuizRecord } from '@/types/quiz'

/**
 * 示例关卡：仅在「未完成关卡」区域展示，可正常打开作答。
 * 已完成关卡与 XP 一律来自服务端，不再使用本地示例数据。
 */

const MINUTE = 60_000
const HOUR = 60 * MINUTE
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

export function buildDemoRecords(): QuizRecord[] {
  const math = makeQuiz('demo_math', '数学闯关', '四则运算、几何与应用题混合练习', ['四则运算', '几何', '应用题'], MATH_QUESTIONS)
  const science = makeQuiz('demo_science', '科学闯关', '物理、化学、生物与天文常识', ['物理', '生物', '化学'], SCIENCE_QUESTIONS)

  return [
    {
      quiz: math,
      answers: partialAnswers(math, 3),
      currentIndex: 3,
      status: 'in_progress',
      createdAt: NOW - 6 * HOUR,
      updatedAt: NOW - 5 * HOUR
    },
    {
      quiz: science,
      answers: partialAnswers(science, 2),
      currentIndex: 2,
      status: 'in_progress',
      createdAt: NOW - 2 * HOUR,
      updatedAt: NOW - 90 * MINUTE
    }
  ]
}