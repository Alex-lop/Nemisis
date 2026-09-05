# Screenshots and recording

Three kinds of capture live here, and they are labelled differently on purpose:

- The GIF, the terminal stills, and the two report renders are real local runs of the packaged
  `sqlite-credit-v1` fixture on this tree (`LOCAL` / `FIXTURE`).
- The `viewer-01` to `viewer-03` captures are headless-Chrome renders of the committed hero evidence,
  which stays bound to its own earlier commit and engine digest (`LOCAL` / `FIXTURE`, from
  `docs/assets/crashcheck-hero/`).
- `viewer-05-fail-closed.png` is the one induced state: the capture script withholds `manifest.json`
  (a 404) so the page's fail-closed path can be seen. It shows the absence of a claim, not evidence.

Nothing is composited and nothing is a provider run. `tests/test_readme_truth.py` fails if any image
the README embeds is missing, empty, or oddly sized, and if any terminal capture has no tape that
regenerates it.

| File | What it shows | Regenerate with |
| --- | --- | --- |
| `crashcheck-demo.gif` | 30 s: buggy → `BUG_REPRODUCED`, agent's patch → `PATCH_FAILED_STILL_REPRODUCES`, atomic → `FIX_PROVEN_FOR_THIS_CAPSULE`, one capsule | `vhs crashcheck-demo.tape` |
| `terminal-doctor-live-blocked.png` | `doctor --mode live` naming exactly what a live run still needs | `vhs crashcheck-stills.tape` |
| `terminal-check-misleading-green.png` | `check` on the agent's patch: verdict, necessity, `$25 → SIGKILL → $50` timeline, exit `1` | `vhs crashcheck-stills.tape` |
| `terminal-replay-atomic-proven.png` | the same capsule replayed against the atomic fix, exit `0` | `vhs crashcheck-stills.tape` |
| `terminal-pytest-green.png` | the full suite, green | `vhs crashcheck-pytest.tape` (run last) |
| `viewer-01-initial.png` | evidence viewer on load: verdict first, FAIL / PASS controls, truth-label bar | `capture-viewer.js` |
| `viewer-02-mid-replay.png` | beat 3 of 5 active during the stepped replay | `capture-viewer.js` |
| `viewer-03-verdict-receipt.png` | replay complete, receipt revealed | `capture-viewer.js` |
| `viewer-05-fail-closed.png` | the same page with its manifest deliberately withheld by the capture script: no claim rendered | `capture-viewer.js` |
| `report-patch-failed.png` | generated HTML report for the failing candidate | `capture-viewer.js` |
| `report-fix-proven.png` | generated HTML report for the proven atomic fix | `capture-viewer.js` |

Run the tapes from the repository root with a clean `src/` so the `engine source commit` line shows
a real SHA rather than `-dirty`. `vhs` is `brew install vhs` (it pulls `ffmpeg` and `ttyd`); the
viewer captures need Google Chrome and `playwright-core`, as described at the top of
`capture-viewer.js`.
