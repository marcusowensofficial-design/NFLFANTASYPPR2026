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
  proj_sleeper?: number
  proj_espn?: number
  proj_consensus?: number
  projected_points_model?: number
  projected_points_fp?: number
  projected_points_sleeper?: number
  projected_points_espn?: number
  projected_points_consensus?: number
  active_projection_source?: string
  consensus_spread?: number
  consensus_agreement?: string
  fp_itemized_stats?: Record<string, number>
  sleeper_itemized_stats?: Record<string, number>
  floor_points?: number | null
  ceiling_points?: number | null
  model_provenance?: Record<string, any>
  comparator_factors?: ComparatorFactorsBundle | null
  wrcb_advantage_score?: number | null
  wrcb_advantage_rating?: string | null
  wrcb_primary_cb?: string | null
  wrcb_is_shadow?: boolean
  game_script?: string | null
  game_script_label?: string | null
  props_receptions_ou?: number | null
  props_rec_yds_ou?: number | null
  props_rush_yds_ou?: number | null
  props_rush_att_ou?: number | null
  props_pass_yds_ou?: number | null
  props_pass_tds_ou?: number | null
  props_anytime_td_odds?: number | null
  props_anytime_td_prob?: number | null
  props_implied_ppr_pts?: number | null
  props_market_sentiment?: string | null
  props_sharp_notes?: string[]
  props_vegas_grade?: string | null
  props_vegas_grade_label?: string | null
  props_vegas_grade_color?: string | null
  props_vegas_takeaway?: string | null
  boris_chen_tier?: number | null
  boris_chen_tier_label?: string | null
  boris_chen_is_dropoff?: boolean
  dvp_fpa?: DvPMatchupDetail | null
}

export interface PlayerPropsData {
  player_id: number
  player_name: string
  position: string
  team: string
  opponent: string
  receptions_ou?: number | null
  receptions_over_juice?: number | null
  receptions_under_juice?: number | null
  rec_yards_ou?: number | null
  rush_yards_ou?: number | null
  rush_att_ou?: number | null
  pass_yards_ou?: number | null
  pass_tds_ou?: number | null
  anytime_td_odds?: number | null
  anytime_td_prob: number
  implied_ppr_points: number
  source: string
  market_sentiment: string
  sharp_notes: string[]
  vegas_grade?: string | null
  vegas_grade_label?: string | null
  vegas_grade_color?: string | null
  vegas_takeaway?: string | null
}

export interface BorisChenTierItem {
  player_name: string
  position: string
  tier: number
  rank?: number | null
  team?: string | null
  tier_label: string
  is_tier_dropoff: boolean
  confidence_spread?: number
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
  total_sleeper_projected?: number
  total_espn_projected?: number
  total_consensus_projected?: number
  opponent_projected_points?: number | null
  opponent_team_id?: number | null
  opponent_team_name?: string | null
  opponent_team_abbrev?: string | null
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

export interface RosterPlayerResponse {
  entry_id: string
  player_id: number
  id?: number
  full_name: string
  position: string
  pro_team: string
  lineup_slot_id: number
  slot_name: string
  is_starter: boolean
  injury_status: string
  injured: boolean
  projected_points: number
  actual_points: number
  lineup_locked: boolean
  fp_injury_note?: string | null
  fp_start_sit_grade?: string | null
  fp_pos_rank?: string | null
  fp_tier?: number | null
  projected_points_espn?: number
  projected_points_fp?: number
  projected_points_sleeper?: number
  projected_points_model?: number
  projected_points_consensus?: number
}

export interface TeamRosterResponse {
  team_id: number
  team_name: string
  abbrev: string
  is_user_team: boolean
  starters_count: number
  bench_count: number
  total_projected_points: number
  roster: RosterPlayerResponse[]
  bench_slots_count: number
  ir_slots_count: number
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
  opp_dvp_rank?: number | null
  matchup_stars?: number | null
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
  starter_id: number
  starter_name: string
  position: string
  injury_status: string
  pro_team: string
  slot_name?: string
  starter_proj?: number
  recommended_bench_id?: number | null
  recommended_bench_name?: string | null
  recommended_bench_pos?: string | null
  recommended_bench_proj?: number
  top_waiver_id?: number | null
  top_waiver_name?: string | null
  top_waiver_pos?: string | null
  top_waiver_proj?: number
  net_projected_pts: number
  alert_message: string
  player_id?: number
  full_name?: string
  team_name?: string
  is_out?: boolean
  is_starter?: boolean
}

export interface InactiveAlertsResponse {
  team_id: number
  has_critical_inactives: boolean
  alerts_count: number
  alerts: InactiveAlertItem[]
}

export interface EmergencyPivotRequest {
  team_id: number
  starter_id: number
  bench_id: number
}

export interface EmergencyPivotResponse {
  success: boolean
  message: string
  starter_name: string
  bench_name: string
  from_slot: string
  to_slot: string
  moves_executed: number
}

export interface OpponentVulnerabilityItem {
  player_id: number
  player_name: string
  position: string
  pro_team: string
  slot_name: string
  projected_points: number
  injury_status: string
  vulnerability_type: string
  severity: string
  description: string
}

export interface SharedGameCorrelation {
  game_matchup: string
  user_players: string[]
  opp_players: string[]
  correlation_type: string
  strategic_takeaway: string
}

export interface TaleOfTheTapePlayer {
  id?: number
  player_id: number
  name?: string
  full_name: string
  position: string
  pro_team: string
  opponent: string
  projected_points: number
  opp_dvp_rank: number
  matchup_stars: number
  matchup_grade: string
  injury_status?: string
  slot_id?: number
}

export interface TaleOfTheTapeSlot {
  slot_name: string
  position: string
  user_player: TaleOfTheTapePlayer
  opp_player: TaleOfTheTapePlayer
  point_delta: number
  advantage: 'USER' | 'OPPONENT' | 'EVEN'
  leverage_label: string
}

export interface OpponentScoutingReport {
  week: number
  user_team_id: number
  user_team_name: string
  user_projected_total: number
  opp_team_id: number
  opp_team_name: string
  opp_primary_owner?: string | null
  opp_projected_total: number
  spread: number
  win_probability: number
  recommended_stance: 'FLOOR' | 'CEILING' | 'BALANCED'
  stance_headline: string
  stance_rationale: string
  vulnerabilities: OpponentVulnerabilityItem[]
  correlations: SharedGameCorrelation[]
  head_to_head_slots: TaleOfTheTapeSlot[]
  key_action_items: string[]
}


export interface CornerbackProfile {
  name: string
  team: string
  slot_role: string
  coverage_grade: number
  is_shadow: boolean
  targets_per_route_allowed: number
  fpts_per_route_allowed: number
  catch_rate_allowed: number
}

export interface WRAlignmentProfile {
  pct_slot: number
  pct_wide: number
  target_share: number
  route_win_rate: number
}

export interface WRCBMatchupAnalysis {
  player_id: number
  full_name: string
  position: string
  pro_team: string
  opponent: string
  projected_points: number
  alignment: WRAlignmentProfile
  primary_cb: CornerbackProfile
  secondary_cb?: CornerbackProfile | null
  slot_cb?: CornerbackProfile | null
  is_shadow_projected: boolean
  advantage_score: number
  advantage_rating: string
  tactical_takeaway: string
  is_user_rostered: boolean
  is_user_starter: boolean
}

export interface GameRosterExposurePlayer {
  player_id: number
  full_name: string
  position: string
  pro_team: string
  is_starter: boolean
  projected_points: number
}

export interface VegasGameEnvironment {
  game_id: string
  game_name: string
  game_date: string
  venue_name: string
  is_dome: boolean
  over_under: number
  spread: number
  favorite_team: string
  underdog_team: string
  spread_magnitude: number
  home_team: string
  away_team: string
  home_implied_total: number
  away_implied_total: number
  highest_implied_total: number
  game_script: string
  game_script_label: string
  pace_index: string
  expected_total_plays: number
  tactical_advice: string
  user_roster_exposure: GameRosterExposurePlayer[]
}

export interface TeamImpliedRanking {
  rank: number
  pro_team: string
  implied_total: number
  opponent: string
  opponent_implied_total?: number
  spread_diff?: number
  is_home: boolean
  is_favorite: boolean
  over_under: number
  game_script: string
}

export interface VegasIntelligenceResponse {
  season: number
  week: number
  total_games: number
  shootout_count: number
  games: VegasGameEnvironment[]
  team_rankings: TeamImpliedRanking[]
  top_target_games: string[]
}

export interface VegasPlayerPropsItem {
  player_id: number
  player_name: string
  position: string
  team: string
  opponent: string
  receptions_ou?: number | null
  receptions_over_juice?: number | null
  receptions_under_juice?: number | null
  rec_yards_ou?: number | null
  rush_yards_ou?: number | null
  rush_att_ou?: number | null
  pass_yards_ou?: number | null
  pass_tds_ou?: number | null
  anytime_td_odds?: number | null
  anytime_td_prob: number
  implied_ppr_points: number
  source: string
  market_sentiment: string
  sharp_notes: string[]
  vegas_grade: string
  vegas_grade_label: string
  vegas_grade_color: string
  vegas_takeaway: string
}


export interface H2HTaleOfTheTapeResponse {
  week: number
  user_team_name: string
  user_team_id: number
  user_projected_total: number
  opp_team_name: string
  opp_team_id: number
  opp_projected_total: number
  spread: number
  posture: string
  slots: TaleOfTheTapeSlot[]
  key_leverage_summary: string
}

export interface DvPMatchupDetail {
  season: number
  week: number
  defensive_team: string
  team_name: string
  position: string
  rank_softness: number
  rank_defense: number
  tier: 'SMASH' | 'FAVORABLE' | 'NEUTRAL' | 'TOUGH' | 'LOCKDOWN' | string
  tier_label: string
  dk_fpa: number
  fd_fpa?: number | null
  vs_avg: number
  prior_season_fpa: number
  current_season_fpa?: number | null
  last4_fpa?: number | null
  trend: string
  supporting_stats: Record<string, number>
  is_baseline: boolean
  sample_games_current: number
  source: string
  source_url?: string
  updated_at?: string | null
}

export interface DvPRecordItem {
  id: string
  season: number
  week: number
  pro_team: string
  team_name: string
  position: string
  rank_softness: number
  rank_defense: number
  tier: 'SMASH' | 'FAVORABLE' | 'NEUTRAL' | 'TOUGH' | 'LOCKDOWN' | string
  tier_label: string
  dk_fpa: number
  fd_fpa?: number | null
  vs_avg: number
  prior_season_fpa: number
  current_season_fpa?: number | null
  last4_fpa?: number | null
  trend: string
  supporting_stats: Record<string, number>
  is_baseline: boolean
  sample_games_current: number
  source: string
  source_url: string
  updated_at?: string | null
}

export interface DvPStatusResponse {
  total_records: number
  is_seeded: boolean
  last_updated?: string | null
  hours_since_sync: number
  is_stale: boolean
  is_baseline: boolean
  sample_games_current?: number
  baseline_context: string
}

// -----------------------------------------------------------------------------
// Daily Fantasy Sports (DFS) Types
// -----------------------------------------------------------------------------

export interface DFSSlateInfo {
  id: string
  name: string
  games_count: number
  platform: string
  is_available: boolean
}

export interface DFSGameStack {
  game: string
  game_ou: number
  qb: string
  target: string
  bring_back: string
  total_salary: number
  total_proj: number
  avg_value: number
}

export interface DFSRosterItem {
  slot: string
  player_id: string
  name: string
  position: string
  team: string
  opponent: string
  salary: number
  proj: number
  ceiling: number
  team_implied: number
  opp_soft_rank: number
  opp_tier?: string
  opp_tier_label?: string
  opp_fd_fpa?: number
  value_ratio: number
  proj_ownership: number
  ownership_tier: string
  leverage_score: number
}

export interface DFSWeatherAudit {
  team: string
  is_dome: boolean
  temp: number
  wind_mph: number
  gusts_mph: number
  precip_in: number
  concern: string
}

export interface DFSInjuryAlert {
  player: string
  status: string
  headline: string
  practice: string
}

export interface DFSLineupAudit {
  weather: DFSWeatherAudit[]
  injury_alerts: DFSInjuryAlert[]
}

export interface DFSExposureItem {
  player_id: string
  name: string
  position: string
  team: string
  count: number
  total_lineups: number
  pct: number
}

export interface DFSLineupResponse {
  mode: string
  slate_id: string
  total_salary: number
  salary_cap: number
  salary_remaining: number
  total_projected_points: number
  total_ceiling_points: number
  value_multiplier: number
  full_ppr_projected_points: number
  cumulative_ownership: number
  ownership_rating: string
  ownership_assessment: string
  roster: DFSRosterItem[]
  active_stack?: {
    qb: string | null
    team: string | null
    opponent: string | null
  } | null
  audit?: DFSLineupAudit
  lineups?: DFSLineupResponse[]
  exposure?: Record<string, DFSExposureItem>
  projection_source?: string
}

export interface DFSUploadResponse {
  success: boolean
  slate_id: string
  filename: string
  total_players: number
  teams: string[]
  games_count: number
  salary_min: number
  salary_max: number
  top_stars: {
    name: string
    position: string
    team: string
    salary: number
    proj: number
  }[]
}

export interface DFSPlayerPoolItem {
  player_id: string
  name: string
  position: string
  team: string
  opponent: string
  salary: number
  proj: number
  ceiling_proj: number
  floor_proj?: number
  team_implied: number
  opp_soft_rank: number
  opp_tier?: string
  opp_tier_label?: string
  opp_fd_fpa?: number
  value_ratio: number
  proj_ownership: number
  ownership_tier: string
  leverage_score: number
}

export interface DFSSlateDataResponse {
  slate_id: string
  projection_source?: string
  total_players: number
  top_stacks: DFSGameStack[]
  leverage_plays: DFSPlayerPoolItem[]
  chalk_plays: DFSPlayerPoolItem[]
  players: DFSPlayerPoolItem[]
}

export interface PlayerMarketSentimentItem {
  player_id: number
  player_name: string
  position: string
  pro_team: string
  opponent: string
  is_thursday_kickoff: boolean
  game_date?: string | null
  starter_confidence: number
  starter_market_question?: string | null
  has_starter_controversy: boolean
  injury_status: string
  practice_status?: string | null
  decoy_risk: 'LOW' | 'MODERATE' | 'HIGH'
  injury_headline?: string | null
  is_rookie: boolean
  rookie_tier?: string | null
  oroy_implied_prob?: number | null
  market_headline: string
  tactical_advice: string
  urgency_level: 'CRITICAL_TNF' | 'HIGH' | 'NORMAL'
}




