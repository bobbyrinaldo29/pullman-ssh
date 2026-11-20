export interface GitCredentials {
  username?: string
  password?: string
  remember?: boolean
}

export function isGitAuthError(output: string): boolean {
  if (!output) return false
  const lower = output.toLowerCase()

  // Local filesystem and lock errors must NEVER be treated as auth errors
  if (
    lower.includes('.git/') ||
    lower.includes('cannot lock ref') ||
    lower.includes('unable to create') ||
    lower.includes('index.lock') ||
    lower.includes('fetch_head') ||
    lower.includes('orig_head') ||
    lower.includes('cannot open .git') ||
    lower.includes('file exists')
  ) {
    return false
  }

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
    lower.includes('permission denied (publickey') ||
    lower.includes('publickey') ||
    lower.includes('device not configured') ||
    lower.includes('repository not found') ||
    lower.includes('please make sure you have the correct access rights') ||
    lower.includes('fatal: authentication') ||
    (lower.includes('permission denied') && (lower.includes('git@') || lower.includes('ssh')))
  )
}

export function isPushDelivered(output: string): boolean {
  if (!output) return false
  const lower = output.toLowerCase()
  if (lower.includes('everything up-to-date')) return true
  // Matches "e5403507e..e7f93f36d  staging -> staging" or "+ e540350...e7f93f3 staging -> staging"
  if (/[a-f0-9]{4,40}\.{2,3}[a-f0-9]{4,40}\s+\S+\s*->\s*\S+/i.test(output)) return true
  // Matches "[new branch]      staging -> staging"
  if (/\[new branch\]\s+\S+\s*->\s*\S+/i.test(output)) return true
  // Matches "[new tag]         v1.0 -> v1.0"
  if (/\[new tag\]\s+\S+\s*->\s*\S+/i.test(output)) return true
  // Matches "branch 'staging' set up to track remote branch"
  if (/branch\s+'\S+'\s+set\s+up\s+to\s+track/i.test(output)) return true
  return false
}

export function extractPushedRef(output: string): { branch: string; commitHash?: string } | null {
  if (!output) return null
  // Match "e5403507e..e7f93f36d  staging -> staging"
  const commitMatch = output.match(/[a-f0-9]{4,40}\.{2,3}([a-f0-9]{4,40})\s+\S+\s*->\s*(\S+)/i)
  if (commitMatch) {
    return { commitHash: commitMatch[1], branch: commitMatch[2] }
  }
  // Match "[new branch]  staging -> staging"
  const newBranchMatch = output.match(/\[new branch\]\s+\S+\s*->\s*(\S+)/i)
  if (newBranchMatch) {
    return { branch: newBranchMatch[1] }
  }
  return null
}

export function gitPreflightSnippet(): string {
  return `_GD=$(git -c safe.directory=* rev-parse --git-dir 2>/dev/null || echo ".git"); if [ -d "$_GD" ]; then rm -f "$_GD"/*.lock "$_GD"/refs/*/*.lock "$_GD"/refs/*/*/*.lock "$_GD"/refs/*/*/*/*.lock 2>/dev/null || true; chmod -R u+rwX,g+rwX,a+rwX "$_GD"/refs "$_GD"/FETCH_HEAD "$_GD"/ORIG_HEAD "$_GD"/index "$_GD"/logs "$_GD"/HEAD 2>/dev/null || true; mkdir -p "$_GD"/refs/remotes/origin 2>/dev/null && chmod 777 "$_GD"/refs/remotes/origin 2>/dev/null || true; fi`
}

export function gitCd(remotePath: string): string {
  const clean = (remotePath || '/').replace(/^diff:/, '').replace(/\/+/g, '/')
  const esc = clean.replace(/'/g, "'\\''")
  return `export PATH="$PATH:/usr/local/bin:/usr/bin:/bin"; P='${esc}'; if [ -d "$P" ]; then cd "$P" 2>/dev/null; else cd "$(dirname "$P")" 2>/dev/null; fi`
}

export function buildAuthUrl(remoteUrl: string, credentials?: GitCredentials): string | null {
  if (!remoteUrl || !credentials?.username || !credentials?.password) return null
  try {
    const parsed = new URL(remoteUrl)
    if (!['http:', 'https:'].includes(parsed.protocol)) return null
    parsed.username = credentials.username
    parsed.password = credentials.password
    return parsed.toString()
  } catch {
    return null
  }
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
  const randSuffix = Math.floor(100000 + Math.random() * 900000)
  const askFileName = `.pullman_ask_${Date.now()}_${randSuffix}.sh`

  // Ephemeral script acting as GIT_ASKPASS, SSH_ASKPASS, and Git credential.helper
  const scriptLines = [
    '#!/bin/sh',
    'p="$1"',
    `U=$(echo '${userB64}' | base64 -d 2>/dev/null || echo '${userB64}' | base64 -D 2>/dev/null || echo '${userB64}' | openssl base64 -d 2>/dev/null || python3 -c "import base64; print(base64.b64decode('${userB64}').decode(), end='')" 2>/dev/null || python -c "import base64; print(base64.b64decode('${userB64}').decode(), end='')" 2>/dev/null)`,
    `P=$(echo '${passB64}' | base64 -d 2>/dev/null || echo '${passB64}' | base64 -D 2>/dev/null || echo '${passB64}' | openssl base64 -d 2>/dev/null || python3 -c "import base64; print(base64.b64decode('${passB64}').decode(), end='')" 2>/dev/null || python -c "import base64; print(base64.b64decode('${passB64}').decode(), end='')" 2>/dev/null)`,
    'if [ "$p" = "get" ]; then',
    '  printf "username=%s\\npassword=%s\\n" "$U" "$P"',
    '  exit 0',
    'fi',
    'if [ "$p" = "store" ] || [ "$p" = "erase" ]; then',
    '  exit 0',
    'fi',
    'case "$p" in',
    '  *[Pp]assword*|*[Tt]oken*|*[Pp]assphrase*)',
    '    printf "%s\\n" "$P"',
    '    ;;',
    '  *[Uu]sername*|*[Ll]ogin*)',
    '    printf "%s\\n" "$U"',
    '    ;;',
    '  *)',
    '    printf "%s\\n" "$P"',
    '    ;;',
    'esac'
  ].join('\n')

  const escScript = scriptLines.replace(/'/g, "'\\''")
  const prepCmd = `P_DIR="$([ -n "$HOME" ] && [ -d "$HOME" ] && [ -w "$HOME" ] && echo "$HOME" || echo "/tmp")"; P_ASK="$P_DIR/${askFileName}"; printf '%s\\n' '${escScript}' > "$P_ASK" && chmod 755 "$P_ASK"`
  // Inject credentials into git command line to support both askpass and credential.helper natively
  const injectGit = command.replace(
    /git -c safe\.directory=\*/g,
    `git -c safe.directory=* -c credential.helper='!sh "$P_ASK"' -c core.askpass='sh "$P_ASK"'`
  )
  const runCmd = `export GIT_ASKPASS="$P_ASK"; export SSH_ASKPASS="$P_ASK"; export GIT_TERMINAL_PROMPT=1; ${injectGit}`
  const cleanup = `rm -f "$P_ASK"`

  const fullCmd = `${prepCmd} && { ${runCmd}; }; __P_CODE=$?; ${cleanup}; exit $__P_CODE`
  return { cmd: fullCmd, hasAskpass: true }
}

export function buildGitPullCommand(remotePath: string): string {
  const cd = gitCd(remotePath)
  const preflight = gitPreflightSnippet()
  return `${cd} && ${preflight} && BR=$(git -c safe.directory=* rev-parse --abbrev-ref HEAD 2>/dev/null); REMOTE=$(git -c safe.directory=* remote 2>/dev/null | head -n 1); [ -z "$REMOTE" ] && REMOTE="origin"; git -c safe.directory=* pull "$REMOTE" "$BR" 2>&1 || git -c safe.directory=* pull 2>&1`
}

export function buildGitPushCommand(remotePath: string): string {
  const cd = gitCd(remotePath)
  const preflight = gitPreflightSnippet()
  return `${cd} && ${preflight} && BR=$(git -c safe.directory=* rev-parse --abbrev-ref HEAD 2>/dev/null); REMOTE=$(git -c safe.directory=* remote 2>/dev/null | head -n 1); [ -z "$REMOTE" ] && REMOTE="origin"; git -c safe.directory=* push "$REMOTE" "$BR" 2>&1 || git -c safe.directory=* push -u "$REMOTE" "$BR" 2>&1 || git -c safe.directory=* push 2>&1`
}

export function getRemoteUrlCommand(remotePath: string): string {
  const cd = gitCd(remotePath)
  return `${cd} && (git -c safe.directory=* config --get remote.origin.url 2>/dev/null || git -c safe.directory=* remote get-url origin 2>/dev/null || git -c safe.directory=* config --get remote.$(git -c safe.directory=* remote 2>/dev/null | head -n 1).url 2>/dev/null || true)`
}

export function buildSaveCredentialCommand(
  remotePath: string,
  remoteUrl: string,
  credentials: GitCredentials
): string | null {
  if (!credentials.username || !credentials.password || !remoteUrl) return null
  const cd = gitCd(remotePath)

  try {
    const parsed = new URL(remoteUrl)
    if (!['http:', 'https:'].includes(parsed.protocol)) return null
    const protocol = parsed.protocol.replace(':', '').replace(/'/g, "'\\''")
    const host = parsed.host.replace(/'/g, "'\\''")
    const user = credentials.username.replace(/'/g, "'\\''")
    const pass = credentials.password.replace(/'/g, "'\\''")

    return `${cd} && (git config --global credential.helper store 2>/dev/null || git -c safe.directory=* config credential.helper store 2>/dev/null || true) && printf 'protocol=%s\\nhost=%s\\nusername=%s\\npassword=%s\\n\\n' '${protocol}' '${host}' '${user}' '${pass}' | git -c safe.directory=* credential approve`
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
  const sep = '<|PULLMAN_SEP|>'
  const fmt = `%H${sep}%h${sep}%P${sep}%an${sep}%ae${sep}%ar${sep}%s${sep}%d${sep}%D%x0a`
  return `PATH=$PATH:/usr/local/bin:/usr/bin:/bin; for P in '${escDir}' '${escCwd}'; do [ -z "$P" ] && continue; T="$P"; [ -f "$T" ] && T=$(dirname "$T"); [ ! -d "$T" ] && continue; cd "$T" 2>/dev/null || continue; R=$(git -c safe.directory=* rev-parse --show-toplevel 2>/dev/null); if [ -n "$R" ]; then cd "$R" 2>/dev/null && git -c safe.directory=* log --all --date-order -n ${limit} --pretty=format:'${fmt}' 2>/dev/null || git -c safe.directory=* log -n ${limit} --pretty=format:'${fmt}' 2>/dev/null; exit 0; fi; done`
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
