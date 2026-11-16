export interface GitCredentials {
  username?: string
  password?: string
  remember?: boolean
}

export function isGitAuthError(output: string): boolean {
  if (!output) return false
  const lower = output.toLowerCase()
  return (
    lower.includes('could not read username') ||
    lower.includes('could not read password') ||
    lower.includes('terminal prompts disabled') ||
    lower.includes('authentication failed') ||
    lower.includes('invalid username or password') ||
    lower.includes('http 401') ||
    lower.includes('401 unauthorized') ||
    lower.includes('not authorized') ||
    lower.includes('access denied') ||
    lower.includes('no such device or address') ||
    lower.includes('permission denied (publickey)') ||
    lower.includes('device not configured')
  )
}

export function wrapCommandWithAskpass(
  command: string,
  credentials?: GitCredentials
): { cmd: string; hasAskpass: boolean } {
  if (!credentials || (!credentials.username && !credentials.password)) {
    return { cmd: command, hasAskpass: false }
  }

  const userB64 = Buffer.from(credentials.username || '').toString('base64')
  const passB64 = Buffer.from(credentials.password || '').toString('base64')
  const askpassPath = `/tmp/.pullman_ask_${Date.now()}_$RANDOM`

  // Ephemeral askpass script using base64 decoding on remote host
  const scriptLines = [
    '#!/bin/sh',
    'p="$1"',
    'case "$p" in',
    '  *[Uu]sername*|*[Ll]ogin*)',
    `    printf '%s\\n' "$(echo '${userB64}' | base64 -d 2>/dev/null || echo '${userB64}' | openssl base64 -d 2>/dev/null)"`,
    '    ;;',
    '  *[Pp]assword*|*[Tt]oken*)',
    `    printf '%s\\n' "$(echo '${passB64}' | base64 -d 2>/dev/null || echo '${passB64}' | openssl base64 -d 2>/dev/null)"`,
    '    ;;',
    '  *)',
    "    printf '\\n'",
    '    ;;',
    'esac'
  ].join('\n')

  const escScript = scriptLines.replace(/'/g, "'\\''")
  const prepCmd = `printf '%s' '${escScript}' > ${askpassPath} && chmod 700 ${askpassPath}`
  const runCmd = `GIT_ASKPASS=${askpassPath} GIT_TERMINAL_PROMPT=1 ${command}`
  const cleanup = `rm -f ${askpassPath}`

  const fullCmd = `${prepCmd} && (${runCmd}); __P_CODE=$?; ${cleanup}; exit $__P_CODE`
  return { cmd: fullCmd, hasAskpass: true }
}

export function getRemoteUrlCommand(remotePath: string): string {
  const clean = remotePath.replace(/\/+/g, '/').replace(/'/g, "'\\''")
  return `cd '${clean}' 2>/dev/null && (git -c safe.directory=* config --get remote.origin.url 2>/dev/null || git -c safe.directory=* config --get remote.$(git -c safe.directory=* remote 2>/dev/null | head -n 1).url 2>/dev/null || true)`
}

export function buildSaveCredentialCommand(
  remotePath: string,
  remoteUrl: string,
  credentials: GitCredentials
): string | null {
  if (!credentials.username || !credentials.password || !remoteUrl) return null
  const clean = remotePath.replace(/\/+/g, '/').replace(/'/g, "'\\''")

  try {
    const parsed = new URL(remoteUrl)
    const protocol = parsed.protocol.replace(':', '')
    const host = parsed.host
    const user = credentials.username.replace(/'/g, "'\\''")
    const pass = credentials.password.replace(/'/g, "'\\''")

    return `cd '${clean}' 2>/dev/null && git -c safe.directory=* config credential.helper store && printf 'protocol=${protocol}\\nhost=${host}\\nusername=${user}\\npassword=${pass}\\n\\n' | git -c safe.directory=* credential approve`
  } catch {
    return null
  }
}

export function buildCherryPickCmd(cd: string, cleanHash: string): string {
  return `${cd} && USER_NAME=$(git -c safe.directory=* config user.name 2>/dev/null || echo ""); [ -z "$USER_NAME" ] && USER_NAME="Pullman"; USER_EMAIL=$(git -c safe.directory=* config user.email 2>/dev/null || echo ""); [ -z "$USER_EMAIL" ] && USER_EMAIL="pullman@localhost"; git -c safe.directory=* -c user.name="$USER_NAME" -c user.email="$USER_EMAIL" cherry-pick '${cleanHash}'`
}

export function buildGitGraphCommitsCmd(remotePath: string, cwd: string, limit = 80): string {
  const escDir = (remotePath || '').replace(/\/+/g, '/').replace(/'/g, "'\\''")
  const escCwd = (cwd || '').replace(/'/g, "'\\''")
  return `PATH=$PATH:/usr/local/bin:/usr/bin:/bin; for P in '${escDir}' '${escCwd}'; do [ -z "$P" ] && continue; T="$P"; [ -f "$T" ] && T=$(dirname "$T"); [ ! -d "$T" ] && continue; cd "$T" 2>/dev/null || continue; R=$(git -c safe.directory=* rev-parse --show-toplevel 2>/dev/null); if [ -n "$R" ]; then cd "$R" 2>/dev/null && git -c safe.directory=* log --all --date-order -n ${limit} --pretty=format:'%H%x09%h%x09%P%x09%an%x09%ae%x09%ar%x09%s%x09%D' 2>/dev/null || git -c safe.directory=* log -n ${limit} --pretty=format:'%H%x09%h%x09%P%x09%an%x09%ae%x09%ar%x09%s%x09%D' 2>/dev/null; exit 0; fi; done`
}

export function buildCommitDetailsCmd(remotePath: string, cleanHash: string): string {
  const clean = remotePath.replace(/\/+/g, '/').replace(/'/g, "'\\''")
  const escHash = cleanHash.replace(/'/g, "'\\''")
  const logCmd = `git -c safe.directory=* --no-pager log -1 --no-color --pretty=format:'PULLMAN_META_START%n%H%n%h%n%an%n%ar%n%s%n%b%nPULLMAN_META_END' --stat --name-status '${escHash}'`
  const fetchCmd = `git -c safe.directory=* fetch origin '${escHash}' 2>/dev/null || git -c safe.directory=* fetch origin '+refs/heads/*:refs/remotes/origin/*' 2>/dev/null || git -c safe.directory=* fetch --all 2>/dev/null || true`
  return `cd '${clean}' 2>/dev/null && OUT=$(${logCmd} 2>/dev/null || true); if [ -z "$OUT" ]; then ${fetchCmd}; OUT=$(${logCmd} 2>/dev/null || true); fi; echo "$OUT"`
}

export function buildGitFileDiffCmd(
  remotePath: string,
  cwd: string,
  hash: string,
  filePath: string
): string {
  const escDir = (remotePath || '').replace(/^diff:/, '').replace(/\/+/g, '/').replace(/'/g, "'\\''")
  const escCwd = (cwd || '').replace(/'/g, "'\\''")
  const escFile = (filePath || '').replace(/^diff:/, '').replace(/\/+/g, '/').replace(/'/g, "'\\''")
  const isCommit = hash && !['HEAD', 'working', 'staged', 'current'].includes(hash) && /^[a-f0-9]{4,40}$/i.test(hash)
  const escHash = isCommit ? hash.replace(/[^a-f0-9]/gi, '') : ''

  return `PATH=$PATH:/usr/local/bin:/usr/bin:/bin; FILE='${escFile}'; R=""
for P in '${escDir}' '${escCwd}' "$(dirname "$FILE")"; do
  [ -z "$P" ] && continue; T="$P"; [ -f "$T" ] && T=$(dirname "$T"); [ ! -d "$T" ] && continue
  cd "$T" 2>/dev/null || continue; R=$(git -c safe.directory=* rev-parse --show-toplevel 2>/dev/null); [ -n "$R" ] && break
done
if [ -n "$R" ]; then
  cd "$R" 2>/dev/null; REL="$FILE"
  case "$FILE" in "$R"/*) REL="\${FILE#$R/}" ;; esac
  REL="\${REL#/}"
  ${isCommit
    ? `D=$(git -c safe.directory=* diff '${escHash}~1' '${escHash}' -- "$REL" 2>/dev/null || git -c safe.directory=* show --format="" '${escHash}' -- "$REL" 2>/dev/null)
  O=$(git -c safe.directory=* show '${escHash}~1:'"$REL" 2>/dev/null || echo "")
  M=$(git -c safe.directory=* show '${escHash}:'"$REL" 2>/dev/null || echo "")`
    : `D=$(git -c safe.directory=* diff HEAD -- "$REL" 2>/dev/null || git -c safe.directory=* diff -- "$REL" 2>/dev/null)
  [ -z "$D" ] && [ -f "$REL" ] && D=$(git -c safe.directory=* diff --no-index /dev/null "$REL" 2>/dev/null)
  O=$(git -c safe.directory=* show HEAD:"$REL" 2>/dev/null || echo "")
  M=$([ -f "$REL" ] && cat "$REL" 2>/dev/null || cat "$R/$REL" 2>/dev/null || cat "$FILE" 2>/dev/null || echo "")`}
  printf "%s\\n___PULLMAN_DIFF_SEP___\\n%s\\n___PULLMAN_DIFF_SEP___\\n%s" "$D" "$O" "$M"
fi`
}
