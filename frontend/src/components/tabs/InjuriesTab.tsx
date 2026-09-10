import React, { useState, useMemo } from 'react'
import type { InjuryFeedResponse, TeamRosterResponse } from '../../types'
import { InjuryStatusPill } from '../shared/InjuryStatusPill'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'

export interface InjuriesTabProps {
  injuriesFeed: InjuryFeedResponse | null
  isLoadingInjuries: boolean
  onRefreshInjuries: (force?: boolean) => void
  teamRosterData?: TeamRosterResponse | null
  onSelectPlayerForCompare?: (playerId: number) => void
  onNavigateTab?: (tab: string) => void
}

export const InjuriesTab: React.FC<InjuriesTabProps> = ({
  injuriesFeed,
  isLoadingInjuries,
  onRefreshInjuries,
  teamRosterData,
  onSelectPlayerForCompare,
  onNavigateTab,
}) => {
  const [injurySearch, setInjurySearch] = useState<string>('')
  const [injuryPosFilter, setInjuryPosFilter] = useState<string>('ALL')
  const [injuryStatusFilter, setInjuryStatusFilter] = useState<string>('ALL')
  const [onlyMyRoster, setOnlyMyRoster] = useState<boolean>(false)
  const [onlyDecoyRisk, setOnlyDecoyRisk] = useState<boolean>(false)

  // Map user's roster players by ID and normalized full name for instantaneous lookups
  const rosterPlayerMap = useMemo(() => {
    const map = new Map<number | string, { isStarter: boolean; slotName: string | null }>()
    if (teamRosterData?.roster) {
      for (const p of teamRosterData.roster) {
        map.set(p.player_id, { isStarter: p.is_starter, slotName: p.slot_name })
        const norm = p.full_name.trim().toLowerCase()
        map.set(norm, { isStarter: p.is_starter, slotName: p.slot_name })
      }
    }
    return map
  }, [teamRosterData])

  const allInjuries = injuriesFeed?.injuries || []

  // KPI telemetry counts
  const kpis = useMemo(() => {
    let myRosterCount = 0
    let myStartersAtRisk = 0
    let decoyCount = 0
    let ruledOutCount = 0

    for (const inj of allInjuries) {
      const rosterInfo = rosterPlayerMap.get(inj.athlete_id) || rosterPlayerMap.get(inj.name.trim().toLowerCase())
      if (rosterInfo) {
        myRosterCount++
        if (rosterInfo.isStarter && (inj.is_out || inj.status.toUpperCase().includes('QUESTIONABLE'))) {
          myStartersAtRisk++
        }
      }
      if (inj.decoy_risk === 'HIGH' || inj.decoy_risk === 'MODERATE') {
        decoyCount++
      }
      if (inj.is_out) {
        ruledOutCount++
      }
    }

    return {
      total: allInjuries.length,
      myRosterCount,
      myStartersAtRisk,
      decoyCount,
      ruledOutCount,
    }
  }, [allInjuries, rosterPlayerMap])

  const filteredInjuries = useMemo(() => {
    return allInjuries.filter((inj) => {
      const rosterInfo = rosterPlayerMap.get(inj.athlete_id) || rosterPlayerMap.get(inj.name.trim().toLowerCase())

      if (onlyMyRoster && !rosterInfo) {
        return false
      }
      if (onlyDecoyRisk && !(inj.decoy_risk === 'HIGH' || inj.decoy_risk === 'MODERATE')) {
        return false
      }
      if (injurySearch) {
        const q = injurySearch.toLowerCase()
        const nameMatch = inj.name.toLowerCase().includes(q)
        const teamMatch = inj.team.toLowerCase().includes(q)
        const backupMatch = inj.backup_player_name?.toLowerCase().includes(q)
        if (!nameMatch && !teamMatch && !backupMatch) {
          return false
        }
      }
      if (injuryPosFilter !== 'ALL' && inj.position.toUpperCase() !== injuryPosFilter) {
        return false
      }
      if (injuryStatusFilter !== 'ALL') {
        if (injuryStatusFilter === 'OUT' && !inj.is_out) return false
        if (injuryStatusFilter === 'QUESTIONABLE' && !inj.status.toUpperCase().includes('QUESTIONABLE')) return false
        if (injuryStatusFilter === 'ACTIVE' && (inj.is_out || inj.status.toUpperCase().includes('QUESTIONABLE'))) return false
      }
      return true
    })
  }, [allInjuries, onlyMyRoster, onlyDecoyRisk, injurySearch, injuryPosFilter, injuryStatusFilter, rosterPlayerMap])

  return (
    <div className="card">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>🩺 Live 2026 NFL Injury Wire & Beneficiary Matrix</span>
            <span className="pill cyan" style={{ fontSize: '11px', fontWeight: 700 }}>
              Live Beat & Depth Chart Sync
            </span>
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13.5px', marginTop: '4px' }}>
            Official NFL designations, practice trajectory curve, decoy trap warnings, and depth chart next-man-up volume beneficiaries.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => onRefreshInjuries(true)}
          disabled={isLoadingInjuries}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
        >
          {isLoadingInjuries ? '⏳ Refreshing Live ESPN Data...' : '🔄 Refresh Live Feed'}
        </button>
      </div>

      {/* KPI Intelligence Strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '12px', marginTop: '16px', marginBottom: '20px' }}>
        <div className="vegas-kpi-card" style={{ padding: '12px 14px' }}>
          <span className="vegas-kpi-label">Official NFL Reports</span>
          <div className="vegas-kpi-value-row">
            <span className="vegas-kpi-number" style={{ fontSize: '20px' }}>{kpis.total}</span>
            <span className="pill zinc" style={{ fontSize: '10px' }}>Verified</span>
          </div>
          <span className="vegas-kpi-sub">All 32 franchises</span>
        </div>

        <div className={`vegas-kpi-card ${kpis.myStartersAtRisk > 0 ? 'highlight-rose' : 'highlight-purple'}`} style={{ padding: '12px 14px' }}>
          <span className="vegas-kpi-label">My Roster Affected</span>
          <div className="vegas-kpi-value-row">
            <span className="vegas-kpi-number" style={{ fontSize: '20px', color: kpis.myStartersAtRisk > 0 ? 'var(--accent-rose)' : 'var(--accent-purple)' }}>
              ⭐ {kpis.myRosterCount}
            </span>
            {kpis.myStartersAtRisk > 0 && (
              <span className="pill rose" style={{ fontSize: '10px', fontWeight: 800 }}>
                🚨 {kpis.myStartersAtRisk} Starter{kpis.myStartersAtRisk > 1 ? 's' : ''} at Risk
              </span>
            )}
          </div>
          <span className="vegas-kpi-sub">{kpis.myStartersAtRisk > 0 ? 'Urgent pivot required' : 'Lineup healthy'}</span>
        </div>

        <div className="vegas-kpi-card highlight-amber" style={{ padding: '12px 14px' }}>
          <span className="vegas-kpi-label">Decoy Trap Alerts</span>
          <div className="vegas-kpi-value-row">
            <span className="vegas-kpi-number" style={{ fontSize: '20px', color: 'var(--accent-amber)' }}>
              ⚠️ {kpis.decoyCount}
            </span>
            <span className="pill amber" style={{ fontSize: '10px' }}>Soft-Tissue</span>
          </div>
          <span className="vegas-kpi-sub">Hamstring / Groin / DNP</span>
        </div>

        <div className="vegas-kpi-card highlight-rose" style={{ padding: '12px 14px' }}>
          <span className="vegas-kpi-label">Confirmed Out / IR</span>
          <div className="vegas-kpi-value-row">
            <span className="vegas-kpi-number" style={{ fontSize: '20px', color: 'var(--accent-rose)' }}>
              🚨 {kpis.ruledOutCount}
            </span>
            <span className="pill rose" style={{ fontSize: '10px' }}>0.0 Proj Pts</span>
          </div>
          <span className="vegas-kpi-sub">Vacated touches available</span>
        </div>
      </div>

      {/* Filter Controls & Quick Toggles */}
      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '16px', alignItems: 'center' }}>
        <input
          type="text"
          placeholder="🔍 Search player, team, or next-up backup..."
          value={injurySearch}
          onChange={(e) => setInjurySearch(e.target.value)}
          className="select-dropdown"
          style={{ flex: '1', minWidth: '220px', cursor: 'text', fontSize: '13px' }}
        />

        {/* Quick Filter: My Roster Only */}
        <button
          type="button"
          className={`btn btn-sm ${onlyMyRoster ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setOnlyMyRoster(!onlyMyRoster)}
          style={
            onlyMyRoster
              ? { backgroundColor: '#8b5cf6', borderColor: '#8b5cf6', color: '#fff', fontWeight: 800 }
              : { border: '1px solid rgba(139, 92, 246, 0.4)', color: 'var(--text-primary)' }
          }
          title="Show only players on your fantasy team"
        >
          ⭐ My Roster Only {kpis.myRosterCount > 0 ? `(${kpis.myRosterCount})` : ''}
        </button>

        {/* Quick Filter: Decoy Risk Only */}
        <button
          type="button"
          className={`btn btn-sm ${onlyDecoyRisk ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setOnlyDecoyRisk(!onlyDecoyRisk)}
          style={
            onlyDecoyRisk
              ? { backgroundColor: '#f59e0b', borderColor: '#f59e0b', color: '#000', fontWeight: 800 }
              : { border: '1px solid rgba(245, 158, 11, 0.4)', color: 'var(--text-primary)' }
          }
          title="Show questionable players with soft-tissue re-injury risk"
        >
          ⚠️ Decoy Traps {kpis.decoyCount > 0 ? `(${kpis.decoyCount})` : ''}
        </button>

        <select
          className="select-dropdown"
          value={injuryPosFilter}
          onChange={(e) => setInjuryPosFilter(e.target.value)}
          style={{ fontSize: '13px' }}
        >
          <option value="ALL">All Positions</option>
          <option value="QB">QB</option>
          <option value="RB">RB</option>
          <option value="WR">WR</option>
          <option value="TE">TE</option>
          <option value="K">K</option>
          <option value="D/ST">D/ST</option>
        </select>

        <select
          className="select-dropdown"
          value={injuryStatusFilter}
          onChange={(e) => setInjuryStatusFilter(e.target.value)}
          style={{ fontSize: '13px' }}
        >
          <option value="ALL">All Statuses</option>
          <option value="OUT">Out / IR / Doubtful</option>
          <option value="QUESTIONABLE">Questionable</option>
          <option value="ACTIVE">Active</option>
        </select>
      </div>

      <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Showing {filteredInjuries.length} of {allInjuries.length} verified reports</span>
        {(onlyMyRoster || onlyDecoyRisk || injurySearch || injuryPosFilter !== 'ALL' || injuryStatusFilter !== 'ALL') && (
          <button
            type="button"
            className="btn btn-secondary btn-xs"
            onClick={() => {
              setOnlyMyRoster(false)
              setOnlyDecoyRisk(false)
              setInjurySearch('')
              setInjuryPosFilter('ALL')
              setInjuryStatusFilter('ALL')
            }}
            style={{ fontSize: '11px', padding: '2px 8px' }}
          >
            Reset Filters
          </button>
        )}
      </div>

      <div className="table-responsive">
        <table className="custom-table">
          <thead>
            <tr>
              <th style={{ minWidth: '180px' }}>Player & Roster Tag</th>
              <th style={{ minWidth: '110px' }}>Team & Pos</th>
              <th style={{ minWidth: '120px' }}>Official Status</th>
              <th style={{ minWidth: '160px' }}>Practice Progression</th>
              <th style={{ minWidth: '220px' }}>⚡ Next-Man-Up Beneficiary</th>
              <th style={{ minWidth: '260px' }}>Beat Detail / Notes</th>
              <th style={{ minWidth: '110px', textAlign: 'center' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredInjuries.map((inj) => {
              const rosterInfo = rosterPlayerMap.get(inj.athlete_id) || rosterPlayerMap.get(inj.name.trim().toLowerCase())
              const isRostered = !!rosterInfo
              const isStarter = rosterInfo?.isStarter ?? false

              return (
                <tr key={inj.athlete_id} style={isStarter ? { backgroundColor: 'rgba(244, 63, 94, 0.05)' } : undefined}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                      <NFLTeamLogo team={inj.team} size={24} style={{ marginTop: '2px' }} />
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                          <span style={{ fontWeight: 700, fontSize: '13.5px' }}>{inj.name}</span>
                          {isRostered && (
                            <span
                              className={`pill ${isStarter ? 'rose' : 'zinc'}`}
                              style={{ fontSize: '9.5px', padding: '1px 6px', fontWeight: isStarter ? 800 : 600 }}
                            >
                              {isStarter ? '🚨 MY STARTER' : '⭐ MY BENCH'}
                            </span>
                          )}
                        </div>

                        {inj.decoy_risk && (
                          <div style={{ marginTop: '3px' }}>
                            <span
                              className={`pill ${inj.decoy_risk === 'HIGH' ? 'rose' : 'amber'}`}
                              style={{ fontSize: '9.5px', padding: '1px 6px', fontWeight: 800 }}
                            >
                              {inj.decoy_risk === 'HIGH' ? '⚠️ HIGH DECOY TRAP' : '⚠️ DECOY RISK'}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  </td>

                  <td>
                    <span style={{ fontWeight: 600 }}>{inj.team}</span>
                    <span className="pill zinc" style={{ fontSize: '10px', marginLeft: '6px' }}>{inj.position}</span>
                  </td>

                  <td>
                    <InjuryStatusPill
                      status={inj.status}
                      fullName={inj.name}
                      position={inj.position}
                      injuryNote={inj.headline ? `${inj.headline}${inj.notes ? ` - ${inj.notes}` : ''}` : inj.notes}
                    />
                  </td>

                  <td>
                    <div>
                      {inj.practice_status ? (
                        <span
                          className={`pill ${
                            inj.practice_status === 'FULL'
                              ? 'emerald'
                              : inj.practice_status === 'LIMITED'
                              ? 'amber'
                              : 'rose'
                          }`}
                          style={{ fontWeight: 700 }}
                        >
                          {inj.practice_status}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Standard</span>
                      )}

                      {inj.practice_trend && inj.practice_trend !== inj.practice_status && (
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px', fontWeight: 500 }}>
                          📈 {inj.practice_trend}
                        </div>
                      )}
                    </div>
                  </td>

                  {/* Next-Man-Up Beneficiary Column */}
                  <td>
                    {inj.backup_player_name ? (
                      <div
                        style={{
                          background: 'rgba(56, 189, 248, 0.08)',
                          border: '1px solid rgba(56, 189, 248, 0.25)',
                          borderRadius: '6px',
                          padding: '6px 10px',
                          fontSize: '12px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                          <span>➔ Next Up:</span>
                          <span style={{ color: 'var(--text-primary)' }}>{inj.backup_player_name}</span>
                          {inj.backup_slot && (
                            <span className="pill zinc" style={{ fontSize: '9px', padding: '1px 4px' }}>
                              {inj.backup_slot}
                            </span>
                          )}
                        </div>
                        {inj.vacated_opportunity_note && (
                          <div style={{ color: 'var(--text-muted)', fontSize: '11px', marginTop: '3px', lineHeight: '1.3' }}>
                            {inj.vacated_opportunity_note}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>--</span>
                    )}
                  </td>

                  <td style={{ fontSize: '12.5px', maxWidth: '380px', lineHeight: '1.4' }}>
                    {inj.headline && (
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '3px' }}>
                        {inj.headline}
                      </div>
                    )}
                    <div style={{ color: 'var(--text-secondary)' }}>
                      {inj.notes || 'No beat notes available.'}
                    </div>
                  </td>

                  <td style={{ textAlign: 'center' }}>
                    {isRostered ? (
                      <button
                        type="button"
                        className="btn btn-secondary btn-xs"
                        onClick={() => {
                          if (onSelectPlayerForCompare) {
                            onSelectPlayerForCompare(inj.athlete_id)
                          }
                          if (onNavigateTab) {
                            onNavigateTab('compare')
                          }
                        }}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '11px',
                          padding: '4px 8px',
                          whiteSpace: 'nowrap',
                          backgroundColor: isStarter ? 'rgba(244, 63, 94, 0.15)' : undefined,
                          borderColor: isStarter ? 'var(--accent-rose)' : undefined,
                          color: isStarter ? 'var(--accent-rose)' : undefined,
                          fontWeight: 700,
                        }}
                        title="Open Start/Sit Comparator to compare against your bench replacements"
                      >
                        ⚖️ Pivot / Compare
                      </button>
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>--</span>
                    )}
                  </td>
                </tr>
              )
            })}

            {filteredInjuries.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  No matching injury reports found for the selected filter criteria.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
