# vault404 - Session Notes

## 2026-04-16 (Session 2)

### Summary
Added live community stats badges to GitHub README. Badges show real-time fixes count, contributor count, and brain size using Shields.io dynamic endpoint format.

### Changes
- `src/vault404/api/routes.py`: Added `/api/v1/badge/{metric}` endpoint returning Shields.io JSON
- `src/vault404/sync/community.py`: Added unique contributor counting to get_stats()
- `README.md`: Added live badges for fixes (99), contributors (1), brain size
- `tests/test_mcp_tools.py`: Fixed test assertions for updated stats structure

### Commits
- `2a1f7ee` feat: add live community stats badges to README

### Deployment
- API redeployed to Railway (v0.1.3)
- Badge endpoints live at `https://web-production-7e0e3.up.railway.app/api/v1/badge/{fixes|contributors|brain}`

### Current Stats (Real Numbers)
- 99 fixes (seeded)
- 1 contributor (seed script)
- Numbers will grow organically as people use vault404

---

## 2026-04-16 (Session 1)

### Summary
Fixed `agent_brain_stats` MCP tool to show both local and community brain stats. Previously it only showed local storage (1 record), missing the 99 patterns in the remote Supabase community brain.

### Changes
- `src/vault404/sync/community.py`: Added `get_stats()` method to CommunityBrain class
- `src/vault404/tools/maintenance.py`: Updated `get_stats()` to combine local + community stats

### Commits
- `2c16ade` feat: show combined local + community brain stats

### What's Next
- Restart Claude Code to reload MCP server with updated stats
- Project is ON HOLD - letting database grow organically

### Notes
- User mentioned reverting tomorrow - unclear why, code is working correctly
- Combined stats now show: "vault404: 100 total | Local: 1 | Community: 99"
