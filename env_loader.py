"""Zero-dependency .env loader. Reads KEY=VALUE lines from a `.env` file in the repo root and
populates os.environ for any key NOT already set, so a value exported in your shell still wins.

Import it ONCE, early (it loads on import):  `import env_loader`
or call explicitly:                          `env_loader.load_env()`

This is how the bot picks up TRADERSPOST_LIVE_URL (and friends) without retyping the secret each
launch. The .env file is gitignored — never commit it. Format (one per line):

    # comments and blank lines are ignored
    TRADERSPOST_LIVE_URL=https://webhooks.traderspost.io/trading/webhook/uuid/token
    TRADERSPOST_APEX_URL=https://...           # optional per-account override
    export FOO=bar                             # a leading `export ` is tolerated

Quoting: surrounding single/double quotes are stripped. No shell expansion, no multiline values.
"""
import os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def load_env(path=PATH, override=False):
    """Load KEY=VALUE pairs from `path` into os.environ. Returns the dict of keys it SET (skips
    keys already present unless override=True). Silently no-ops if the file is missing — the bot
    runs fine without a .env (you can still export vars or pass them inline)."""
    set_keys = {}
    if not os.path.exists(path):
        return set_keys
    with open(path) as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if (len(val) >= 2) and val[0] == val[-1] and val[0] in ("'", '"'):
                val = val[1:-1]                      # strip matching surrounding quotes
            if not key:
                continue
            if override or key not in os.environ:
                os.environ[key] = val
                set_keys[key] = val
    return set_keys


# load on import so any entry point that imports this module gets the .env automatically
load_env()
