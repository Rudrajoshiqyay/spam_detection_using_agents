import type { FraudDecision, FeedbackStats, HealthStatus, Transaction, OutcomeLabel } from '@/types'

const BASE = import.meta.env.VITE_API_URL ?? '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`)
  return res.json()
}

// Health & Status
export const apiHealth = () => get<HealthStatus>('/health')

// Detection
export const apiDetect = (transaction: Transaction, userId: string) =>
  post<{ result: FraudDecision }>('/detect', { transaction, user_id: userId })

// Profiles
export const apiProfiles = () => get<Record<string, unknown>>('/profiles')

// Feedback
export const apiFeedbackStats = () => get<FeedbackStats>('/feedback/stats')
export const apiFeedbackRecent = (limit = 20) => get<unknown[]>(`/feedback/recent?limit=${limit}`)
export const apiFeedbackSubmit = (payload: {
  transaction_id: string
  user_id: string
  system_decision: string
  system_risk_score: number
  analyst_decision: string
  outcome_label: OutcomeLabel
  notes?: string
  reviewer_id?: string
  device_id?: string
  merchant_id?: string
}) => post<{ feedback_id: string; status: string }>('/feedback/submit', payload)

// Demo scenarios
export const apiDemoScenario = (name: string) =>
  post<unknown>(`/demo/scenario/${name}`, {})

// Metrics
export const apiMetricsEval = () => get<unknown>('/metrics/evaluation')
export const apiGroundTruthStats = () => get<unknown>('/ground-truth/stats')
export const apiFraudTypePerf = () => get<unknown>('/metrics/fraud-type-performance')

// Simulation
export const apiSimulateFull = (params: unknown) =>
  post<unknown>('/simulate/full', params)
