import { useState, useEffect, useMemo } from 'react'
import type {
  LeagueSummaryResponse,
  OptimizedLineupResult,
  VegasIntelligenceResponse,
  TeamImpliedRanking,
  VegasPlayerPropsItem,
} from '../../types'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'
import { formatToMDT } from '../../utils/dateUtils'

// NFL Team Metadata Directory
const NFL_TEAMS_INFO: Record<string, { name: string; city: string; stadium: string; conference: 'AFC' | 'NFC' }> = {
  ARI: { name: 'Cardinals', city: 'Arizona', stadium: 'State Farm Stadium', conference: 'NFC' },
  ATL: { name: 'Falcons', city: 'Atlanta', stadium: 'Mercedes-Benz Stadium', conference: 'NFC' },
  BAL: { name: 'Ravens', city: 'Baltimore', stadium: 'M&T Bank Stadium', conference: 'AFC' },
  BUF: { name: 'Bills', city: 'Buffalo', stadium: 'Highmark Stadium', conference: 'AFC' },
  CAR: { name: 'Panthers', city: 'Carolina', stadium: 'Bank of America Stadium', conference: 'NFC' },
  CHI: { name: 'Bears', city: 'Chicago', stadium: 'Soldier Field', conference: 'NFC' },
  CIN: { name: 'Bengals', city: 'Cincinnati', stadium: 'Paycor Stadium', conference: 'AFC' },
  CLE: { name: 'Browns', city: 'Cleveland', stadium: 'Huntington Bank Field', conference: 'AFC' },
  DAL: { name: 'Cowboys', city: 'Dallas', stadium: 'AT&T Stadium', conference: 'NFC' },
  DEN: { name: 'Broncos', city: 'Denver', stadium: 'Empower Field at Mile High', conference: 'AFC' },
  DET: { name: 'Lions', city: 'Detroit', stadium: 'Ford Field', conference: 'NFC' },
  GB: { name: 'Packers', city: 'Green Bay', stadium: 'Lambeau Field', conference: 'NFC' },
  HOU: { name: 'Texans', city: 'Houston', stadium: 'NRG Stadium', conference: 'AFC' },
  IND: { name: 'Colts', city: 'Indianapolis', stadium: 'Lucas Oil Stadium', conference: 'AFC' },
  JAX: { name: 'Jaguars', city: 'Jacksonville', stadium: 'EverBank Stadium', conference: 'AFC' },
  KC: { name: 'Chiefs', city: 'Kansas City', stadium: 'GEHA Field at Arrowhead', conference: 'AFC' },
  LAC: { name: 'Chargers', city: 'Los Angeles', stadium: 'SoFi Stadium', conference: 'AFC' },
  LAR: { name: 'Rams', city: 'Los Angeles', stadium: 'SoFi Stadium', conference: 'NFC' },
  LV: { name: 'Raiders', city: 'Las Vegas', stadium: 'Allegiant Stadium', conference: 'AFC' },
  MIA: { name: 'Dolphins', city: 'Miami', stadium: 'Hard Rock Stadium', conference: 'AFC' },
  MIN: { name: 'Vikings', city: 'Minnesota', stadium: 'U.S. Bank Stadium', conference: 'NFC' },
  NE: { name: 'Patriots', city: 'New England', stadium: 'Gillette Stadium', conference: 'AFC' },
  NO: { name: 'Saints', city: 'New Orleans', stadium: 'Caesars Superdome', conference: 'NFC' },
  NYG: { name: 'Giants', city: 'New York', stadium: 'MetLife Stadium', conference: 'NFC' },
  NYJ: { name: 'Jets', city: 'New York', stadium: 'MetLife Stadium', conference: 'AFC' },
  PHI: { name: 'Eagles', city: 'Philadelphia', stadium: 'Lincoln Financial Field', conference: 'NFC' },
  PIT: { name: 'Steelers', city: 'Pittsburgh', stadium: 'Acrisure Stadium', conference: 'AFC' },
  SEA: { name: 'Seahawks', city: 'Seattle', stadium: 'Lumen Field', conference: 'NFC' },
  SF: { name: '49ers', city: 'San Francisco', stadium: "Levi's Stadium", conference: 'NFC' },
  TB: { name: 'Buccaneers', city: 'Tampa Bay', stadium: 'Raymond James Stadium', conference: 'NFC' },
  TEN: { name: 'Titans', city: 'Tennessee', stadium: 'Nissan Stadium', conference: 'AFC' },
  WSH: { name: 'Commanders', city: 'Washington', stadium: 'Northwest Stadium', conference: 'NFC' },
}

interface VegasTabProps {
  league: LeagueSummaryResponse | null
  selectedTeamId: number
  lineup: OptimizedLineupResult | null
  onSelectTab?: (tab: string) => void
  onCompareStarterWithBench?: (starter: any, bench: any) => void
}

export function VegasTab({
  league,
  selectedTeamId,
  lineup,
}: VegasTabProps) {
  const currentWeek = league?.current_week || 1
  const [selectedWeek, setSelectedWeek] = useState<number>(currentWeek)
  const [vegasData, setVegasData] = useState<VegasIntelligenceResponse | null>(null)
  const [propsData, setPropsData] = useState<VegasPlayerPropsItem[]>([])
  const [isLoadingVegas, setIsLoadingVegas] = useState<boolean>(true)
  const [isLoadingProps, setIsLoadingProps] = useState<boolean>(false)
  const [activeSubView, setActiveSubView] = useState<'totals' | 'schedule' | 'matrix' | 'props'>('totals')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [teamFilter, setTeamFilter] = useState<'ALL' | 'HIGH' | 'LOW' | 'FAVORITES' | 'UNDERDOGS' | 'ROSTER'>('ALL')
  const [propsPosFilter, setPropsPosFilter] = useState<string>('ALL')
  const [copiedSlate, setCopiedSlate] = useState<boolean>(false)

  // Sync selectedWeek if league loaded with valid week
  useEffect(() => {
    if (league?.current_week && league.current_week !== selectedWeek) {
      setSelectedWeek(league.current_week)
    }
  }, [league?.current_week])

  // Fetch Vegas Intelligence & Props for the selected week
  useEffect(() => {
    loadVegasForWeek(selectedWeek)
  }, [selectedWeek, selectedTeamId])

  const loadVegasForWeek = async (week: number) => {
    setIsLoadingVegas(true)
    setIsLoadingProps(true)
    try {
      const [vRes, pRes] = await Promise.all([
        fetch(`/api/analysis/vegas-environments?week=${week}&team_id=${selectedTeamId}`),
        fetch(`/api/analysis/vegas-slate-props?week=${week}&limit=80`),
      ])

      if (vRes.ok) {
        const vJson: VegasIntelligenceResponse = await vRes.json()
        setVegasData(vJson)
      } else {
        console.error('Failed to fetch vegas environments:', vRes.status)
      }

      if (pRes.ok) {
        const pJson: VegasPlayerPropsItem[] = await pRes.json()
        setPropsData(pJson)
      }
    } catch (err) {
      console.error('Error fetching vegas intelligence:', err)
    } finally {
      setIsLoadingVegas(false)
      setIsLoadingProps(false)
    }
  }

  // Roster set for quick lookup
  const userRosterTeamPids = useMemo(() => {
    const pids = new Set<number>()
    if (lineup?.starters) {
      for (const s of lineup.starters) {
        const p = s.recommended_player
        if (p?.player_id) pids.add(p.player_id)
      }
    }
    if (lineup?.bench) {
      for (const b of lineup.bench) {
        if (b?.player_id) pids.add(b.player_id)
      }
    }
    return pids
  }, [lineup])

  // Map of team -> array of rostered players in user team
  const rosterPlayersByTeam = useMemo(() => {
    const map = new Map<string, Array<{ id: number; name: string; pos: string; isStarter: boolean; proj: number }>>()
    if (!lineup) return map

    if (lineup.starters) {
      for (const s of lineup.starters) {
        const p = s.recommended_player
        if (!p) continue
        const team = (p.pro_team || '').toUpperCase().trim()
        if (!team) continue
        const list = map.get(team) || []
        list.push({
          id: p.player_id,
          name: p.full_name,
          pos: p.position,
          isStarter: true,
          proj: p.projected_points || 0,
        })
        map.set(team, list)
      }
    }

    if (lineup.bench) {
      for (const b of lineup.bench) {
        if (!b) continue
        const team = (b.pro_team || '').toUpperCase().trim()
        if (!team) continue
        const list = map.get(team) || []
        list.push({
          id: b.player_id,
          name: b.full_name,
          pos: b.position,
          isStarter: false,
          proj: b.projected_points || 0,
        })
        map.set(team, list)
      }
    }

    return map
  }, [lineup])

  // Slate KPI calculations
  const slateKpis = useMemo(() => {
    if (!vegasData || vegasData.games.length === 0) {
      return {
        totalGames: 0,
        shootoutCount: 0,
        highestTeam: null as TeamImpliedRanking | null,
        lowestTeam: null as TeamImpliedRanking | null,
        avgTotal: 0,
        myRosterGamesCount: 0,
      }
    }

    const totalGames = vegasData.games.length
    const shootoutCount = vegasData.shootout_count || vegasData.games.filter((g) => g.game_script === 'SHOOTOUT').length

    const sortedRankings = [...vegasData.team_rankings].sort((a, b) => b.implied_total - a.implied_total)
    const highestTeam = sortedRankings.length > 0 ? sortedRankings[0] : null
    const lowestTeam = sortedRankings.length > 0 ? sortedRankings[sortedRankings.length - 1] : null

    const totalOU = vegasData.games.reduce((acc, g) => acc + (g.over_under || 0), 0)
    const avgTotal = totalGames > 0 ? totalOU / totalGames : 0

    const myRosterGamesCount = vegasData.games.filter((g) => {
      const homeTeam = (g.home_team || '').toUpperCase().trim()
      const awayTeam = (g.away_team || '').toUpperCase().trim()
      return (rosterPlayersByTeam.get(homeTeam)?.length || 0) > 0 || (rosterPlayersByTeam.get(awayTeam)?.length || 0) > 0
    }).length

    return {
      totalGames,
      shootoutCount,
      highestTeam,
      lowestTeam,
      avgTotal,
      myRosterGamesCount,
    }
  }, [vegasData, rosterPlayersByTeam])

  // Filtered Team Rankings
  const filteredTeamRankings = useMemo(() => {
    if (!vegasData) return []
    let list = vegasData.team_rankings

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      list = list.filter((t) => {
        const teamInfo = NFL_TEAMS_INFO[t.pro_team]
        const nameMatch = teamInfo ? `${teamInfo.city} ${teamInfo.name}`.toLowerCase().includes(q) : false
        return t.pro_team.toLowerCase().includes(q) || t.opponent.toLowerCase().includes(q) || nameMatch
      })
    }

    if (teamFilter === 'HIGH') {
      list = list.filter((t) => t.implied_total >= 24.0)
    } else if (teamFilter === 'LOW') {
      list = list.filter((t) => t.implied_total < 21.0)
    } else if (teamFilter === 'FAVORITES') {
      list = list.filter((t) => t.is_favorite)
    } else if (teamFilter === 'UNDERDOGS') {
      list = list.filter((t) => !t.is_favorite)
    } else if (teamFilter === 'ROSTER') {
      list = list.filter((t) => (rosterPlayersByTeam.get(t.pro_team)?.length || 0) > 0)
    }

    return list
  }, [vegasData, searchQuery, teamFilter, rosterPlayersByTeam])

  // Filtered Games Schedule
  const filteredGames = useMemo(() => {
    if (!vegasData) return []
    let list = vegasData.games

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      list = list.filter(
        (g) =>
          g.game_name.toLowerCase().includes(q) ||
          g.home_team.toLowerCase().includes(q) ||
          g.away_team.toLowerCase().includes(q) ||
          g.venue_name.toLowerCase().includes(q)
      )
    }

    if (teamFilter === 'ROSTER') {
      list = list.filter((g) => {
        const homeList = rosterPlayersByTeam.get(g.home_team.toUpperCase().trim()) || []
        const awayList = rosterPlayersByTeam.get(g.away_team.toUpperCase().trim()) || []
        return homeList.length > 0 || awayList.length > 0
      })
    }

    return [...list].sort((a, b) => {
      const timeA = a.game_date ? new Date(a.game_date).getTime() : Infinity
      const timeB = b.game_date ? new Date(b.game_date).getTime() : Infinity
      if (timeA !== timeB) {
        return timeA - timeB
      }
      const totalA = a.over_under || (a.home_implied_total + a.away_implied_total) || 0
      const totalB = b.over_under || (b.home_implied_total + b.away_implied_total) || 0
      return totalB - totalA
    })
  }, [vegasData, searchQuery, teamFilter, rosterPlayersByTeam])

  // Filtered Props
  const filteredProps = useMemo(() => {
    let list = propsData
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      list = list.filter(
        (p) =>
          p.player_name.toLowerCase().includes(q) ||
          p.team.toLowerCase().includes(q) ||
          p.opponent.toLowerCase().includes(q)
      )
    }
    if (propsPosFilter !== 'ALL') {
      list = list.filter((p) => p.position === propsPosFilter)
    }
    return list
  }, [propsData, searchQuery, propsPosFilter])

  // Copy slate summary to clipboard
  const handleCopySlateSummary = () => {
    if (!vegasData) return
    const lines = [
      `NFL Week ${selectedWeek} Vegas Betting Odds & Implied Totals`,
      `Slate Games: ${vegasData.total_games || vegasData.games.length} | Shootouts: ${slateKpis.shootoutCount}`,
      '--------------------------------------------------',
      'TEAM IMPLIED TOTALS RANKINGS:',
    ]

    vegasData.team_rankings.forEach((t) => {
      const favText = t.is_favorite ? 'FAV' : 'DOG'
      lines.push(
        `#${t.rank.toString().padStart(2, '0')} ${t.pro_team.padEnd(3)}: ${t.implied_total.toFixed(1)} pts (${(t.implied_total / 7).toFixed(1)} TDs) vs ${t.opponent} [${favText} | O/U ${t.over_under.toFixed(1)}]`
      )
    })

    lines.push('\nSCHEDULE SLATE LINES:')
    vegasData.games.forEach((g) => {
      lines.push(
        `${g.away_team} @ ${g.home_team} | Total: ${g.over_under.toFixed(1)} | Line: ${g.favorite_team} -${g.spread_magnitude.toFixed(1)} | Implied: ${g.away_team} ${g.away_implied_total.toFixed(1)} - ${g.home_implied_total.toFixed(1)} ${g.home_team}`
      )
    })

    navigator.clipboard.writeText(lines.join('\n')).then(() => {
      setCopiedSlate(true)
      setTimeout(() => setCopiedSlate(false), 2500)
    })
  }

  // Format date helper (Mountain Daylight Time MDT)
  const formatKickoff = (dateStr: string) => {
    return formatToMDT(dateStr)
  }

  // Render script badge helper
  const renderScriptBadge = (script: string, label: string) => {
    switch (script) {
      case 'SCORING_BONANZA':
        return <span className="pill emerald" style={{ fontSize: '11px', fontWeight: 800 }}>⚡ Scoring Bonanza</span>
      case 'SHOOTOUT':
        return <span className="pill amber" style={{ fontSize: '11px', fontWeight: 800 }}>🔥 {label && label !== 'SHOOTOUT' ? label : 'Shootout'}</span>
      case 'FAVORITE_RUN_FUNNEL':
        return <span className="pill emerald" style={{ fontSize: '11px', fontWeight: 700 }}>🏃 Run Funnel</span>
      case 'UNDERDOG_PASS_FUNNEL':
        return <span className="pill cyan" style={{ fontSize: '11px', fontWeight: 700 }}>📈 Trailing Pass</span>
      case 'DEFENSIVE_SLUGFEST':
        return <span className="pill rose" style={{ fontSize: '11px', fontWeight: 700 }}>🛡️ Defensive Slugfest</span>
      default:
        return <span className="pill zinc" style={{ fontSize: '11px' }}>⚖️ Balanced</span>
    }
  }

  return (
    <div className="vegas-dashboard-container">
      {/* 1. TOP HEADER & WEEK SELECTION BAR */}
      <div className="vegas-header-bar">
        <div className="vegas-header-left">
          <div className="vegas-brand-icon">🎲</div>
          <div>
            <div className="vegas-header-title-row">
              <h2 className="vegas-header-title">Vegas Odds, Spreads & Team Implied Totals</h2>
              <span className="pill cyan" style={{ fontSize: '11px', fontWeight: 700 }}>
                DraftKings Sportsbook Consensus
              </span>
              <span className="pill purple" style={{ fontSize: '11px' }}>
                Season 2026
              </span>
            </div>
            <p className="vegas-header-subtitle">
              Live sportsbook betting markets, implied team touchdown volumes, pace intelligence, and roster matchup exposures.
            </p>
          </div>
        </div>

        <div className="vegas-header-actions">
          {/* Week Selector Pills */}
          <div className="vegas-week-selector">
            <span className="vegas-week-label">Slate Week:</span>
            <div className="vegas-week-pills">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18].map((w) => (
                <button
                  key={w}
                  type="button"
                  className={`vegas-week-btn ${selectedWeek === w ? 'active' : ''}`}
                  onClick={() => setSelectedWeek(w)}
                >
                  W{w}
                  {currentWeek === w && <span className="vegas-current-dot" title="Current Week" />}
                </button>
              ))}
            </div>
          </div>

          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleCopySlateSummary}
            title="Copy slate betting lines to clipboard"
          >
            {copiedSlate ? '✓ Copied to Clipboard!' : '📋 Copy Slate Summary'}
          </button>

          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => loadVegasForWeek(selectedWeek)}
            disabled={isLoadingVegas}
          >
            {isLoadingVegas ? '⏳ Loading...' : '🔄 Refresh Odds'}
          </button>
        </div>
      </div>

      {/* 2. HERO KPI BANNER */}
      <div className="vegas-kpi-banner">
        <div className="vegas-kpi-card">
          <span className="vegas-kpi-label">Weekly Slate Games</span>
          <div className="vegas-kpi-value-row">
            <span className="vegas-kpi-number">{slateKpis.totalGames}</span>
            <span className="pill cyan" style={{ fontSize: '10.5px' }}>NFL Matchups</span>
          </div>
          <span className="vegas-kpi-sub">Official schedule & lines</span>
        </div>

        <div className="vegas-kpi-card highlight-amber">
          <span className="vegas-kpi-label">Projected Shootouts</span>
          <div className="vegas-kpi-value-row">
            <span className="vegas-kpi-number" style={{ color: 'var(--accent-amber)' }}>
              🔥 {slateKpis.shootoutCount}
            </span>
            <span className="pill amber" style={{ fontSize: '10px' }}>O/U ≥ 47.5 & Close</span>
          </div>
          <span className="vegas-kpi-sub">High volume, game-stack upside</span>
        </div>

        <div className="vegas-kpi-card highlight-emerald">
          <span className="vegas-kpi-label">Highest Implied Total</span>
          <div className="vegas-kpi-value-row">
            {slateKpis.highestTeam ? (
              <>
                <NFLTeamLogo team={slateKpis.highestTeam.pro_team} size={28} />
                <span className="vegas-kpi-number" style={{ color: 'var(--accent-emerald)' }}>
                  {slateKpis.highestTeam.implied_total.toFixed(1)}
                </span>
                <span className="pill emerald" style={{ fontSize: '11px', fontWeight: 800 }}>
                  {slateKpis.highestTeam.pro_team}
                </span>
              </>
            ) : (
              <span className="vegas-kpi-number">--</span>
            )}
          </div>
          <span className="vegas-kpi-sub">
            {slateKpis.highestTeam
              ? `~${(slateKpis.highestTeam.implied_total / 7).toFixed(1)} projected team TDs`
              : 'Implied ceiling'}
          </span>
        </div>

        <div className="vegas-kpi-card highlight-rose">
          <span className="vegas-kpi-label">Lowest Implied Total</span>
          <div className="vegas-kpi-value-row">
            {slateKpis.lowestTeam ? (
              <>
                <NFLTeamLogo team={slateKpis.lowestTeam.pro_team} size={28} />
                <span className="vegas-kpi-number" style={{ color: 'var(--accent-rose)' }}>
                  {slateKpis.lowestTeam.implied_total.toFixed(1)}
                </span>
                <span className="pill rose" style={{ fontSize: '11px', fontWeight: 800 }}>
                  {slateKpis.lowestTeam.pro_team}
                </span>
              </>
            ) : (
              <span className="vegas-kpi-number">--</span>
            )}
          </div>
          <span className="vegas-kpi-sub">
            {slateKpis.lowestTeam
              ? `Touchdown Desert vs ${slateKpis.lowestTeam.opponent}`
              : 'Defensive suppression'}
          </span>
        </div>

        <div className="vegas-kpi-card">
          <span className="vegas-kpi-label">Slate Average Total</span>
          <div className="vegas-kpi-value-row">
            <span className="vegas-kpi-number" style={{ color: 'var(--accent-cyan)' }}>
              {slateKpis.avgTotal.toFixed(1)}
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>pts/game</span>
          </div>
          <span className="vegas-kpi-sub">League scoring baseline</span>
        </div>

        <div className="vegas-kpi-card highlight-purple">
          <span className="vegas-kpi-label">My Roster Exposure</span>
          <div className="vegas-kpi-value-row">
            <span className="vegas-kpi-number" style={{ color: 'var(--accent-purple)' }}>
              ⭐ {slateKpis.myRosterGamesCount}
            </span>
            <span className="pill purple" style={{ fontSize: '10px' }}>Games with My Players</span>
          </div>
          <span className="vegas-kpi-sub">Fantasy lineup investment</span>
        </div>
      </div>

      {/* 3. SUBVIEW NAVIGATION PILLS & FILTER BAR */}
      <div className="vegas-controls-row">
        <div className="vegas-subview-pills">
          <button
            type="button"
            className={`vegas-subview-pill ${activeSubView === 'totals' ? 'active' : ''}`}
            onClick={() => setActiveSubView('totals')}
          >
            📊 All 32 Team Implied Totals
            <span className="vegas-pill-badge">{vegasData?.team_rankings.length || 32}</span>
          </button>

          <button
            type="button"
            className={`vegas-subview-pill ${activeSubView === 'schedule' ? 'active' : ''}`}
            onClick={() => setActiveSubView('schedule')}
          >
            🏈 Game Slate Schedule & Lines
            <span className="vegas-pill-badge">{vegasData?.games.length || 0}</span>
          </button>

          <button
            type="button"
            className={`vegas-subview-pill ${activeSubView === 'matrix' ? 'active' : ''}`}
            onClick={() => setActiveSubView('matrix')}
          >
            ⚡ Shootout & Gamescript Matrix
          </button>

          <button
            type="button"
            className={`vegas-subview-pill ${activeSubView === 'props' ? 'active' : ''}`}
            onClick={() => setActiveSubView('props')}
          >
            🎯 Sportsbook Player Props
            <span className="vegas-pill-badge">{propsData.length}</span>
          </button>
        </div>

        {/* Search & Team Filter */}
        <div className="vegas-filter-group">
          <input
            type="text"
            className="input-search"
            placeholder="Search teams, matchups, players..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: '220px', padding: '7px 12px', fontSize: '12.5px' }}
          />

          {activeSubView === 'totals' && (
            <div className="vegas-quick-filters">
              <button
                type="button"
                className={`pill-filter ${teamFilter === 'ALL' ? 'active' : ''}`}
                onClick={() => setTeamFilter('ALL')}
              >
                All 32
              </button>
              <button
                type="button"
                className={`pill-filter ${teamFilter === 'HIGH' ? 'active' : ''}`}
                onClick={() => setTeamFilter('HIGH')}
              >
                🔥 High (≥24)
              </button>
              <button
                type="button"
                className={`pill-filter ${teamFilter === 'LOW' ? 'active' : ''}`}
                onClick={() => setTeamFilter('LOW')}
              >
                ⚠️ Low (&lt;21)
              </button>
              <button
                type="button"
                className={`pill-filter ${teamFilter === 'FAVORITES' ? 'active' : ''}`}
                onClick={() => setTeamFilter('FAVORITES')}
              >
                Favorites
              </button>
              <button
                type="button"
                className={`pill-filter ${teamFilter === 'UNDERDOGS' ? 'active' : ''}`}
                onClick={() => setTeamFilter('UNDERDOGS')}
              >
                Underdogs
              </button>
              <button
                type="button"
                className={`pill-filter ${teamFilter === 'ROSTER' ? 'active' : ''}`}
                onClick={() => setTeamFilter('ROSTER')}
              >
                ⭐ My Roster ({slateKpis.myRosterGamesCount})
              </button>
            </div>
          )}

          {activeSubView === 'props' && (
            <div className="vegas-quick-filters">
              {['ALL', 'QB', 'RB', 'WR', 'TE'].map((pos) => (
                <button
                  key={pos}
                  type="button"
                  className={`pill-filter ${propsPosFilter === pos ? 'active' : ''}`}
                  onClick={() => setPropsPosFilter(pos)}
                >
                  {pos}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 4. MAIN CONTENT AREA */}
      {isLoadingVegas ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>🎲</div>
          <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
            Fetching Vegas Betting Lines for Week {selectedWeek}...
          </div>
          <div style={{ fontSize: '13px' }}>Loading spreads, game over/unders, and implied team totals</div>
        </div>
      ) : (
        <>
          {/* ================================================================= */}
          {/* VIEW 1: ALL 32 TEAM IMPLIED TOTALS LEADERBOARD                     */}
          {/* ================================================================= */}
          {activeSubView === 'totals' && (
            <div className="vegas-totals-container">
              <div className="vegas-totals-header-legend">
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span>NFL Week {selectedWeek} Team Implied Totals Leaderboard</span>
                    <span className="pill cyan" style={{ fontSize: '11px' }}>
                      {filteredTeamRankings.length} Teams Ranked
                    </span>
                  </h3>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    Calculated from DraftKings game over/under and point spread: Implied Total = (O/U / 2) ± (Spread / 2).
                  </p>
                </div>

                <div className="vegas-color-legend">
                  <span className="legend-item">
                    <span className="legend-dot emerald" /> ≥25.0 pts (TD Bonanza)
                  </span>
                  <span className="legend-item">
                    <span className="legend-dot cyan" /> 23.0 - 24.9 pts (Elevated)
                  </span>
                  <span className="legend-item">
                    <span className="legend-dot amber" /> 21.0 - 22.9 pts (Neutral)
                  </span>
                  <span className="legend-item">
                    <span className="legend-dot rose" /> &lt;21.0 pts (TD Desert)
                  </span>
                </div>
              </div>

              {filteredTeamRankings.length === 0 ? (
                <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  No teams match your search or filter criteria.
                </div>
              ) : (
                <div className="vegas-table-wrapper">
                  <table className="vegas-totals-table">
                    <thead>
                      <tr>
                        <th style={{ width: '60px', textAlign: 'center' }}>Rank</th>
                        <th style={{ width: '220px' }}>NFL Team</th>
                        <th style={{ width: '260px' }}>Implied Points & Ceiling Meter</th>
                        <th style={{ width: '120px', textAlign: 'center' }}>Exp. TDs</th>
                        <th style={{ width: '195px' }}>Matchup & Spread</th>
                        <th style={{ width: '90px', textAlign: 'center' }}>Game O/U</th>
                        <th style={{ width: '175px' }}>Environment Script</th>
                        <th>My Fantasy Roster Exposure</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredTeamRankings.map((team) => {
                        const teamMeta = NFL_TEAMS_INFO[team.pro_team]
                        const myPlayers = rosterPlayersByTeam.get(team.pro_team) || []
                        const maxCeiling = 32.0
                        const pctBar = Math.min(100, Math.max(15, (team.implied_total / maxCeiling) * 100))

                        let barColor = 'var(--accent-amber)'
                        let tagClass = 'amber'
                        if (team.implied_total >= 25.0) {
                          barColor = 'var(--accent-emerald)'
                          tagClass = 'emerald'
                        } else if (team.implied_total >= 23.0) {
                          barColor = 'var(--accent-cyan)'
                          tagClass = 'cyan'
                        } else if (team.implied_total < 21.0) {
                          barColor = 'var(--accent-rose)'
                          tagClass = 'rose'
                        }

                        const expTds = (team.implied_total / 7.0).toFixed(1)

                        return (
                          <tr key={team.pro_team} className={myPlayers.length > 0 ? 'row-rostered' : ''}>
                            {/* Rank */}
                            <td style={{ textAlign: 'center' }}>
                              <span
                                className={`vegas-rank-badge ${team.rank <= 5 ? 'top-rank' : team.rank >= 28 ? 'bottom-rank' : ''}`}
                              >
                                #{team.rank}
                              </span>
                            </td>

                            {/* Team */}
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                <NFLTeamLogo team={team.pro_team} size={30} />
                                <div>
                                  <div style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <span>{teamMeta ? `${teamMeta.city} ${teamMeta.name}` : team.pro_team}</span>
                                    <span className="vegas-team-pill-badge" style={{ fontSize: '10px', padding: '1px 5px' }}>{team.pro_team}</span>
                                  </div>
                                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                                    {team.is_home ? '🏠 Home' : '✈️ Road'} • {teamMeta?.conference || 'NFL'}
                                  </div>
                                </div>
                              </div>
                            </td>

                            {/* Implied Points Meter */}
                            <td>
                              <div className="vegas-meter-cell">
                                <div className="vegas-meter-val-row">
                                  <span className="vegas-implied-pts" style={{ color: barColor }}>
                                    {team.implied_total.toFixed(2)} pts
                                  </span>
                                  <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                                    {pctBar.toFixed(0)}% ceiling
                                  </span>
                                </div>
                                <div className="vegas-progress-track">
                                  <div
                                    className="vegas-progress-bar"
                                    style={{ width: `${pctBar}%`, backgroundColor: barColor }}
                                  />
                                </div>
                              </div>
                            </td>

                            {/* Expected TDs */}
                            <td style={{ textAlign: 'center' }}>
                              <div className={`vegas-tds-badge ${tagClass}`}>
                                <span className="tds-val">~{expTds}</span>
                                <span className="tds-lbl">TDs</span>
                              </div>
                            </td>

                            {/* Matchup & Spread */}
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
                                <span style={{ fontSize: '13px', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                                  <span>{team.is_home ? 'vs' : '@'}</span>
                                  <NFLTeamLogo team={team.opponent} size={18} />
                                  <span>{team.opponent}</span>
                                </span>
                                {team.spread_diff !== undefined && team.spread_diff !== 0 && (
                                  <span
                                    className={`pill ${team.is_favorite ? 'emerald' : 'zinc'}`}
                                    style={{ fontSize: '10px', padding: '1px 6px', fontWeight: 700 }}
                                    title={team.is_favorite ? `Favored by ${Math.abs(team.spread_diff).toFixed(1)} pts` : `Underdog by ${Math.abs(team.spread_diff).toFixed(1)} pts`}
                                  >
                                    {team.spread_diff > 0 ? `+${team.spread_diff.toFixed(1)} pts` : `${team.spread_diff.toFixed(1)} pts`}
                                  </span>
                                )}
                              </div>
                              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                                Opp Implied:{' '}
                                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-secondary)' }}>
                                  {team.opponent_implied_total != null ? `${team.opponent_implied_total.toFixed(2)} pts` : '--'}
                                </span>
                              </div>
                              <div style={{ fontSize: '10.5px', color: team.is_favorite ? 'var(--accent-emerald)' : 'var(--text-muted)', marginTop: '1px', fontWeight: team.is_favorite ? 600 : 400 }}>
                                {team.is_favorite ? '⭐ Favorite' : 'Underdog'}
                              </div>
                            </td>

                            {/* Game O/U */}
                            <td style={{ textAlign: 'center' }}>
                              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '13px' }}>
                                {team.over_under.toFixed(1)}
                              </span>
                            </td>

                            {/* Environment Script */}
                            <td>
                              {renderScriptBadge(team.game_script, team.game_script)}
                            </td>

                            {/* My Roster Exposure */}
                            <td>
                              {myPlayers.length === 0 ? (
                                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>No players rostered</span>
                              ) : (
                                <div className="vegas-roster-exposure-list">
                                  {myPlayers.map((p) => (
                                    <span
                                      key={p.id}
                                      className={`pill ${p.isStarter ? 'emerald' : 'zinc'}`}
                                      style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                                    >
                                      <span>{p.name}</span>
                                      <span style={{ fontSize: '9px', opacity: 0.8 }}>({p.pos})</span>
                                      <span style={{ fontWeight: 800, fontSize: '9px' }}>
                                        {p.isStarter ? 'START' : 'BENCH'}
                                      </span>
                                    </span>
                                  ))}
                                </div>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ================================================================= */}
          {/* VIEW 2: GAME SCHEDULE SLATE & LINES                               */}
          {/* ================================================================= */}
          {activeSubView === 'schedule' && (
            <div className="vegas-schedule-grid">
              {filteredGames.length === 0 ? (
                <div className="card" style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  No games found matching your search.
                </div>
              ) : (
                filteredGames.map((game) => {
                  const hasRoster = game.user_roster_exposure.length > 0
                  const homeMeta = NFL_TEAMS_INFO[game.home_team]
                  const awayMeta = NFL_TEAMS_INFO[game.away_team]

                  return (
                    <div
                      key={game.game_id}
                      className={`vegas-game-card ${hasRoster ? 'card-has-roster' : ''}`}
                    >
                      {/* Matchup Header Banner */}
                      <div className="vegas-game-card-header">
                        <div>
                          <div className="vegas-kickoff-time">
                            📅 {formatKickoff(game.game_date)}
                          </div>
                          <div className="vegas-venue-title">
                            {game.venue_name}
                            {game.is_dome && (
                              <span className="pill cyan" style={{ fontSize: '9.5px', marginLeft: '6px' }}>
                                🏟️ Dome
                              </span>
                            )}
                          </div>
                        </div>

                        <div>{renderScriptBadge(game.game_script, game.game_script_label)}</div>
                      </div>

                      {/* Teams & Implied Score Board */}
                      <div className="vegas-matchup-scoreboard">
                        {/* Away Team */}
                        <div className="vegas-team-col away">
                          <NFLTeamLogo team={game.away_team} size={44} style={{ marginBottom: '4px' }} />
                          <div className="vegas-team-code">{game.away_team}</div>
                          <div className="vegas-team-fullname">
                            {awayMeta ? `${awayMeta.city} ${awayMeta.name}` : game.away_team}
                          </div>
                          <div className="vegas-team-implied-score">
                            <span className="score-label">Away Implied:</span>
                            <span className="score-number">{game.away_implied_total.toFixed(1)} pts</span>
                          </div>
                          <div className="vegas-team-td-estimate">
                            ~{(game.away_implied_total / 7).toFixed(1)} TDs
                          </div>
                        </div>

                        {/* VS Divider & Odds Lines */}
                        <div className="vegas-vs-divider">
                          <span className="vs-badge">VS</span>
                          <div className="vegas-line-pill">
                            Line: <strong>{game.favorite_team} -{game.spread_magnitude.toFixed(1)}</strong>
                          </div>
                          <div className="vegas-ou-pill">
                            O/U: <strong>{game.over_under.toFixed(1)}</strong>
                          </div>
                        </div>

                        {/* Home Team */}
                        <div className="vegas-team-col home">
                          <NFLTeamLogo team={game.home_team} size={44} style={{ marginBottom: '4px' }} />
                          <div className="vegas-team-code">{game.home_team}</div>
                          <div className="vegas-team-fullname">
                            {homeMeta ? `${homeMeta.city} ${homeMeta.name}` : game.home_team}
                          </div>
                          <div className="vegas-team-implied-score">
                            <span className="score-label">Home Implied:</span>
                            <span className="score-number">{game.home_implied_total.toFixed(1)} pts</span>
                          </div>
                          <div className="vegas-team-td-estimate">
                            ~{(game.home_implied_total / 7).toFixed(1)} TDs
                          </div>
                        </div>
                      </div>

                      {/* Pace & Game Environment Stats */}
                      <div className="vegas-pace-strip">
                        <div className="pace-metric">
                          <span className="label">Projected Plays:</span>
                          <span className="val">{game.expected_total_plays} plays</span>
                        </div>
                        <div className="pace-divider" />
                        <div className="pace-metric">
                          <span className="label">Pace Tempo:</span>
                          <span className="val" style={{ color: 'var(--accent-cyan)' }}>
                            {game.pace_index}
                          </span>
                        </div>
                        <div className="pace-divider" />
                        <div className="pace-metric" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span className="label">Favorite:</span>
                          <NFLTeamLogo team={game.favorite_team} size={16} />
                          <span className="val" style={{ color: 'var(--accent-emerald)' }}>
                            {game.favorite_team}
                          </span>
                        </div>
                      </div>

                      {/* Action Network / ETR Tactical Takeaway */}
                      <div className="vegas-tactical-takeaway">
                        <div className="takeaway-badge">💡 Fantasy Game Script Impact</div>
                        <p className="takeaway-text">{game.tactical_advice}</p>
                      </div>

                      {/* My Roster Exposure in this Game */}
                      {hasRoster && (
                        <div className="vegas-card-roster-exposure">
                          <div className="roster-exposure-title">
                            ⭐ My Fantasy Roster in this Matchup ({game.user_roster_exposure.length} players):
                          </div>
                          <div className="roster-exposure-chips">
                            {game.user_roster_exposure.map((p) => (
                              <div
                                key={p.player_id}
                                className={`roster-player-chip ${p.is_starter ? 'is-starter' : 'is-bench'}`}
                              >
                                <div className="chip-name-row">
                                  <span className="player-name">{p.full_name}</span>
                                  <span className="player-pos">({p.position})</span>
                                </div>
                                <div className="chip-status-row">
                                  <span className={`status-tag ${p.is_starter ? 'start' : 'bench'}`}>
                                    {p.is_starter ? 'STARTER' : 'BENCH'}
                                  </span>
                                  <span className="proj-pts">{p.projected_points.toFixed(1)} proj pts</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })
              )}
            </div>
          )}

          {/* ================================================================= */}
          {/* VIEW 3: SHOOTOUT & GAMESCRIPT MATRIX                              */}
          {/* ================================================================= */}
          {activeSubView === 'matrix' && (
            <div className="vegas-matrix-container">
              {/* Category 1: Shootouts */}
              <div className="vegas-matrix-section">
                <div className="vegas-matrix-header amber">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '20px' }}>🔥</span>
                    <div>
                      <h4 style={{ fontSize: '15px', fontWeight: 800 }}>High-Ceiling Shootout Environments</h4>
                      <p style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                        Over/Under ≥ 47.5 pts with tight spreads (≤ 4.5 pts). Maximum tempo, multi-TD ceiling, ideal DFS stacks.
                      </p>
                    </div>
                  </div>
                  <span className="pill amber" style={{ fontSize: '11px', fontWeight: 800 }}>
                    {vegasData?.games.filter((g) => g.game_script === 'SHOOTOUT').length || 0} Games
                  </span>
                </div>

                <div className="vegas-matrix-grid">
                  {vegasData?.games.filter((g) => g.game_script === 'SHOOTOUT').map((g) => (
                    <div key={g.game_id} className="vegas-matrix-card amber-border">
                      <div className="matrix-card-title">
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                          <NFLTeamLogo team={g.away_team} size={20} />
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>@</span>
                          <NFLTeamLogo team={g.home_team} size={20} />
                          <span style={{ marginLeft: '2px', fontWeight: 700 }}>{g.game_name}</span>
                        </div>
                        <span className="pill amber" style={{ fontSize: '10px' }}>O/U {g.over_under.toFixed(1)}</span>
                      </div>
                      <div className="matrix-card-details">
                        <span>Spread: {g.favorite_team} -{g.spread_magnitude.toFixed(1)}</span>
                        <span>Implied: {g.away_team} {g.away_implied_total.toFixed(1)} @ {g.home_implied_total.toFixed(1)} {g.home_team}</span>
                      </div>
                      <div className="matrix-card-tactical">{g.tactical_advice}</div>
                    </div>
                  ))}
                  {vegasData?.games.filter((g) => g.game_script === 'SHOOTOUT').length === 0 && (
                    <div className="card" style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                      No shootouts meet the O/U ≥ 47.5 threshold on this slate.
                    </div>
                  )}
                </div>
              </div>

              {/* Category 2: Positive Run Funnels */}
              <div className="vegas-matrix-section">
                <div className="vegas-matrix-header emerald">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '20px' }}>🏃</span>
                    <div>
                      <h4 style={{ fontSize: '15px', fontWeight: 800 }}>Positive Run Funnel Favorites</h4>
                      <p style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                        Favorites by ≥ 6.5 pts in sub-45 totals. Heavy 2nd-half clock-killing carries for primary bellcow RBs.
                      </p>
                    </div>
                  </div>
                  <span className="pill emerald" style={{ fontSize: '11px', fontWeight: 800 }}>
                    {vegasData?.games.filter((g) => g.game_script === 'FAVORITE_RUN_FUNNEL').length || 0} Games
                  </span>
                </div>

                <div className="vegas-matrix-grid">
                  {vegasData?.games.filter((g) => g.game_script === 'FAVORITE_RUN_FUNNEL').map((g) => (
                    <div key={g.game_id} className="vegas-matrix-card emerald-border">
                      <div className="matrix-card-title">
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                          <NFLTeamLogo team={g.away_team} size={20} />
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>@</span>
                          <NFLTeamLogo team={g.home_team} size={20} />
                          <span style={{ marginLeft: '2px', fontWeight: 700 }}>{g.game_name}</span>
                        </div>
                        <span className="pill emerald" style={{ fontSize: '10px' }}>{g.favorite_team} -{g.spread_magnitude.toFixed(1)}</span>
                      </div>
                      <div className="matrix-card-details">
                        <span>O/U: {g.over_under.toFixed(1)}</span>
                        <span>Fav Implied: {Math.max(g.home_implied_total, g.away_implied_total).toFixed(1)} pts</span>
                      </div>
                      <div className="matrix-card-tactical">{g.tactical_advice}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Category 3: Trailing Pass Funnels */}
              <div className="vegas-matrix-section">
                <div className="vegas-matrix-header cyan">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '20px' }}>📈</span>
                    <div>
                      <h4 style={{ fontSize: '15px', fontWeight: 800 }}>High-Volume Trailing Pass Scripts</h4>
                      <p style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                        Heavy underdogs (+6.5 or greater) projected to chase points. PPR dump-offs for receiving RBs & slot WRs.
                      </p>
                    </div>
                  </div>
                  <span className="pill cyan" style={{ fontSize: '11px', fontWeight: 800 }}>
                    {vegasData?.games.filter((g) => g.game_script === 'UNDERDOG_PASS_FUNNEL').length || 0} Games
                  </span>
                </div>

                <div className="vegas-matrix-grid">
                  {vegasData?.games.filter((g) => g.game_script === 'UNDERDOG_PASS_FUNNEL').map((g) => (
                    <div key={g.game_id} className="vegas-matrix-card cyan-border">
                      <div className="matrix-card-title">
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                          <NFLTeamLogo team={g.away_team} size={20} />
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>@</span>
                          <NFLTeamLogo team={g.home_team} size={20} />
                          <span style={{ marginLeft: '2px', fontWeight: 700 }}>{g.game_name}</span>
                        </div>
                        <span className="pill cyan" style={{ fontSize: '10px' }}>Dog: {g.underdog_team} (+{g.spread_magnitude.toFixed(1)})</span>
                      </div>
                      <div className="matrix-card-details">
                        <span>O/U: {g.over_under.toFixed(1)}</span>
                        <span>Pass Tempo: {g.pace_index}</span>
                      </div>
                      <div className="matrix-card-tactical">{g.tactical_advice}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Category 4: Defensive Slugfests */}
              <div className="vegas-matrix-section">
                <div className="vegas-matrix-header rose">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '20px' }}>🛡️</span>
                    <div>
                      <h4 style={{ fontSize: '15px', fontWeight: 800 }}>Low-Scoring Defensive Slugfests</h4>
                      <p style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                        Over/Under ≤ 40.5 pts. Suppressed skill player ceiling, turnover equity, premier spots for streaming D/STs.
                      </p>
                    </div>
                  </div>
                  <span className="pill rose" style={{ fontSize: '11px', fontWeight: 800 }}>
                    {vegasData?.games.filter((g) => g.game_script === 'DEFENSIVE_SLUGFEST').length || 0} Games
                  </span>
                </div>

                <div className="vegas-matrix-grid">
                  {vegasData?.games.filter((g) => g.game_script === 'DEFENSIVE_SLUGFEST').map((g) => (
                    <div key={g.game_id} className="vegas-matrix-card rose-border">
                      <div className="matrix-card-title">
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                          <NFLTeamLogo team={g.away_team} size={20} />
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>@</span>
                          <NFLTeamLogo team={g.home_team} size={20} />
                          <span style={{ marginLeft: '2px', fontWeight: 700 }}>{g.game_name}</span>
                        </div>
                        <span className="pill rose" style={{ fontSize: '10px' }}>O/U {g.over_under.toFixed(1)}</span>
                      </div>
                      <div className="matrix-card-details">
                        <span>Line: {g.favorite_team} -{g.spread_magnitude.toFixed(1)}</span>
                        <span>Pace: {g.pace_index} ({g.expected_total_plays} plays)</span>
                      </div>
                      <div className="matrix-card-tactical">{g.tactical_advice}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ================================================================= */}
          {/* VIEW 4: SPORTSBOOK PLAYER PROPS                                   */}
          {/* ================================================================= */}
          {activeSubView === 'props' && (
            <div className="vegas-props-container">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: 700 }}>
                    Vegas Sportsbook Player Propositions & Implied Fantasy Points
                  </h3>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    Receptions Over/Under, Anytime Touchdown implied probabilities, yardage lines, and market-synthesized PPR output.
                  </p>
                </div>
                <span className="pill emerald" style={{ fontSize: '11px' }}>
                  {filteredProps.length} Key Skill Players
                </span>
              </div>

              {isLoadingProps ? (
                <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  Loading sportsbook proposition markets...
                </div>
              ) : filteredProps.length === 0 ? (
                <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  No player propositions found matching filter.
                </div>
              ) : (
                <div className="vegas-props-grid">
                  {filteredProps.map((p) => {
                    const isRostered = userRosterTeamPids.has(p.player_id)
                    const tdPct = Math.round(p.anytime_td_prob * 100)

                    return (
                      <div
                        key={p.player_id}
                        className={`vegas-prop-card ${isRostered ? 'prop-rostered' : ''}`}
                      >
                        <div className="prop-card-header">
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span style={{ fontWeight: 800, fontSize: '15px' }}>{p.player_name}</span>
                              <span className="pill zinc" style={{ fontSize: '10px' }}>{p.position}</span>
                              {isRostered && (
                                <span className="pill purple" style={{ fontSize: '9px', fontWeight: 800 }}>MY ROSTER</span>
                              )}
                            </div>
                            <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', marginTop: '3px', display: 'flex', alignItems: 'center', gap: '5px' }}>
                              <NFLTeamLogo team={p.team} size={16} />
                              <span>{p.team}</span>
                              <span>vs</span>
                              <NFLTeamLogo team={p.opponent} size={16} />
                              <span>{p.opponent}</span>
                            </div>
                          </div>

                          <span className={`pill ${p.vegas_grade_color || 'cyan'}`} style={{ fontSize: '10px', fontWeight: 700 }}>
                            {p.vegas_grade_label || p.vegas_grade}
                          </span>
                        </div>

                        {/* Implied PPR Points Bar */}
                        <div className="prop-implied-bar">
                          <span className="prop-implied-label">Market Implied PPR:</span>
                          <span className="prop-implied-value" style={{ color: 'var(--accent-emerald)' }}>
                            {p.implied_ppr_points.toFixed(1)} pts
                          </span>
                        </div>

                        {/* Props Lines Grid */}
                        <div className="prop-lines-grid">
                          {/* Receptions O/U */}
                          {p.receptions_ou != null && (
                            <div className="prop-line-cell">
                              <span className="line-label">Receptions O/U</span>
                              <span className="line-val">{p.receptions_ou.toFixed(1)} rec</span>
                            </div>
                          )}

                          {/* Anytime TD */}
                          <div className="prop-line-cell">
                            <span className="line-label">Anytime TD Odds</span>
                            <span className="line-val" style={{ color: tdPct >= 50 ? 'var(--accent-emerald)' : 'inherit' }}>
                              {tdPct}% ({p.anytime_td_odds != null && p.anytime_td_odds > 0 ? `+${p.anytime_td_odds}` : p.anytime_td_odds})
                            </span>
                          </div>

                          {/* Yardage Line */}
                          {p.position === 'QB' && p.pass_yards_ou != null && (
                            <div className="prop-line-cell">
                              <span className="line-label">Pass Yds O/U</span>
                              <span className="line-val">{p.pass_yards_ou.toFixed(1)} yds</span>
                            </div>
                          )}

                          {p.position === 'RB' && p.rush_yards_ou != null && (
                            <div className="prop-line-cell">
                              <span className="line-label">Rush Yds O/U</span>
                              <span className="line-val">{p.rush_yards_ou.toFixed(1)} yds</span>
                            </div>
                          )}

                          {(p.position === 'WR' || p.position === 'TE') && p.rec_yards_ou != null && (
                            <div className="prop-line-cell">
                              <span className="line-label">Rec Yds O/U</span>
                              <span className="line-val">{p.rec_yards_ou.toFixed(1)} yds</span>
                            </div>
                          )}

                          {p.rush_att_ou != null && (
                            <div className="prop-line-cell">
                              <span className="line-label">Carries O/U</span>
                              <span className="line-val">{p.rush_att_ou.toFixed(1)} att</span>
                            </div>
                          )}
                        </div>

                        {/* Takeaway */}
                        {p.vegas_takeaway && (
                          <div className="prop-takeaway-box">
                            {p.vegas_takeaway}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
