# Nemisis CrashCheck — 30-second terminal recording.
# Regenerate from the repository root with:  vhs docs/assets/screenshots/crashcheck-demo.tape
# Everything shown is a real local run of the packaged sqlite-credit-v1 fixture (LOCAL / FIXTURE).

Output docs/assets/screenshots/crashcheck-demo.gif

Set Shell "bash"
Set FontSize 17
Set Width 1400
Set Height 760
Set Padding 22
Set Theme "Catppuccin Mocha"
Set TypingSpeed 12ms
Set WindowBar Colorful
Set WindowBarSize 36

# Build the frozen crash capsule once, off camera, so the three replays share one capsule.
Hide
Type "rm -rf .nemisis/runs .nemisis/repros && uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/misleading-green --corrected fixture:sqlite-credit-v1/atomic --mode local > /dev/null 2>&1; CAP=$(ls .nemisis/repros/double-credit/*/capsule.json); clear"
Enter
Sleep 8s
Show

Type "# 1/3  Original buggy handler, under one frozen crash capsule"
Enter
Sleep 1s
Type `uv run nemisis replay "$CAP" --source fixture:sqlite-credit-v1/buggy --role base --mode local; echo "exit code $?"`
Enter
Sleep 4s
Sleep 2.5s
Type "clear"
Enter

Type `# 2/3  The agent's "fixed" patch: its tests are green. Same kill, same retry.`
Enter
Sleep 1s
Type `uv run nemisis replay "$CAP" --source fixture:sqlite-credit-v1/misleading-green --role candidate --mode local; echo "exit code $?"`
Enter
Sleep 4s
Sleep 3.5s
Type "clear"
Enter

Type "# 3/3  The atomic fix: exactly once, five fresh worlds, same capsule"
Enter
Sleep 1s
Type `uv run nemisis replay "$CAP" --source fixture:sqlite-credit-v1/atomic --role corrected --mode local; echo "exit code $?"`
Enter
Sleep 4s
Sleep 4.5s
