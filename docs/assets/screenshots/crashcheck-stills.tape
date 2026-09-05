# Nemisis CrashCheck — terminal stills (PNG). Regenerate from the repository root with:
#   vhs docs/assets/screenshots/crashcheck-stills.tape
# The GIF this tape also writes lands under the gitignored .nemisis/ and is not committed.

Output .nemisis/vhs-stills-scratch.gif

Set Shell "bash"
Set FontSize 17
Set Width 1400
Set Height 760
Set Padding 22
Set Theme "Catppuccin Mocha"
Set TypingSpeed 1ms
Set WindowBar Colorful
Set WindowBarSize 36

Hide
Type "rm -rf .nemisis/runs .nemisis/repros; clear"
Enter
Sleep 1s
Show

Type `uv run nemisis doctor --mode live; echo "exit code $?"`
Enter
Sleep 4s
Screenshot docs/assets/screenshots/terminal-doctor-live-blocked.png
Sleep 1s
Type "clear"
Enter

Type `uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/misleading-green --corrected fixture:sqlite-credit-v1/atomic --mode local; echo "exit code $?"`
Enter
Sleep 8s
Screenshot docs/assets/screenshots/terminal-check-misleading-green.png
Sleep 1s
Type "clear"
Enter

Type `CAP=$(ls .nemisis/repros/double-credit/*/capsule.json); uv run nemisis replay "$CAP" --source fixture:sqlite-credit-v1/atomic --role corrected --mode local; echo "exit code $?"`
Enter
Sleep 6s
Screenshot docs/assets/screenshots/terminal-replay-atomic-proven.png
Sleep 1s
