# Review prompt

What a review of the code against the [[workflow-spec]] should produce.
Moved here from the spec on 2026-11-18. The first review is
`docs/workflow-review.md`.

=== WHAT TO PRODUCE ===

1. A table with columns: Check | Status (Pass / Partial / Fail / Not found) |
   Evidence | What to fix. Cover every role rule, every song-selection step,
   every chords/playback rule, every hard rule, and every expected table.
2. A list of anything in my material that is NOT part of this flow (extra
   features, extra tables, or behaviour that contradicts the flow).
3. The 3 most important fixes, in priority order.
4. A one-line verdict: does it follow the flow, mostly follow it, or not?
