# Nemisis test suite still (PNG). Run last, after the README embeds every capture, so the
# count shown is the count the docs quote. Regenerate from the repository root with:
#   vhs docs/assets/screenshots/crashcheck-pytest.tape

Output .nemisis/vhs-pytest-scratch.gif

Set Shell "bash"
Set FontSize 17
Set Width 1400
Set Height 260
Set Padding 22
Set Theme "Catppuccin Mocha"
Set TypingSpeed 1ms
Set WindowBar Colorful
Set WindowBarSize 36

Type "uv run pytest -q"
Enter
Sleep 80s
Screenshot docs/assets/screenshots/terminal-pytest-green.png
Sleep 1s
