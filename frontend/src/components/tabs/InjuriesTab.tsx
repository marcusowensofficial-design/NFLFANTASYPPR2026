import React, { useState } from 'react'
import type { InjuryFeedResponse } from '../../types'
import { InjuryStatusPill } from '../shared/InjuryStatusPill'
import { NFLTeamLogo } from '../shared/NFLTeamLogo'

export interface InjuriesTabProps {
  injuriesFeed: InjuryFeedResponse | null
  isLoadingInjuries: boolean
  onRefreshInjuries: () => void
}

export const InjuriesTab: React.FC<InjuriesTabProps> = ({
  injuriesFeed,
  isLoadingInjuries,
  onRefreshInjuries,
}) => {
  const [injurySearch, setInjurySearch] = useState<string>('')
  const [injuryPosFilter, setInjuryPosFilter] = useState<string>('ALL')
  const [injuryStatusFilter, setInjuryStatusFilter] = useState<string>('ALL')

  const filteredInjuries = (injuriesFeed?.injuries || []).filter((inj) => {
    if (injurySearch && !inj.name.toLowerCase().includes(injurySearch.toLowerCase()) && !inj.team.toLowerCase().includes(injurySearch.toLowerCase())) {
      return false
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

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">🩺 Live 2026 NFL Injury Wire</h3>
        <span className="pill rose">
          {injuriesFeed ? `${injuriesFeed.total_count} Official Reports` : 'Live Reports'}
        </span>
      </div>

      <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '20px' }}>
        Official NFL injury designations and practice progression. Questionable players receive automated availability
        discounts in the Start/Sit scoring engine based on Friday practice participation.
      </p>

      {/* Search & Filter Controls */}
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '14px', alignItems: 'center' }}>
        <input
          type="text"
          placeholder="🔍 Search player name or team..."
          value={injurySearch}
          onChange={(e) => setInjurySearch(e.target.value)}
          className="select-dropdown"
          style={{ flex: '1', minWidth: '220px', cursor: 'text' }}
        />

        <select
          className="select-dropdown"
          value={injuryPosFilter}
          onChange={(e) => setInjuryPosFilter(e.target.value)}
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
        >
          <option value="ALL">All Statuses</option>
          <option value="OUT">Out / IR / Doubtful</option>
          <option value="QUESTIONABLE">Questionable</option>
          <option value="ACTIVE">Active</option>
        </select>

        <button
          className="btn btn-secondary btn-sm"
          onClick={onRefreshInjuries}
          disabled={isLoadingInjuries}
        >
          {isLoadingInjuries ? '⏳ Refreshing...' : '🔄 Refresh Live Feed'}
        </button>
      </div>

      <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '16px' }}>
        Showing {filteredInjuries.length} of {injuriesFeed?.total_count || 800} verified NFL reports
      </div>

      <div className="table-responsive">
        <table className="custom-table">
          <thead>
            <tr>
              <th>Player</th>
              <th>Team & Pos</th>
              <th>Status</th>
              <th>Practice Participation</th>
              <th>Beat Reporter Detail / Practice Notes</th>
            </tr>
          </thead>
          <tbody>
            {filteredInjuries.map((inj) => (
              <tr key={inj.athlete_id}>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <NFLTeamLogo team={inj.team} size={22} />
                    <span style={{ fontWeight: 700 }}>{inj.name}</span>
                  </div>
                </td>
                <td>{inj.team} ({inj.position})</td>
                <td>
                  <InjuryStatusPill
                    status={inj.status}
                    fullName={inj.name}
                    position={inj.position}
                    injuryNote={inj.headline ? `${inj.headline}${inj.notes ? ` - ${inj.notes}` : ''}` : inj.notes}
                  />
                </td>
                <td>
                  {inj.practice_status ? (
                    <span className={`pill ${
                      inj.practice_status === 'FULL' ? 'emerald' : inj.practice_status === 'LIMITED' ? 'amber' : 'rose'
                    }`}>
                      {inj.practice_status}
                    </span>
                  ) : (
                    <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Standard</span>
                  )}
                </td>
                <td style={{ fontSize: '13px', maxWidth: '440px', lineHeight: '1.4' }}>
                  {inj.headline && (
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                      {inj.headline}
                    </div>
                  )}
                  <div style={{ color: 'var(--text-secondary)' }}>
                    {inj.notes || 'No beat notes available.'}
                  </div>
                </td>
              </tr>
            ))}
            {filteredInjuries.length === 0 && (
              <tr>
                <td colSpan={5} style={{ textAlign: 'center', padding: '36px', color: 'var(--text-muted)' }}>
                  No matching injury reports found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
