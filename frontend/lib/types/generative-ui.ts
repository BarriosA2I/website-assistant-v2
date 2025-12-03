// lib/types/generative-ui.ts
// ============================================================================
// BARRIOS A2I WEBSITE ASSISTANT v2.0 — GENERATIVE UI TYPES
// ============================================================================
// These types mirror the Python Pydantic schemas exactly.
// Used for type-safe rendering of dynamic cards from the backend.
// ============================================================================

// ============================================================================
// ENUMS
// ============================================================================

export enum CardType {
  COMPETITOR_ANALYSIS = "competitor_analysis",
  PERSONA = "persona",
  SCRIPT_PREVIEW = "script_preview",
  ROI_CALCULATOR = "roi_calculator",
  PRICING_COMPARISON = "pricing_comparison",
  MARKET_TREND = "market_trend",
}

export type Advantage = "us" | "them" | "tie";
export type Severity = "low" | "medium" | "high" | "critical";
export type BudgetAuthority = "none" | "influence" | "approve" | "final_decision";
export type ScriptFormat = "15s" | "30s" | "60s" | "90s";
export type ScriptTone = "professional" | "casual" | "urgent" | "inspirational";
export type Platform = "youtube" | "tiktok" | "instagram" | "linkedin" | "tv";
export type ScriptStatus = "draft" | "pending_approval" | "approved" | "rejected";
export type SectionType = "hook" | "problem" | "solution" | "proof" | "cta";
export type TrendDirection = "up" | "down" | "stable";
export type CtaAction = "book_call" | "start_trial" | "contact_sales";
export type PricingPeriod = "one-time" | "monthly" | "yearly";

// ============================================================================
// COMPETITOR ANALYSIS CARD
// ============================================================================

export interface CompetitorStat {
  metric: string;
  our_value: string;
  their_value: string;
  advantage: Advantage;
  delta_percent?: number | null;
}

export interface KillShot {
  headline: string;
  detail: string;
  proof_point?: string | null;
}

export interface CompetitorAnalysisCard {
  type: CardType.COMPETITOR_ANALYSIS;
  title?: string;
  competitor_name: string;
  competitor_logo_url?: string | null;
  our_logo_url?: string | null;
  stats: CompetitorStat[];
  kill_shot: KillShot;
  confidence_score: number;
  data_freshness: string;
  sources: string[];
  generated_at: string;
  trace_id?: string | null;
}

// ============================================================================
// PERSONA CARD
// ============================================================================

export interface PainPoint {
  title: string;
  severity: Severity;
  description: string;
}

export interface PersonaCard {
  type: CardType.PERSONA;
  persona_name: string;
  title: string;
  company_type: string;
  avatar_url?: string | null;
  age_range: string;
  income_range: string;
  income_percentile: number;
  pain_points: PainPoint[];
  goals: string[];
  objections: string[];
  decision_drivers: string[];
  budget_authority: BudgetAuthority;
  buying_timeline: string;
  confidence_score: number;
  generated_at: string;
}

// ============================================================================
// SCRIPT PREVIEW CARD
// ============================================================================

export interface ScriptSection {
  section_type: SectionType;
  content: string;
  duration_seconds?: number | null;
  notes?: string | null;
}

export interface ScriptPreviewCard {
  type: CardType.SCRIPT_PREVIEW;
  script_id: string;
  title: string;
  format: ScriptFormat;
  tone: ScriptTone;
  sections: ScriptSection[];
  full_script: string;
  word_count: number;
  estimated_duration_seconds: number;
  target_persona?: string | null;
  target_platform: Platform;
  status: ScriptStatus;
  revision_number: number;
  can_regenerate: boolean;
  can_edit: boolean;
  can_approve: boolean;
  generated_at: string;
}

// ============================================================================
// ROI CALCULATOR CARD
// ============================================================================

export interface ROISlider {
  id: string;
  label: string;
  min_value: number;
  max_value: number;
  default_value: number;
  step: number;
  unit: string;
  tooltip?: string | null;
}

export interface ROIProjection {
  metric_name: string;
  current_value: number;
  projected_value: number;
  improvement_percent: number;
  timeframe: string;
}

export interface ROICalculatorCard {
  type: CardType.ROI_CALCULATOR;
  title: string;
  subtitle?: string | null;
  sliders: ROISlider[];
  projections: ROIProjection[];
  total_savings: number;
  savings_currency: string;
  payback_period_months?: number | null;
  formula_description?: string | null;
  cta_text: string;
  cta_action: CtaAction;
  generated_at: string;
}

// ============================================================================
// PRICING COMPARISON CARD
// ============================================================================

export interface PricingTier {
  name: string;
  price: number;
  period: PricingPeriod;
  features: string[];
  is_recommended: boolean;
  competitor_price?: number | null;
  savings_vs_competitor?: number | null;
}

export interface PricingComparisonCard {
  type: CardType.PRICING_COMPARISON;
  title: string;
  tiers: PricingTier[];
  competitor_name?: string | null;
  key_differentiators: string[];
  money_back_guarantee?: string | null;
  generated_at: string;
}

// ============================================================================
// MARKET TREND CARD
// ============================================================================

export interface TrendDataPoint {
  date: string;
  value: number;
  label?: string | null;
}

export interface MarketTrendCard {
  type: CardType.MARKET_TREND;
  title: string;
  trend_direction: TrendDirection;
  trend_percent: number;
  timeframe: string;
  data_points: TrendDataPoint[];
  insight: string;
  recommendation: string;
  sources: string[];
  generated_at: string;
}

// ============================================================================
// RENDER CARD UNION TYPE
// ============================================================================

export type RenderCard =
  | CompetitorAnalysisCard
  | PersonaCard
  | ScriptPreviewCard
  | ROICalculatorCard
  | PricingComparisonCard
  | MarketTrendCard;

// ============================================================================
// ASSISTANT MESSAGE
// ============================================================================

export interface AssistantMessage {
  content: string;
  render_card?: RenderCard | null;
  intent: string;
  confidence: number;
  model_used: string;
  latency_ms: number;
  cost_usd: number;
  trace_id: string;
  session_id: string;
  turn_number: number;
}

// ============================================================================
// TYPE GUARDS
// ============================================================================

export function isCompetitorCard(card: RenderCard): card is CompetitorAnalysisCard {
  return card.type === CardType.COMPETITOR_ANALYSIS;
}

export function isPersonaCard(card: RenderCard): card is PersonaCard {
  return card.type === CardType.PERSONA;
}

export function isScriptCard(card: RenderCard): card is ScriptPreviewCard {
  return card.type === CardType.SCRIPT_PREVIEW;
}

export function isROICard(card: RenderCard): card is ROICalculatorCard {
  return card.type === CardType.ROI_CALCULATOR;
}

export function isPricingCard(card: RenderCard): card is PricingComparisonCard {
  return card.type === CardType.PRICING_COMPARISON;
}

export function isTrendCard(card: RenderCard): card is MarketTrendCard {
  return card.type === CardType.MARKET_TREND;
}
