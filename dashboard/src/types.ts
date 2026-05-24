export type Metrics = {
  vacancies_total: number
  hot_total: number
  drafts_total: number
  sent_total: number
  interviews_total: number
}

export type Vacancy = {
  id: number
  external_id: string
  title: string
  company: string
  description: string
  url: string
  apply_url?: string | null
  salary_from?: number | null
  salary_to?: number | null
  currency?: string | null
  schedule?: string | null
  employment?: string | null
  score: number
  decision: 'hot' | 'review' | 'maybe' | 'archive' | string
  status: string
  skills?: string[]
  score_reasons?: string[]
  score_penalties?: string[]
  application_status?: string | null
  cover_letter?: string | null
}

export type FeedbackEvent = {
  id: number
  event_type: string
  rating?: number | null
  notes?: string | null
  vacancy_title?: string | null
  company?: string | null
  created_at: string
}

export type LearningSignal = {
  key: string
  weight: number
  positive_count: number
  negative_count: number
  updated_at: string
}

export type DashboardSummary = {
  metrics: Metrics
  pipeline: Record<string, number>
  top_vacancies: Vacancy[]
  feedback_recent: FeedbackEvent[]
  learning_signals: LearningSignal[]
}
