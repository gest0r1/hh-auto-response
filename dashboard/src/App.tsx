import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Activity, Bot, BrainCircuit, BriefcaseBusiness, CheckCircle2, Clock3, Database, ExternalLink, Flame, Send, Sparkles, Target, TrendingUp } from 'lucide-react'
import type { DashboardSummary, Vacancy } from './types'

const API_URL = import.meta.env.VITE_API_URL || ''

const demoData: DashboardSummary = {
  metrics: { vacancies_total: 2, hot_total: 1, drafts_total: 2, sent_total: 0, interviews_total: 0 },
  pipeline: { draft: 2 },
  top_vacancies: [
    {
      id: 1,
      external_id: 'demo-hh-1',
      title: 'Full-stack developer для AI CRM',
      company: 'Demo Product',
      description: 'Удалённо, долгосрочный контракт. React, Python, FastAPI, Telegram, CRM, dashboard.',
      url: 'https://hh.ru',
      apply_url: 'https://hh.ru/applicant/vacancy_response?vacancyId=demo-1',
      salary_from: 220000,
      salary_to: 320000,
      currency: 'RUR',
      schedule: 'remote',
      employment: 'part',
      score: 96,
      decision: 'hot',
      status: 'hot',
      skills: ['React', 'Python', 'FastAPI', 'Telegram', 'CRM'],
      score_reasons: ['skill match: React', 'remote/удалёнка', 'salary >= target'],
      score_penalties: [],
      application_status: 'draft',
      cover_letter: 'Здравствуйте, Demo Product! Увидел вакансию — это мой профиль: React, Python, FastAPI и Telegram. Могу быстро собрать первый контур CRM и дашборд.',
    },
    {
      id: 2,
      external_id: 'demo-hh-2',
      title: 'Backend Python integrations engineer',
      company: 'OpsCloud',
      description: 'API integrations, automation, PostgreSQL. Можно удалённо.',
      url: 'https://hh.ru',
      apply_url: 'https://hh.ru/applicant/vacancy_response?vacancyId=demo-2',
      salary_from: 180000,
      salary_to: 240000,
      currency: 'RUR',
      schedule: 'remote',
      employment: 'full',
      score: 82,
      decision: 'review',
      status: 'review',
      skills: ['Python', 'API', 'PostgreSQL'],
      score_reasons: ['skill match: Python', 'preferred keyword: automation'],
      score_penalties: [],
      application_status: 'draft',
      cover_letter: 'Здравствуйте! Вижу задачу по интеграциям и автоматизации. Могу разобрать API, собрать backend-контур и вывести статусы в CRM.',
    },
  ],
  feedback_recent: [
    { id: 1, event_type: 'approved', rating: 5, notes: 'Больше акцента на CRM', vacancy_title: 'Full-stack developer для AI CRM', company: 'Demo Product', created_at: new Date().toISOString() },
  ],
  learning_signals: [
    { key: 'CRM', weight: 1.34, positive_count: 2, negative_count: 0, updated_at: new Date().toISOString() },
    { key: 'офис', weight: -0.28, positive_count: 0, negative_count: 1, updated_at: new Date().toISOString() },
  ],
}

function formatMoney(vacancy: Vacancy) {
  const from = vacancy.salary_from ? vacancy.salary_from.toLocaleString('ru-RU') : null
  const to = vacancy.salary_to ? vacancy.salary_to.toLocaleString('ru-RU') : null
  const currency = vacancy.currency === 'RUR' ? '₽' : vacancy.currency || ''
  if (from && to) return `${from}–${to} ${currency}`
  if (from) return `от ${from} ${currency}`
  if (to) return `до ${to} ${currency}`
  return 'зарплата не указана'
}

function decisionLabel(decision: string) {
  return {
    hot: 'горячая',
    review: 'проверить',
    maybe: 'сомнительно',
    archive: 'архив',
  }[decision] || decision
}

function MetricCard({ icon: Icon, label, value, detail }: { icon: typeof Activity; label: string; value: number | string; detail: string }) {
  return (
    <article className="metric-card">
      <div className="metric-icon"><Icon size={20} /></div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        <span>{detail}</span>
      </div>
    </article>
  )
}

function VacancyCard({ vacancy, index }: { vacancy: Vacancy; index: number }) {
  const reasons = vacancy.score_reasons || []
  const penalties = vacancy.score_penalties || []
  return (
    <article className={`vacancy-card decision-${vacancy.decision}`}>
      <div className="rank">#{String(index + 1).padStart(2, '0')}</div>
      <div className="vacancy-main">
        <div className="vacancy-head">
          <div>
            <div className="eyebrow">{vacancy.company}</div>
            <h3>{vacancy.title}</h3>
          </div>
          <div className="score-ring" style={{ '--score': `${vacancy.score * 3.6}deg` } as CSSProperties}>
            <span>{vacancy.score}</span>
          </div>
        </div>
        <div className="vacancy-meta">
          <span><Target size={14} /> {decisionLabel(vacancy.decision)}</span>
          <span><BriefcaseBusiness size={14} /> {formatMoney(vacancy)}</span>
          <span><Clock3 size={14} /> {vacancy.schedule || 'schedule n/a'} / {vacancy.employment || 'employment n/a'}</span>
        </div>
        <p className="description">{vacancy.description}</p>
        <div className="chips">
          {(vacancy.skills || []).slice(0, 7).map((skill) => <span key={skill}>{skill}</span>)}
        </div>
        <div className="reason-grid">
          <div>
            <b>Почему подходит</b>
            {(reasons.length ? reasons : ['скоринг ждёт данных']).slice(0, 4).map((reason) => <small key={reason}>+ {reason}</small>)}
          </div>
          <div>
            <b>Риски</b>
            {(penalties.length ? penalties : ['критичных рисков нет']).slice(0, 4).map((reason) => <small key={reason}>− {reason}</small>)}
          </div>
        </div>
        {vacancy.cover_letter && (
          <details className="draft-box">
            <summary><Sparkles size={16} /> Черновик отклика</summary>
            <p>{vacancy.cover_letter}</p>
          </details>
        )}
      </div>
      <div className="vacancy-links">
        <a className="open-link" href={vacancy.url} target="_blank" rel="noreferrer"><ExternalLink size={16} /> HH</a>
        {vacancy.apply_url && <a className="open-link apply" href={vacancy.apply_url} target="_blank" rel="noreferrer"><Send size={16} /> Отклик</a>}
      </div>
    </article>
  )
}

export function App() {
  const [data, setData] = useState<DashboardSummary>(demoData)
  const [source, setSource] = useState<'api' | 'demo'>('demo')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const pipelineTotal = useMemo(
    () => (Object.values(data.pipeline || {}) as number[]).reduce((sum, value) => sum + value, 0),
    [data.pipeline],
  )

  async function loadDashboard() {
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/api/dashboard`)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const payload = await response.json()
      setData(payload)
      setSource('api')
    } catch {
      setData(demoData)
      setSource('demo')
    } finally {
      setLoading(false)
    }
  }

  async function runAgent() {
    setRunning(true)
    try {
      await fetch(`${API_URL}/api/agent/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ queries: ['React Python CRM', 'Telegram bot Python', 'AI automation developer'], per_query: 10, draft_threshold: 80, mode: 'public' }),
      })
      await loadDashboard()
    } finally {
      setRunning(false)
    }
  }

  useEffect(() => { loadDashboard() }, [])

  return (
    <main className="app-shell">
      <div className="mesh mesh-a" />
      <div className="mesh mesh-b" />
      <section className="hero-panel">
        <nav className="topbar">
          <div className="brand"><Bot size={22} /> Headhunter CRM Agent</div>
          <div className={`source-pill ${source}`}>{source === 'api' ? 'live sqlite' : 'demo fallback'} {loading && '· sync'}</div>
        </nav>
        <div className="hero-grid">
          <div>
            <p className="eyebrow">самообучающийся контур поиска работы</p>
            <h1>CRM, агент откликов и дашборд конверсии в одном экране.</h1>
            <p className="hero-copy">Система ищет вакансии HH, считает релевантность, пишет персональные черновики, сохраняет всё в SQLite и учится на вашей реакции: approve, edit, reject, reply, interview, offer.</p>
            <div className="hero-actions">
              <button onClick={runAgent} disabled={running}>{running ? 'Агент работает…' : 'Запустить no-API поиск HH'}</button>
              <button className="ghost" onClick={loadDashboard}>Обновить CRM</button>
            </div>
          </div>
          <div className="agent-orbit" aria-label="Agent pipeline visual">
            <div className="orbit-core"><BrainCircuit size={42} /><span>learning loop</span></div>
            <div className="orbit-card o1"><Database size={16} /> SQLite CRM</div>
            <div className="orbit-card o2"><Flame size={16} /> Hot score</div>
            <div className="orbit-card o3"><Send size={16} /> Drafts</div>
            <div className="orbit-card o4"><TrendingUp size={16} /> Feedback</div>
          </div>
        </div>
      </section>

      <section className="metrics-grid">
        <MetricCard icon={Database} label="Вакансии" value={data.metrics.vacancies_total} detail="сохранено в базе" />
        <MetricCard icon={Flame} label="Горячие" value={data.metrics.hot_total} detail="score ≥ 85" />
        <MetricCard icon={Sparkles} label="Черновики" value={data.metrics.drafts_total} detail="готовы к проверке" />
        <MetricCard icon={CheckCircle2} label="Собесы" value={data.metrics.interviews_total} detail="цель воронки" />
      </section>

      <section className="workspace-grid">
        <div className="panel vacancies-panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">приоритетная лента</p>
              <h2>Лучшие вакансии и отклики</h2>
            </div>
            <span>{data.top_vacancies.length} карточек</span>
          </div>
          <div className="vacancy-list">
            {data.top_vacancies.length ? data.top_vacancies.map((vacancy, index) => <VacancyCard key={vacancy.external_id || vacancy.id} vacancy={vacancy} index={index} />) : <p className="empty">Пока нет вакансий. Запустите seed-demo или агент поиска.</p>}
          </div>
        </div>

        <aside className="side-stack">
          <div className="panel">
            <div className="panel-head compact"><h2>Воронка</h2><span>{pipelineTotal} активных</span></div>
            <div className="pipeline-list">
              {Object.entries(data.pipeline || {}).map(([status, count]) => (
                <div className="pipeline-row" key={status}>
                  <span>{status}</span>
                  <div><i style={{ width: `${Math.max(8, (count / Math.max(1, pipelineTotal)) * 100)}%` }} /></div>
                  <b>{count}</b>
                </div>
              ))}
              {!pipelineTotal && <p className="empty">Воронка пустая.</p>}
            </div>
          </div>

          <div className="panel">
            <div className="panel-head compact"><h2>Обучение</h2><BrainCircuit size={18} /></div>
            <div className="signals">
              {(data.learning_signals || []).slice(0, 8).map((signal) => (
                <div className="signal" key={signal.key}>
                  <span>{signal.key}</span>
                  <b className={signal.weight >= 1 ? 'positive' : signal.weight < 0 ? 'negative' : ''}>{signal.weight.toFixed(2)}</b>
                </div>
              ))}
              {!data.learning_signals?.length && <p className="empty">Сигналы появятся после approve/reject/edit.</p>}
            </div>
          </div>

          <div className="panel">
            <div className="panel-head compact"><h2>Последний фидбэк</h2><Activity size={18} /></div>
            <div className="feedback-list">
              {(data.feedback_recent || []).slice(0, 6).map((event) => (
                <article key={event.id}>
                  <b>{event.event_type}</b>
                  <span>{event.company || '—'} · {event.vacancy_title || 'без вакансии'}</span>
                  {event.notes && <p>{event.notes}</p>}
                </article>
              ))}
              {!data.feedback_recent?.length && <p className="empty">История реакций пока пустая.</p>}
            </div>
          </div>
        </aside>
      </section>
    </main>
  )
}
