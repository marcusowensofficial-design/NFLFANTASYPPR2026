import React from 'react'
import type { PreFlightPushPreview, LineupPushResponse } from '../../types'

export interface PreFlightPushModalProps {
  isOpen: boolean
  onClose: () => void
  pushPreview: PreFlightPushPreview | null
  pushResult: LineupPushResponse | null
  selectedMoveIds: number[]
  toggleMoveSelection: (playerId: number) => void
  onExecutePush: () => void
  isPushing: boolean
  currentWeek: number
}

export const PreFlightPushModal: React.FC<PreFlightPushModalProps> = ({
  isOpen,
  onClose,
  pushPreview,
  pushResult,
  selectedMoveIds,
  toggleMoveSelection,
  onExecutePush,
  isPushing,
  currentWeek,
}) => {
  if (!isOpen || !pushPreview) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="modal-title">🚀 Push Lineup to ESPN</div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              {pushPreview.team_name} • Week {currentWeek}
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          {pushResult && (
            <div className={`diag-box ${pushResult.success ? 'success' : 'error'}`}>
              <strong>{pushResult.success ? '✅ Success!' : '⚠️ Result:'}</strong> {pushResult.message}
            </div>
          )}

          {pushPreview.moves_count === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px 0' }}>
              <div style={{ fontSize: '36px', marginBottom: '8px' }}>🎉</div>
              <h4 style={{ fontWeight: 700, fontSize: '16px', color: 'var(--accent-emerald)' }}>
                Your ESPN Lineup is Already 100% Optimal!
              </h4>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '6px' }}>
                All recommended starters currently occupy their highest-scoring active slots on ESPN. No roster changes needed.
              </p>
            </div>
          ) : (
            <>
              <div style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                Review the starter and bench movements below. Uncheck any individual swap you wish to exclude before committing to ESPN:
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {pushPreview.moves.map((move) => {
                  const isChecked = selectedMoveIds.includes(move.player_id)
                  const isStarterPromotion = move.to_slot_id !== 20
                  return (
                    <div
                      key={`${move.player_id}_${move.from_slot_id}_${move.to_slot_id}`}
                      className="push-move-card"
                      style={{
                        borderLeft: isStarterPromotion
                          ? '4px solid var(--accent-emerald)'
                          : '4px solid var(--text-muted)',
                      }}
                    >
                      <div className="push-move-left">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleMoveSelection(move.player_id)}
                          style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                        />
                        <div>
                          <div className="push-move-title">
                            {move.player_name}{' '}
                            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                              ({move.position})
                            </span>
                          </div>
                          <div className="push-move-detail">
                            <span className="slot-badge" style={{ fontSize: '10px' }}>{move.from_slot_name}</span>
                            <span className="push-arrow">➔</span>
                            <span
                              className="slot-badge"
                              style={{
                                fontSize: '10px',
                                background: isStarterPromotion ? 'rgba(16,185,129,0.2)' : 'rgba(255,255,255,0.08)',
                              }}
                            >
                              {move.to_slot_name}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div style={{ textAlign: 'right' }}>
                        <div
                          style={{
                            fontSize: '13px',
                            fontWeight: 700,
                            color: move.net_gain >= 0 ? 'var(--accent-emerald)' : 'var(--text-muted)',
                          }}
                        >
                          {move.net_gain >= 0 ? `+${move.net_gain.toFixed(1)} pts` : `${move.net_gain.toFixed(1)} pts`}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          StartScore: {move.start_score}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          {pushPreview.moves_count > 0 && (
            <button
              className="btn btn-primary"
              style={{
                backgroundColor: '#10b981',
                borderColor: '#10b981',
                color: '#022c22',
                fontWeight: 800,
              }}
              onClick={onExecutePush}
              disabled={isPushing || selectedMoveIds.length === 0}
            >
              {isPushing ? '⏳ Submitting to ESPN...' : `Confirm & Push (${selectedMoveIds.length} Moves)`}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
