// Core domain types mirroring the FastAPI backend models

export type RiskLevel = 'critical' | 'high' | 'medium' | 'low' | 'minimal';
export type DecisionType = 'block' | 'review' | 'approve' | 'auto_approve';
export type OutcomeLabel = 'true_positive' | 'false_positive' | 'true_negative' | 'false_negative' | 'unknown';

export interface Transaction {
  transaction_id: string;
  user_id: string;
  amount: number;
  currency: string;
  merchant_id: string;
  merchant_name: string;
  merchant_category: string;
  location_city: string;
  location_country: string;
  latitude: number;
  longitude: number;
  device_id: string;
  channel: string;
  transaction_type: string;
  timestamp: string;
  is_international: boolean;
  ip_address?: string;
}

export interface AgentRisk {
  agent: string;
  risk_score: number;
  confidence: number;
  key_findings: string[];
  verdict: string;
  reasoning: string;
  latency_ms?: number;
}

export interface FraudDecision {
  transaction_id: string;
  user_id: string;
  decision: DecisionType;
  risk_score: number;
  risk_level: RiskLevel;
  confidence: number;
  pre_risk_score: number;
  should_investigate: boolean;
  screening_flags: string[];
  agent_risks: AgentRisk[];
  consensus_score: number;
  weighted_risk: number;
  positive_signals: string[];
  negative_signals: string[];
  explanation: string;
  counterfactual: string;
  story_narrative: string;
  recommended_action: string;
  kill_chain_stage?: string;
  graph_risk_score?: number;
  processing_time_ms: number;
  timestamp: string;
}

export interface LiveTransaction extends Transaction {
  decision?: FraudDecision;
  status: 'processing' | 'approved' | 'blocked' | 'review';
  riskScore?: number;
}

export interface FeedbackStats {
  total_feedback: number;
  outcome_counts: Record<string, number>;
  missed_fraud_types: Record<string, number>;
  metrics: {
    precision: number | null;
    recall: number | null;
    f1_score: number | null;
    false_positive_rate: number | null;
  };
}

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'error';
  redis: string;
  timestamp: string;
  pipeline_latency_ms?: number;
  graph_nodes?: number;
}

export interface PipelineNode {
  id: string;
  label: string;
  type: 'input' | 'service' | 'agent' | 'consensus' | 'output' | 'feedback';
  x: number;
  y: number;
  description: string;
  purpose: string;
  inputs: string[];
  outputs: string[];
  files: string[];
  latency: string;
  auditScore?: number;
  status?: 'idle' | 'active' | 'complete' | 'error';
  confidence?: number;
  testCount?: number;
  dependencies?: string[];
}

export interface SystemMetric {
  label: string;
  value: string | number;
  unit?: string;
  status: 'ok' | 'warning' | 'error';
  trend?: number;
}

export interface ChartDataPoint {
  time: string;
  value: number;
  fraud?: number;
  legitimate?: number;
}

export interface FraudRing {
  ring_id: string;
  ring_type: string;
  member_count: number;
  total_amount: number;
  risk_score: number;
  detected_at: string;
}

export interface DemoScenario {
  id: string;
  name: string;
  description: string;
  icon: string;
  riskLevel: RiskLevel;
}
