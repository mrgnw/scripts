#!/usr/bin/env bash

set -euo pipefail

readonly script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly cleanup_script="$script_dir/docker-clean-huly-teable"
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT

mock_docker="$temp_dir/docker"
call_log="$temp_dir/calls"

cat >"$mock_docker" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%q ' "$@" >>"$CALL_LOG"
printf '\n' >>"$CALL_LOG"

if [[ "$1" == ps ]]; then
	case " $* " in
		*' label=com.docker.compose.project=huly_v7 '*)
			if [[ "$2" == -aq ]]; then
				printf 'huly-one\nhuly-two\n'
			else
				printf 'huly-one\thuly_v7-front-1\tExited (0)\thuly/front\n'
			fi
			;;
		*' label=com.docker.compose.project=teable '*)
			if [[ "$2" == -aq ]]; then
				printf 'teable-one\n'
			else
				printf 'teable-one\tteable-teable-db-1\tExited (0)\tpostgres\n'
			fi
			;;
	esac
fi
EOF
chmod +x "$mock_docker"

assert_contains() {
	local expected="$1"
	local file="$2"
	if ! grep -Fq -- "$expected" "$file"; then
		echo "expected to find: $expected" >&2
		cat "$file" >&2
		exit 1
	fi
}

: >"$call_log"
DOCKER_BIN="$mock_docker" CALL_LOG="$call_log" "$cleanup_script" >"$temp_dir/dry-run.out"
assert_contains 'Dry run — re-run with --apply' "$temp_dir/dry-run.out"
assert_contains 'huly-one' "$temp_dir/dry-run.out"
if grep -Fq 'container rm' "$call_log"; then
	echo 'dry run called docker container rm' >&2
	exit 1
fi

: >"$call_log"
DOCKER_BIN="$mock_docker" CALL_LOG="$call_log" "$cleanup_script" --apply >"$temp_dir/apply.out"
assert_contains 'Removing 3 exited container(s)' "$temp_dir/apply.out"
assert_contains 'container rm huly-one huly-two teable-one' "$call_log"

if DOCKER_BIN="$mock_docker" CALL_LOG="$call_log" "$cleanup_script" --unexpected >"$temp_dir/bad-arg.out" 2>&1; then
	echo 'unknown argument unexpectedly succeeded' >&2
	exit 1
fi
assert_contains 'error: unknown argument: --unexpected' "$temp_dir/bad-arg.out"

echo 'docker-clean-huly-teable tests passed'
