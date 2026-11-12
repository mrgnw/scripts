This is the wild west. No apologies, just don't set your expectations too high.

# Scripts

Isolated files that can be run directly once they are given execution permissions with `chmod +x script_path` and are added to the PATH.

## Languages

```sh
#! /usr/bin/env zsh
#! /usr/bin/env -S uv run --script
#! /usr/bin/env python3
#! /usr/bin/env swift
```

Binary files are compiled for apple silicon from the adjacent script

``` sh
swift-tool # binary
swift-tool.swift # script
```

---

## Key Scripts

### Daemon Management

#### `dm` - Development Daemon Manager
Quick access to overmind-based daemon management for development services.

**Location:** `~/dev/_daemons/` (manages services via Procfile)

**Usage:**
```bash
dm start -D          # Start all development services in background
dm status            # Check what's running
dm restart anani     # Restart a specific service
dm connect opencode  # View live logs for a service
dm kill              # Stop all services
```

**Services managed:**
- `opencode` (PORT=13370) - Code server
- `appligator` (PORT=13371) - Full-stack app (FastAPI + Svelte)
- `anani` (PORT=13372) - SvelteKit app

**Tech:** Overmind + tmux + Procfile

**Docs:** See `~/dev/_daemons/README.md` for full documentation

---

#### `svc` - System Service Manager
Manages system-level services via PM2 (e.g., ttyd).

**Location:** `~/dev/_daemons/ecosystem.config.js`

**Usage:**
```bash
svc start          # Start all services
svc start ttyd     # Start specific service
svc stop ttyd      # Stop service
svc restart ttyd   # Restart service
svc status         # Show status
svc logs ttyd      # Show logs
```

**Tech:** PM2 (Node.js process manager)

---

### Service Management Philosophy

**Use `dm` (Overmind) for:**
- Development services you frequently restart
- Services you need to interact with (live logs, debugging)
- Projects with hot-reload (appligator, anani)
- Services needing colored, real-time output

**Use `svc` (PM2) for:**
- System services that should always run
- Services needing log rotation
- Services that should start on boot
- Production-like services (ttyd, reverse proxies)

Both can coexist without conflict - use the right tool for each job.

## xcode-sims

Delete Xcode simulator runtimes and devices when not in use, re-download when needed.

```sh
scripts/xcode-sims off
scripts/xcode-sims on
scripts/xcode-sims on visionOS
scripts/xcode-sims status
```

## ship

Put the latest main live for any app, the same way every time. `ship` runs the app's own `pnpm ship`.

```sh
ship social
```

Run from anywhere. The app is its folder `~/dev/<app>`, or the `dir` of a pitchfork daemon with that name.

```sh
cd ~/dev/social
ship
```

With no argument it runs the `ship` script of the project in the current folder (not parent folders). Anywhere else it lists the apps that have a `ship` script and ships nothing.

`ship` never merges anything. It deploys what is on main.

### Give an app a ship script

Cloudflare apps:

```json
"ship": "pnpm build && wrangler deploy"
```

Apps that pitchfork runs on this machine, with the daemon id from `pitchfork list`:

```json
"ship": "ship-pitchfork global/social"
```

`ship-pitchfork <daemon id>` stops unless the checkout is on `main`, clean, and in sync with `origin/main`. Then it runs, in order:

```sh
git pull --ff-only origin main
pnpm install --frozen-lockfile
pnpm build
pitchfork restart global/social
```

`pitchfork restart` only restarts the process. The pull and build above are what bring in new code, because the app serves its `build/` folder.
