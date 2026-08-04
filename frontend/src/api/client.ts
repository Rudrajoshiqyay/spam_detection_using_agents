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
export const apiDetect = async (transaction: Transaction, userId: string) => {
  const data = await post<{ result: any }>('/detect', { transaction, user_id: userId });
  const backend = data.result;
  
  // Map backend's 'BLOCKED'/'APPROVED' etc to frontend's 'block'/'approve'
  let mappedDecision: import('@/types').DecisionType = 'approve';
  const fd = backend.final_decision?.toLowerCase() || '';
  if (fd === 'blocked') mappedDecision = 'block';
  else if (fd === 'monitoring' || fd === 'escalated' || fd === 'step_up_auth' || fd === 'temporary_hold') mappedDecision = 'review';
  else if (fd === 'approved') mappedDecision = 'approve';

  const riskScore = backend.consensus?.risk_score ?? backend.pre_risk_score ?? 0;
  let riskLevel: import('@/types').RiskLevel = 'minimal';
  if (riskScore >= 80) riskLevel = 'critical';
  else if (riskScore >= 60) riskLevel = 'high';
  else if (riskScore >= 40) riskLevel = 'medium';
  else if (riskScore >= 20) riskLevel = 'low';

  const mappedResult: FraudDecision = {
    transaction_id: backend.transaction_id || transaction.transaction_id,
    user_id: backend.user_id || userId,
    decision: mappedDecision,
    risk_score: riskScore,
    risk_level: riskLevel,
    confidence: backend.consensus?.confidence_score ? backend.consensus.confidence_score / 100 : 0.8,
    pre_risk_score: backend.pre_risk_score ?? 0,
    should_investigate: backend.routed_to_deep_investigation ?? false,
    screening_flags: [],
    agent_risks: backend.consensus?.agent_risks || [],
    consensus_score: backend.consensus?.agreement_score ?? 0,
    weighted_risk: riskScore,
    positive_signals: [],
    negative_signals: backend.explainability?.contributing_factors || [],
    explanation: backend.explainability?.human_explanation || backend.explainability?.evidence_summary || '',
    counterfactual: backend.counterfactual ? `${backend.counterfactual.primary_contributor} (${backend.counterfactual.contribution_score})` : '',
    story_narrative: backend.story || '',
    recommended_action: backend.analyst_recommendation?.recommended_action || '',
    processing_time_ms: backend.total_latency_ms ?? 250,
    timestamp: backend.timestamp || new Date().toISOString()
  };

  return { result: mappedResult };
}

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
