import sys
import os
sys.path.insert(0, os.path.abspath("."))
import asyncio
from fastapi.testclient import TestClient
from src.main import app

def test_multi_source_projections_and_lineups():
    client = TestClient(app)
    
    sources = ["MODEL", "CONSENSUS", "FANTASYPROS", "ESPN"]
    lineup_totals = {}
    
    print("\n--- 1. Testing GET /api/lineup/optimal with all 4 projection sources ---")
    for src in sources:
        resp = client.get(f"/api/lineup/optimal?team_id=1&mode=BALANCED&projection_source={src}")
        assert resp.status_code == 200, f"Failed for {src}: {resp.status_code} - {resp.text}"
        data = resp.json()
        
        starters = data.get("starters", [])
        bench = data.get("bench", [])
        total_pts = data.get("total_projected_points")
        lineup_totals[src] = total_pts
        
        assert len(starters) == 9, f"Expected 9 starters for {src}, got {len(starters)}"
        assert len(bench) > 0, f"Expected bench players for {src}"
        
        print(f"[{src}] Total Lineup Projected: {total_pts:.2f} pts | Starters: {len(starters)} | Bench: {len(bench)}")
        print(f"  Totals reported: Model={data.get('total_model_projected')}, FP={data.get('total_fp_projected')}, ESPN={data.get('total_espn_projected')}, Consensus={data.get('total_consensus_projected')}")
        
        # Verify first starter has multi-source fields populated
        p0 = starters[0]["recommended_player"]
        print(f"  Sample Starter: {p0['full_name']} ({p0['position']}) | Active Pts: {p0['projected_points']}")
        print(f"    Multi-Source Breakdown: Model={p0.get('proj_model')}, FP={p0.get('proj_fantasypros')}, ESPN={p0.get('proj_espn')}, Consensus={p0.get('proj_consensus')}")
        print(f"    Consensus Agreement: {p0.get('consensus_agreement')} (Spread: {p0.get('consensus_spread')} pts)")
        print(f"    Real FantasyPros Itemized Stats: {p0.get('fp_itemized_stats')}")
        
        assert p0.get("proj_model") is not None, "proj_model missing"
        assert p0.get("proj_consensus") is not None, "proj_consensus missing"
        assert p0.get("consensus_agreement") is not None, "consensus_agreement missing"

    print("\n--- 2. Testing POST /api/lineup/push with custom substitutions & projection source ---")
    # Fetch optimal starters to construct a custom swap
    resp = client.get("/api/lineup/optimal?team_id=1&mode=BALANCED&projection_source=MODEL")
    data = resp.json()
    starters = data["starters"]
    bench = data["bench"]
    
    # Simulate swapping the bench player into the first starter's slot
    custom_ids = [s["recommended_player"]["player_id"] for s in starters]
    orig_starter_id = custom_ids[0]
    bench_sub_id = bench[0]["player_id"]
    custom_ids[0] = bench_sub_id
    
    push_payload = {
        "team_id": 1,
        "confirm": False,
        "mode": "BALANCED",
        "projection_source": "CONSENSUS",
        "custom_starter_ids": custom_ids,
    }
    
    push_resp = client.post("/api/lineup/push", json=push_payload)
    assert push_resp.status_code == 200, f"Push preflight failed: {push_resp.status_code} - {push_resp.text}"
    push_data = push_resp.json()
    print(f"Push Preflight Success: {push_data.get('status_message')} | Moves flagged: {push_data.get('moves_count')}")
    for m in push_data.get("moves", []):
        print(f"  Move: {m['player_name']} ({m['position']}) from {m['from_slot_name']} -> {m['to_slot_name']} (Net: {m['net_gain']})")
    
    print("\nALL BACKEND VERIFICATION CHECKS PASSED PERFECTLY!")

if __name__ == "__main__":
    test_multi_source_projections_and_lineups()
