import React from 'react'

export const MatchupRatingKey: React.FC<{
  isOpen: boolean
  onToggle: () => void
}> = ({ isOpen, onToggle }) => {
  const tiers = [
    { stars: 1, label: 'Bad Matchup', dvp: 'DvP #1–6', desc: 'Stifling Opponent (Fewest Pts Conceded)' },
    { stars: 2, label: 'Tough', dvp: 'DvP #7–12', desc: 'Below Average Matchup' },
    { stars: 3, label: 'Neutral', dvp: 'DvP #13–20', desc: 'Middle of the Pack' },
    { stars: 4, label: 'Good Matchup', dvp: 'DvP #21–26', desc: 'Above Average Matchup' },
    { stars: 5, label: 'Amazing Matchup', dvp: 'DvP #27–32', desc: 'Generous / Smash Matchup (Most Pts Conceded)' },
  ]

  return (
    <div className="matchup-key-banner">
      <div className="matchup-key-header" onClick={onToggle}>
        <div className="matchup-key-title-group">
          <span className="matchup-key-title">
            <span>⭐</span> FantasyPros Matchup Rating Key
          </span>
          <span className="matchup-key-subtitle">
            1 Star (Worst) to 5 Stars (Best) scale calibrated against Opponent Defense vs Position (DvP #1–32)
          </span>
        </div>
        <button
          type="button"
          className="matchup-key-toggle-btn"
          onClick={(e) => {
            e.stopPropagation()
            onToggle()
          }}
        >
          {isOpen ? '▲ Collapse Key' : '▼ View Rating Key'}
        </button>
      </div>

      {isOpen && (
        <div className="matchup-key-grid">
          {tiers.map((t) => (
            <div key={t.stars} className={`matchup-key-card tier-${t.stars}`}>
              <div className="matchup-key-card-header">
                <span className="matchup-stars-row">
                  {[1, 2, 3, 4, 5].map((s) => (
                    <span key={s} className={`star-icon ${s <= t.stars ? 'filled' : 'empty'}`}>
                      ★
                    </span>
                  ))}
                </span>
                <span className="matchup-stars-text">{t.stars}/5</span>
              </div>
              <div className={`matchup-key-card-label tier-${t.stars}`}>{t.label}</div>
              <div className="matchup-key-card-desc">
                <strong style={{ color: 'var(--text-primary)' }}>{t.dvp}</strong> • {t.desc}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
