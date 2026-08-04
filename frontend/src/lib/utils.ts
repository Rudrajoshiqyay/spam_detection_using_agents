import { clsx, type ClassValue } from 'clsx'
import type { RiskLevel, DecisionType } from '@/types'

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

export function riskColor(score: number): string {
  if (score >= 80) return 'text-red-400'
  if (score >= 60) return 'text-orange-400'
  if (score >= 40) return 'text-yellow-400'
  if (score >= 20) return 'text-blue-400'
  return 'text-green-400'
}

export function riskBg(score: number): string {
  if (score >= 80) return 'bg-red-500/20 border-red-500/40'
  if (score >= 60) return 'bg-orange-500/20 border-orange-500/40'
  if (score >= 40) return 'bg-yellow-500/20 border-yellow-500/40'
  if (score >= 20) return 'bg-blue-500/20 border-blue-500/40'
  return 'bg-green-500/20 border-green-500/40'
}

export function riskLevelColor(level: RiskLevel): string {
  const map: Record<RiskLevel, string> = {
    critical: 'text-red-400',
    high: 'text-orange-400',
    medium: 'text-yellow-400',
    low: 'text-blue-400',
    minimal: 'text-green-400',
  }
  return map[level] ?? 'text-gray-400'
}

export function decisionColor(decision: DecisionType): string {
  const map: Record<DecisionType, string> = {
    block: 'text-red-400 bg-red-500/10 border-red-500/30',
    review: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
    approve: 'text-green-400 bg-green-500/10 border-green-500/30',
    auto_approve: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  }
  return map[decision] ?? 'text-gray-400'
}

export function formatAmount(amount: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount)
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function relativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export function truncate(s: string, n = 30): string {
  return s.length > n ? s.slice(0, n) + '…' : s
}

// Generate mock transactions for demo mode
let _txnCounter = 0
const MERCHANTS = [
  ['Whole Foods', 'grocery'], ['Amazon', 'online_retail'], ['Shell Gas', 'gas_station'],
  ['Apple Store', 'electronics'], ['CVS Pharmacy', 'pharmacy'], ['Starbucks', 'food_beverage'],
  ['Uber', 'transport'], ['Netflix', 'subscription'], ['Target', 'retail'], ['Best Buy', 'electronics'],
  ['Coinbase', 'crypto'], ['Binance', 'crypto'], ['Western Union', 'wire_transfer'],
  ['Steam', 'gaming'], ['Instacart', 'grocery'],
]
const CITIES = ['New York', 'London', 'Singapore', 'Tokyo', 'Lagos', 'Dubai', 'Paris', 'Berlin']
const COUNTRIES = ['US', 'GB', 'SG', 'JP', 'NG', 'AE', 'FR', 'DE']
const USERS = ['alice_johnson', 'bob_smith', 'carlos_mendez', 'diana_prince', 'evan_chen']
const CHANNELS = ['online', 'pos', 'mobile', 'atm']

export function generateMockTransaction(): import('@/types').Transaction {
  const [merchant, category] = MERCHANTS[Math.floor(Math.random() * MERCHANTS.length)]
  const cityIdx = Math.floor(Math.random() * CITIES.length)
  const isHighRisk = ['crypto', 'wire_transfer'].includes(category)
  return {
    transaction_id: `txn_${Date.now()}_${++_txnCounter}`,
    user_id: USERS[Math.floor(Math.random() * USERS.length)],
    amount: isHighRisk
      ? Math.floor(Math.random() * 5000) + 500
      : Math.floor(Math.random() * 300) + 5,
    currency: 'USD',
    merchant_id: `m_${merchant.toLowerCase().replace(/\s/g, '_')}`,
    merchant_name: merchant,
    merchant_category: category,
    location_city: CITIES[cityIdx],
    location_country: COUNTRIES[cityIdx],
    latitude: 40.7128,
    longitude: -74.0060,
    device_id: `dev_${Math.floor(Math.random() * 20)}`,
    channel: CHANNELS[Math.floor(Math.random() * CHANNELS.length)],
    transaction_type: 'purchase',
    timestamp: new Date().toISOString(),
    is_international: cityIdx > 1,
    ip_address: `${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.1.1`,
  }
}

export function generateMockDecision(txn: import('@/types').Transaction): FraudDecision {
  const isHighRisk = ['crypto', 'wire_transfer'].includes(txn.merchant_category)
  const isMediumRisk = ['gaming', 'online_retail'].includes(txn.merchant_category)
  const baseScore = isHighRisk ? 70 + Math.random() * 25 : isMediumRisk ? 35 + Math.random() * 30 : 5 + Math.random() * 25
  const score = Math.round(baseScore)
  const level: RiskLevel = score >= 80 ? 'critical' : score >= 60 ? 'high' : score >= 40 ? 'medium' : score >= 20 ? 'low' : 'minimal'
  const decision: DecisionType = score >= 75 ? 'block' : score >= 45 ? 'review' : 'approve'
  return {
    transaction_id: txn.transaction_id,
    user_id: txn.user_id,
    decision,
    risk_score: score,
    risk_level: level,
    confidence: 0.7 + Math.random() * 0.25,
    pre_risk_score: score * 0.8,
    should_investigate: score >= 45,
    screening_flags: score > 50 ? ['high_amount', txn.is_international ? 'international' : 'new_merchant'] : [],
    agent_risks: [
      { agent: 'behavior', risk_score: score * 0.9, confidence: 0.8, key_findings: ['behavioral_deviation'], verdict: score > 50 ? 'suspicious' : 'normal', reasoning: 'Pattern analysis' },
      { agent: 'device', risk_score: score * 0.7, confidence: 0.85, key_findings: ['device_check'], verdict: 'normal', reasoning: 'Device fingerprint clean' },
      { agent: 'geo', risk_score: txn.is_international ? score * 1.1 : score * 0.5, confidence: 0.9, key_findings: txn.is_international ? ['cross_border'] : [], verdict: txn.is_international ? 'suspicious' : 'normal', reasoning: 'Geo risk assessment' },
      { agent: 'merchant', risk_score: isHighRisk ? score * 1.2 : score * 0.6, confidence: 0.75, key_findings: isHighRisk ? ['high_risk_merchant'] : [], verdict: isHighRisk ? 'high_risk' : 'trusted', reasoning: 'Merchant reputation check' },
      { agent: 'graph', risk_score: score * 0.8, confidence: 0.7, key_findings: [], verdict: 'normal', reasoning: 'No fraud network detected' },
    ],
    consensus_score: score,
    weighted_risk: score,
    positive_signals: score < 40 ? ['known_merchant', 'normal_amount', 'familiar_location'] : [],
    negative_signals: score > 50 ? ['high_risk_merchant_category', txn.is_international ? 'cross_border' : 'velocity_spike'] : [],
    explanation: `Transaction analyzed across 5 AI agents. Risk score ${score}/100 based on ${txn.merchant_category} category, ${txn.is_international ? 'international' : 'domestic'} location, and behavioral pattern.`,
    counterfactual: score > 50 ? `If this transaction were domestic and the merchant were lower-risk, score would drop to ${Math.max(10, score - 35)}.` : 'Transaction profile is consistent with historical behavior.',
    story_narrative: `${txn.user_id} attempted a ${formatAmount(txn.amount)} ${txn.merchant_category} transaction at ${txn.merchant_name} from ${txn.location_city}. ${decision === 'block' ? 'Transaction was blocked due to elevated risk indicators.' : decision === 'review' ? 'Transaction flagged for analyst review.' : 'Transaction approved within normal parameters.'}`,
    recommended_action: decision === 'block' ? 'Block and notify customer' : decision === 'review' ? 'Hold for analyst review' : 'Approve transaction',
    processing_time_ms: 80 + Math.random() * 120,
    timestamp: new Date().toISOString(),
  }
}

// Re-export for direct use
import type { FraudDecision } from '@/types'
