# The two commands a judge with Docker and no uv runs:
#
#     docker build -t nemisis .
#     docker run --rm nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/mark-first
#
# The second exits 1 and prints PATCH_FAILED_INVARIANT_BROKEN: mark-first passes the base's kill
# point and still loses the credit at its own. Evidence is written to /app/.nemisis inside the
# container; add `-v "$PWD/out:/out"` and `--output-dir /out` to keep it.
#
# CrashCheck kills real process groups, so this needs a POSIX container, not a Windows one.
FROM python:3.12.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /uvx /usr/local/bin/

WORKDIR /app
COPY . .
RUN uv sync --frozen --no-dev

# --no-dev matters at run time as well as at build time: without it `uv run` would install
# mypy and ruff on first use, so the container would need the network to run a check.
ENTRYPOINT ["uv", "run", "--frozen", "--no-dev", "nemisis"]
