import { Tooltip } from './Tooltip'

export interface VegasPropsCapablePlayer {
  position: string
  props_vegas_grade?: string | null
  props_vegas_grade_label?: string | null
  props_vegas_grade_color?: string | null
  props_vegas_takeaway?: string | null
  props_receptions_ou?: number | null
  props_rec_yds_ou?: number | null
  props_rush_yds_ou?: number | null
  props_rush_att_ou?: number | null
  props_pass_yds_ou?: number | null
  props_pass_tds_ou?: number | null
  props_anytime_td_odds?: number | null
  props_anytime_td_prob?: number | null
  props_implied_ppr_pts?: number | null
  props_sharp_notes?: string[]
  implied_team_total?: number | null
}

export const renderLineupVegasProps = (p: VegasPropsCapablePlayer, _isBench: boolean = false) => {
  // Check if player has any Vegas props or grade data
  if (
    !p.props_vegas_grade &&
    !p.props_receptions_ou &&
    !p.props_rec_yds_ou &&
    !p.props_rush_yds_ou &&
    !p.props_rush_att_ou &&
    !p.props_pass_yds_ou &&
    !p.props_implied_ppr_pts
  ) {
    return null
  }

  const pos = p.position?.toUpperCase() || ''
  const gradeColor = p.props_vegas_grade_color || 'zinc'
  const gradeLabel = p.props_vegas_grade_label || p.props_vegas_grade || 'Vegas'
  const takeawayTitle = p.props_vegas_takeaway ? `Vegas Outlook: ${p.props_vegas_takeaway}` : 'Vegas Sportsbook Props'

  return (
    <div className="lineup-vegas-strip">
      <Tooltip term="VEGAS_PROPS" title={takeawayTitle}>
        <span className={`lineup-vegas-grade ${gradeColor}`}>
          {gradeLabel}
        </span>
      </Tooltip>

      {/* QB Props: Pass Yards, Pass TDs, Mobile Rush Yards, TD Prob */}
      {pos === 'QB' && (
        <>
          {p.props_pass_yds_ou ? (
            <span className="lineup-prop-chip" title="Passing Yards Over/Under">
              🎯 <strong>{p.props_pass_yds_ou}</strong> Pass Yds
            </span>
          ) : null}
          {p.props_pass_tds_ou ? (
            <span className="lineup-prop-chip" title="Passing Touchdowns Over/Under">
              🏈 <strong>{p.props_pass_tds_ou}</strong> TDs
            </span>
          ) : null}
          {p.props_rush_yds_ou && p.props_rush_yds_ou >= 12.0 ? (
            <span className="lineup-prop-chip" title="QB Rushing Yards Over/Under">
              🏃 <strong>{p.props_rush_yds_ou}</strong> Rush
            </span>
          ) : null}
          {p.props_anytime_td_prob && p.props_anytime_td_prob >= 0.35 ? (
            <span className="lineup-prop-chip td" title="Anytime TD Probability">
              💰 <strong>{Math.round(p.props_anytime_td_prob * 100)}%</strong> TD
            </span>
          ) : null}
        </>
      )}

      {/* RB / FB Props: Carries O/U, Rush Yards, Receptions O/U, TD Prob */}
      {['RB', 'FB'].includes(pos) && (
        <>
          {p.props_rush_att_ou ? (
            <span className="lineup-prop-chip" title="Rushing Attempts Over/Under">
              🏃 <strong>{p.props_rush_att_ou}</strong> Carries
            </span>
          ) : null}
          {p.props_rush_yds_ou ? (
            <span className="lineup-prop-chip" title="Rushing Yards Over/Under">
              💨 <strong>{p.props_rush_yds_ou}</strong> Rush Yds
            </span>
          ) : null}
          {p.props_receptions_ou && p.props_receptions_ou >= 1.5 ? (
            <span className="lineup-prop-chip" title="Receptions Over/Under in Full PPR">
              🎯 <strong>{p.props_receptions_ou}</strong> Rec
            </span>
          ) : null}
          {p.props_anytime_td_prob && p.props_anytime_td_prob >= 0.38 ? (
            <span className="lineup-prop-chip td" title="Anytime TD Probability">
              💰 <strong>{Math.round(p.props_anytime_td_prob * 100)}%</strong> TD
            </span>
          ) : null}
        </>
      )}

      {/* WR Props: Receptions O/U, Receiving Yards, TD Prob */}
      {pos === 'WR' && (
        <>
          {p.props_receptions_ou ? (
            <span className="lineup-prop-chip" title="Receptions Over/Under in Full PPR">
              🎯 <strong>{p.props_receptions_ou}</strong> Rec O/U
            </span>
          ) : null}
          {p.props_rec_yds_ou ? (
            <span className="lineup-prop-chip" title="Receiving Yards Over/Under">
              💨 <strong>{p.props_rec_yds_ou}</strong> Rec Yds
            </span>
          ) : null}
          {p.props_anytime_td_prob && p.props_anytime_td_prob >= 0.30 ? (
            <span className="lineup-prop-chip td" title="Anytime TD Probability">
              💰 <strong>{Math.round(p.props_anytime_td_prob * 100)}%</strong> TD
            </span>
          ) : null}
        </>
      )}

      {/* TE Props: Receptions O/U, Receiving Yards, TD Prob */}
      {pos === 'TE' && (
        <>
          {p.props_receptions_ou ? (
            <span className="lineup-prop-chip" title="Receptions Over/Under in Full PPR">
              🎯 <strong>{p.props_receptions_ou}</strong> Rec O/U
            </span>
          ) : null}
          {p.props_rec_yds_ou ? (
            <span className="lineup-prop-chip" title="Receiving Yards Over/Under">
              💨 <strong>{p.props_rec_yds_ou}</strong> Rec Yds
            </span>
          ) : null}
          {p.props_anytime_td_prob && p.props_anytime_td_prob >= 0.28 ? (
            <span className="lineup-prop-chip td" title="Anytime TD Probability">
              💰 <strong>{Math.round(p.props_anytime_td_prob * 100)}%</strong> TD
            </span>
          ) : null}
        </>
      )}

      {/* K Props: Team Implied Total, Implied Points */}
      {pos === 'K' && (
        <>
          {p.implied_team_total ? (
            <span className="lineup-prop-chip itt" title="Vegas Implied Team Total Points">
              ⚡ <strong>{p.implied_team_total.toFixed(1)}</strong> Team ITT
            </span>
          ) : null}
          {p.props_implied_ppr_pts ? (
            <span className="lineup-prop-chip" title="Vegas Market Implied Points">
              🎯 <strong>{p.props_implied_ppr_pts.toFixed(1)}</strong> Implied Pts
            </span>
          ) : null}
        </>
      )}

      {/* D/ST Props: Opponent Implied Points Allowed, Implied Points */}
      {['D/ST', 'DST'].includes(pos) && (
        <>
          {(() => {
            const oppNote = p.props_sharp_notes?.find((n: string) => n.includes('against:'))
            const match = oppNote?.match(/against:\s*([\d.]+)/)
            const oppItt = match ? match[1] : null
            if (oppItt) {
              return (
                <span className="lineup-prop-chip itt" title="Opponent Projected Team Points (Lower is Better)">
                  🛡️ <strong>{oppItt}</strong> Opp ITT
                </span>
              )
            }
            if (p.props_implied_ppr_pts) {
              return (
                <span className="lineup-prop-chip itt" title="Vegas Market Implied Fantasy Points">
                  🛡️ <strong>{p.props_implied_ppr_pts.toFixed(1)}</strong> Implied Pts
                </span>
              )
            }
            return null
          })()}
        </>
      )}
    </div>
  )
}
