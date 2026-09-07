export interface ComponentScores {
  projection_score: number
  opportunity_score: number
  matchup_score: number
  environment_score: number
  health_score: number
  weather_score: number
}

export interface ItemizedStats {
  pass_att?: number
  pass_cmp?: number
  pass_yds?: number
  pass_td?: number
  pass_int?: number
  rush_att?: number
  rush_yds?: number
  rush_td?: number
  targets?: number
  receptions?: number
  rec_yds?: number
  rec_td?: number
  fg_made?: number
  pat_made?: number
  sacks?: number
  turnovers?: number
  def_td?: number
  pts_allowed?: number
  calculated_ppr?: number
}

export interface UpcomingMatchup {
  week: number
  opp: string
  is_home: boolean
  date?: string
  venue?: string
  is_dome?: boolean
  spread?: number
  implied_total?: number
}

export interface LineupMoveItem {
  player_id: number
  player_name: string
  position: string
  from_slot_id: number
  from_slot_name: string
  to_slot_id: number
  to_slot_name: string
  net_gain: number
  start_score: number
}

export interface PreFlightPushPreview {
  team_id: number
  team_name: string
  moves_count: number
  moves: LineupMoveItem[]
  can_push_to_espn: boolean
  status_message: string
}

export interface LineupPushResponse {
  success: boolean
  message: string
  moves_executed: number
  team_id: number
  raw_payload?: Record<string, any>
}

export interface StartSitEvaluation {
  player_id: number
  full_name: string
  position: string
  pro_team: string
  projected_points: number
  start_score: number
  confidence: string
  recommendation: string
  matchup_grade: string
  opponent: string
  is_home: boolean
  implied_team_total: number
  injury_status: string
  weather_summary: string | null
  reasons_positive: string[]
  reasons_negative: string[]
  components: ComponentScores
  itemized_stats?: ItemizedStats
  upcoming_schedule?: UpcomingMatchup[]
  consensus_rank?: number | null
  ceiling_score?: number
  floor_score?: number
  contingency_score?: number
  mode?: string
  game_date?: string | null
  live_vorp?: number | null
  fp_rank_ecr?: number | null
  fp_pos_rank?: string | null
  fp_tier?: number | null
  fp_rank_ave?: number | null
  fp_rank_std?: number | null
  fp_start_sit_grade?: string | null
  fp_r2p_pts?: number | null
  fp_injury_note?: string | null
  matchup_resilience?: string
  playoff_sos_score?: number
  playoff_sos_grade?: string
  opp_dvp_rank?: number | null
  opp_def_rank?: number | null
  opp_off_rank?: number | null
  opp_dvp_grade?: string | null
  matchup_stars?: number | null
  dvp_source?: string | null
  volume_share?: number | null
  team_projected_plays?: number | null
  team_pass_att?: number | null
  team_rush_att?: number | null
  efficiency_multiplier?: number | null
  proj_model?: number
  proj_fantasypros?: number
  proj_espn?: number
  proj_consensus?: number
  active_projection_source?: string
  consensus_spread?: number
  consensus_agreement?: string
  fp_itemized_stats?: Record<string, number>
  floor_points?: number | null
  ceiling_points?: number | null
  model_provenance?: Record<string, any>
  comparator_factors?: ComparatorFactorsBundle | null
}

export interface FactorScoreDetail {
  score: number
  bucket: string
  bucket_color: string
  raw_inputs: Record<string, any>
  contributions: Record<string, number>
  formula_description: string
  reasons: string[]
}

export interface ComparatorFactorsBundle {
  projection: FactorScoreDetail
  opportunity: FactorScoreDetail
  matchup: FactorScoreDetail
  environment: FactorScoreDetail
}


export interface SlotAssignment {
  slot_id: number
  slot_name: string
  recommended_player: StartSitEvaluation
  current_starter: StartSitEvaluation | null
  is_diff: boolean
  net_start_score_delta: number
  net_projected_delta: number
  is_flex_timing_optimal?: boolean
  flex_timing_note?: string | null
}

export interface ComparisonResult {
  recommended_player_id: number
  recommended_player_name: string
  is_close_call: boolean
  score_delta: number
  headline: string
  detailed_rationale: string
  players: StartSitEvaluation[]
}

export interface CloseCallPair {
  slot_name: string
  starter: StartSitEvaluation
  bench_player: StartSitEvaluation
  score_delta: number
  comparison: ComparisonResult
}

export interface OptimizedLineupResult {
  team_id: number
  total_start_score: number
  total_projected_points: number
  current_espn_projected: number
  net_projected_gain: number
  starters: SlotAssignment[]
  bench: StartSitEvaluation[]
  ir?: StartSitEvaluation[]
  bench_slots_count?: number
  ir_slots_count?: number
  close_calls: CloseCallPair[]
  differences_count: number
  mode?: string
  projection_source?: string
  total_model_projected?: number
  total_fp_projected?: number
  total_espn_projected?: number
  total_consensus_projected?: number
  opponent_projected_points?: number | null
  implied_matchup_spread?: number | null
  game_theory_posture?: string | null
  game_theory_recommendation?: string | null
  flex_timing_risk?: boolean
  flex_timing_warning?: string | null
  active_stacks?: string[]
}

export interface ScoringSettings {
  league_size: number
  weights: ScoringWeights
}

export interface TeamSummary {
  id: number
  league_id: number
  name: string
  abbrev: string
  primary_owner: string | null
  is_user_team: boolean
  division_id: number
  record: string
  wins?: number
  losses?: number
  ties?: number
  win_pct?: number
  rank?: number
  points_for: number
  points_against: number
  starter_count: number
  bench_count: number
}

export interface MatchupResponseItem {
  id: string
  league_id: number
  season: number
  week: number
  matchup_id: number
  home_team_id: number
  away_team_id: number
  home_team_name: string
  away_team_name: string
  home_team_abbrev: string
  away_team_abbrev: string
  home_score: number
  away_score: number
  home_projected: number
  away_projected: number
  winner: string | null
}

export interface LeagueSummaryResponse {
  id: number
  season: number
  name: string
  size: number
  current_week: number
  is_ppr: boolean
  reception_points: number
  roster_slots: Record<string, number>
  user_team_id: number | null
  last_synced_at: string | null
  teams: TeamSummary[]
}


export interface RosterArchitectureAudit {
  grade: string
  score: number
  handcuff_rb_count: number
  wasted_bench_slots: string[]
  key_strengths: string[]
  tactical_prescriptions: string[]
}

export interface LookaheadStreamerItem {
  player_id: number
  full_name: string
  position: string
  pro_team: string
  next_week: number
  next_opponent: string
  matchup_grade: string
  matchup_score: number
  tactical_reason: string
}

export interface DeadweightBenchItem {
  player_id: number
  full_name: string
  position: string
  projected_points: number
  start_score: number
  ceiling_score: number
  diagnosis: string
  suggested_action: string
}

export interface WaiverUpgradeRecommendation {
  pickup_player: StartSitEvaluation
  drop_player: StartSitEvaluation | null
  upgrade_type: string
  replaces_slot: string | null
  net_projected_delta: number
  net_start_score_delta: number
  rationale: string
}

export interface WaiverAnalysisResult {
  user_team_id: number
  total_available_scanned: number
  top_upgrades: WaiverUpgradeRecommendation[]
  streaming_te: StartSitEvaluation[]
  streaming_dst: StartSitEvaluation[]
  streaming_k: StartSitEvaluation[]
  architecture_audit?: RosterArchitectureAudit | null
  lookahead_streaming_dst?: LookaheadStreamerItem[]
  lookahead_streaming_k?: LookaheadStreamerItem[]
  deadweight_drops?: DeadweightBenchItem[]
}

export interface TradePlayerSummary {
  player_id: number
  full_name: string
  position: string
  pro_team: string
  projected_points: number
  start_score: number
  is_starter: boolean
  playoff_sos_score?: number
  playoff_sos_grade?: string
}

export interface ConsolidationTradeRecommendation {
  trade_id: string
  partner_team_id: number
  partner_team_name: string
  target_alpha: TradePlayerSummary
  send_players: TradePlayerSummary[]
  waiver_backfill?: TradePlayerSummary | null
  user_net_projected_delta: number
  user_net_start_score_delta: number
  partner_net_projected_delta: number
  feasibility: string
  rationale: string
  pitch_message: string
  target_playoff_sos?: number
  target_playoff_grade?: string
  user_playoff_leverage_delta?: number
  is_championship_target?: boolean
}

export interface ConsolidationTradeAnalysisResult {
  user_team_id: number
  total_trades_analyzed: number
  recommendations: ConsolidationTradeRecommendation[]
}

export interface ScoringWeights {
  projection_weight: number
  opportunity_weight: number
  matchup_weight: number
  environment_weight: number
  health_weight: number
  weather_weight: number
}

export interface WeeklyAuditMetrics {
  week: number
  starters_evaluated: number
  correct_start_decisions: number
  incorrect_start_decisions: number
  accuracy_pct: number
  total_recommended_points: number
  total_optimal_points: number
  points_left_on_bench: number
  efficiency_pct: number
}

export interface BacktestReport {
  total_weeks_audited: number
  overall_accuracy_pct: number
  overall_efficiency_pct: number
  current_weights: ScoringWeights
  weekly_breakdowns: WeeklyAuditMetrics[]
}

export interface PlayerDirectoryItem {
  id: number
  full_name: string
  position: string
  pro_team: string
  projected_points: number
  injury_status: string
  team_id: number | null
  team_name: string | null
  team_abbrev: string | null
  is_user_team: boolean
  is_starter: boolean
  is_free_agent: boolean
  slot_name: string | null
}

export interface InjuryResponseItem {
  athlete_id: number
  name: string
  position: string
  team: string
  status: string
  practice_status: string | null
  headline: string | null
  notes: string | null
  date: string | null
  is_playable: boolean
  is_out: boolean
}

export interface InjuryFeedResponse {
  total_count: number
  matched_count: number
  injuries: InjuryResponseItem[]
}

export interface StreamerRecommendation {
  player_id?: number | null
  player_name: string
  position: string
  pro_team: string
  rank_ecr: number
  pos_rank: string
  rank_std?: number | null
  grade?: string | null
  r2p_pts?: number | null
  opponent?: string | null
  is_rostered: boolean
  rostered_by_team_name?: string | null
}

export interface FantasyProsRankingsResponse {
  season: number
  week: number
  rankings: Record<string, any[]>
}

/**
 * Normalizes a player full name and optional position into a direct FantasyPros profile URL.
 * Example: "Christian McCaffrey" -> "https://www.fantasypros.com/nfl/players/christian-mccaffrey.php"
 * Team defense maps to the DST projections hub.
 */
export function getFantasyProsPlayerUrl(fullName: string, position?: string): string {
  if (!fullName) return 'https://www.fantasypros.com/nfl/'
  const posUpper = (position || '').trim().toUpperCase()
  if (posUpper === 'D/ST' || posUpper === 'DST' || posUpper === 'DEF') {
    return 'https://www.fantasypros.com/nfl/projections/dst.php'
  }
  const clean = fullName
    .toLowerCase()
    .replace(/[.']/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')

  return `https://www.fantasypros.com/nfl/players/${clean}.php`
}

/**
 * Checks if a status designation represents an injury (e.g. Q, OUT, IR, DOUBTFUL, etc.)
 */
export function isInjuryStatus(status?: string | null): boolean {
  if (!status) return false
  const s = status.trim().toUpperCase()
  if (['ACTIVE', 'HEALTHY', 'NORMAL', 'OK', 'NONE', 'N/A', ''].includes(s)) {
    return false
  }
  return true
}

export interface InactiveAlertItem {
  player_id: number
  full_name: string
  position: string
  team_name: string
  slot_name: string
  injury_status: string
  is_out: boolean
  is_starter: boolean
  alert_message: string
}

export interface InactiveAlertsResponse {
  team_id: number
  has_inactives: boolean
  count: number
  alerts: InactiveAlertItem[]
}

