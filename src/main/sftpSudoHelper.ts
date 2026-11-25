export type SudoStrategy =
  | 'su_stdin'
  | 'su_dash_stdin'
  | 'su_root_stdin'
  | 'sudo_s_stdin'
  | 'bash_stdin'
  | 'sh_stdin'
  | 'su_c'
  | 'sh_c'
  | 'su_stdin_pty'
  | 'su_dash_stdin_pty'
  | 'su_root_stdin_pty'
  | 'direct_su_pty'
  | 'none'

export interface SudoCapability {
  strategy: SudoStrategy
  checkedPassword: string
  error?: string
}

export interface SudoSessionLike {
  client: any
  config?: { user?: string; password?: string }
  sudoCapability?: SudoCapability
  sudoProbePromise?: Promise<SudoCapability>
}

export interface ExecResult {
  stdout: string
  stderr: string
  code: number
}

const ANSI_ESCAPE_RE = /\u001b\[[0-9;?]*[ -/]*[@-~]|\u001b\][^\u0007]*\u0007/g
const OUT_BEGIN_MARKER = '__PM_OUT_BEGIN__'

function stripAnsi(s: string): string {
  return s.replace(ANSI_ESCAPE_RE, '').replace(/\r/g, '')
}

export function isSudoPolicyDenied(out: string): boolean {
  return /not allowed to execute|not allowed to run|not in the sudoers|may not run sudo/i.test(out)
}

export function isSudoBadPassword(out: string): boolean {
  return /sorry,\s*try again|incorrect password|authentication failure|passwords? do not match/i.test(out)
}

function isSudoTtyRequired(out: string): boolean {
  return /must have a tty|no tty present|must be run from a terminal|standard in must be a tty|terminal is required/i.test(
    out
  )
}

function isSudoPasswordNeeded(out: string): boolean {
  return /a password is required|password is required|no askpass program/i.test(out)
}

export function rawExec(rawSsh: any, command: string, pty = false): Promise<ExecResult> {
  return new Promise((resolve, reject) => {
    rawSsh.exec(command, { pty }, (err: any, stream: any) => {
      if (err) return reject(err)
      let stdout = ''
      let stderr = ''
      let exitCode: number | null = null
      let hadSignal = false

      stream.on('data', (data: Buffer | string) => {
        stdout += data.toString()
      })
      if (stream.stderr) {
        stream.stderr.on('data', (data: Buffer | string) => {
          stderr += data.toString()
        })
      }
      stream.on('exit', (code: number | null, signal?: string) => {
        if (typeof code === 'number') exitCode = code
        else if (signal) hadSignal = true
      })
      stream.on('close', () => {
        resolve({ stdout, stderr, code: exitCode !== null ? exitCode : hadSignal ? 1 : 0 })
      })
    })
  })
}

function encodeCommandBase64(command: string): string {
  return Buffer.from(command, 'utf8').toString('base64')
}

function buildRootLine(command: string, withOutMarker: boolean): string {
  const b64 = encodeCommandBase64(command)
  const decodeExpr = `$(printf '%s\\n' '${b64}' | (base64 -d 2>/dev/null || base64 -D 2>/dev/null || openssl base64 -d -A 2>/dev/null))`
  const prefix = withOutMarker ? `printf '${OUT_BEGIN_MARKER}'; ` : ''
  return `${prefix}exec sh -c "${decodeExpr}" </dev/null`
}

function getSudoTargetArgs(strategy: SudoStrategy): string {
  switch (strategy) {
    case 'su_stdin':
    case 'su_stdin_pty':
      return 'su'
    case 'su_dash_stdin':
    case 'su_dash_stdin_pty':
      return 'su -'
    case 'su_root_stdin':
    case 'su_root_stdin_pty':
      return 'su root'
    case 'sudo_s_stdin':
      return '-s'
    case 'bash_stdin':
      return 'bash'
    case 'sh_stdin':
      return 'sh'
    default:
      return 'su'
  }
}

async function execViaPipeStrategy(
  rawSsh: any,
  strategy: SudoStrategy,
  command: string,
  password: string
): Promise<ExecResult> {
  let cmdToRun = ''

  if (strategy === 'su_c' || strategy === 'sh_c') {
    const esc = command.replace(/'/g, "'\\''")
    const runner = strategy === 'su_c' ? `su -c '${esc}'` : `-- sh -c '${esc}'`
    const checkArg = strategy === 'su_c' ? `su -c 'true'` : `-- sh -c 'true'`
    if (password) {
      const escPass = password.replace(/'/g, "'\\''")
      cmdToRun =
        `if sudo -n ${checkArg} >/dev/null 2>&1; then ` +
        `sudo -n ${runner}; ` +
        `else ` +
        `printf '%s\\n' '${escPass}' | sudo -S -p '' ${runner}; ` +
        `fi`
    } else {
      cmdToRun = `sudo -n ${runner}`
    }
    return rawExec(rawSsh, cmdToRun, false)
  }

  const sudoArgs = getSudoTargetArgs(strategy)
  const withMarker = strategy === 'su_dash_stdin' || strategy === 'sudo_s_stdin'
  const rootLine = buildRootLine(command, withMarker)
  const escLine = rootLine.replace(/'/g, "'\\''")

  if (password) {
    const escPass = password.replace(/'/g, "'\\''")
    cmdToRun =
      `if printf 'exit 0\\n' | sudo -n ${sudoArgs} >/dev/null 2>&1; then ` +
      `printf '%s\\n' '${escLine}' | sudo -n ${sudoArgs}; ` +
      `else ` +
      `{ printf '%s\\n' '${escPass}'; printf '%s\\n' '${escLine}'; } | sudo -S -p '' ${sudoArgs}; ` +
      `fi`
  } else {
    cmdToRun = `printf '%s\\n' '${escLine}' | sudo -n ${sudoArgs}`
  }

  const res = await rawExec(rawSsh, cmdToRun, false)
  if (withMarker && res.stdout.includes(OUT_BEGIN_MARKER)) {
    const idx = res.stdout.indexOf(OUT_BEGIN_MARKER)
    res.stdout = res.stdout.slice(idx + OUT_BEGIN_MARKER.length)
  }
  return res
}

function buildPtyPayload(command: string): string {
  const b64 = encodeCommandBase64(command)
  const runSnippet =
    `sh /tmp/.pms_$$ > /tmp/.pmo_$$ 2> /tmp/.pme_$$ </dev/null; _R=$?; ` +
    `printf '\\n__PM_S__%d:' "$_R"; ` +
    `(base64 -w0 /tmp/.pmo_$$ 2>/dev/null || base64 /tmp/.pmo_$$ | tr -d '\\r\\n'); ` +
    `printf ':'; ` +
    `(base64 -w0 /tmp/.pme_$$ 2>/dev/null || base64 /tmp/.pme_$$ | tr -d '\\r\\n'); ` +
    `printf '__PM_E__\\n'; rm -f /tmp/.pms_$$ /tmp/.pmo_$$ /tmp/.pme_$$; exit $_R`

  if (b64.length <= 1800) {
    return (
      `stty -echo 2>/dev/null; printf '%s\\n' '${b64}' | (base64 -d 2>/dev/null || base64 -D 2>/dev/null || openssl base64 -d -A 2>/dev/null) > /tmp/.pms_$$ && { ${runSnippet}; }\n`
    )
  }

  const chunks = b64.match(/.{1,76}/g) || [b64]
  return (
    `stty -echo 2>/dev/null; cat <<'__PMEOF__' | (base64 -d 2>/dev/null || base64 -D 2>/dev/null || openssl base64 -d -A 2>/dev/null) > /tmp/.pms_$$\n` +
    `${chunks.join('\n')}\n` +
    `__PMEOF__\n` +
    `${runSnippet}\n`
  )
}

async function execViaPtyStrategy(
  rawSsh: any,
  strategy: SudoStrategy,
  command: string,
  password: string,
  timeoutMs = 120000
): Promise<ExecResult> {
  const ptyCmd =
    strategy === 'direct_su_pty'
      ? 'su'
      : `sudo -p '__PM_PW__' ${getSudoTargetArgs(strategy)}`

  return new Promise((resolve, reject) => {
    rawSsh.exec(ptyCmd, { pty: true }, (err: any, stream: any) => {
      if (err) return reject(err)

      let rawBuf = ''
      let pwSent = false
      let cmdSent = false
      let settled = false
      let exitCode: number | null = null
      let promptTimer: ReturnType<typeof setTimeout> | null = null

      const cleanup = (): void => {
        if (promptTimer) {
          clearTimeout(promptTimer)
          promptTimer = null
        }
        clearTimeout(authTimer)
        clearTimeout(overallTimer)
      }

      const finish = (result: ExecResult): void => {
        if (settled) return
        settled = true
        cleanup()
        try {
          stream.end()
        } catch {
          // ignore
        }
        resolve(result)
      }

      const authTimer = setTimeout(() => {
        if (!cmdSent && !settled) {
          finish({
            stdout: '',
            stderr: stripAnsi(rawBuf).trim() || 'Timed out waiting for elevated shell prompt.',
            code: 1
          })
        }
      }, 15000)

      const overallTimer = setTimeout(() => {
        if (!settled) {
          finish({
            stdout: '',
            stderr: stripAnsi(rawBuf).trim() || 'Elevated command execution timed out.',
            code: 1
          })
        }
      }, timeoutMs)

      const sendCommandPayload = (): void => {
        if (cmdSent || settled) return
        cmdSent = true
        clearTimeout(authTimer)
        rawBuf = ''
        try {
          stream.write(buildPtyPayload(command))
        } catch (writeErr) {
          finish({
            stdout: '',
            stderr: writeErr instanceof Error ? writeErr.message : String(writeErr),
            code: 1
          })
        }
      }

      stream.on('data', (chunk: Buffer | string) => {
        if (settled) return
        rawBuf += chunk.toString()

        if (cmdSent) {
          const match = rawBuf.match(/__PM_S__(\d+):([A-Za-z0-9+/=\r\n]*):([A-Za-z0-9+/=\r\n]*)__PM_E__/)
          if (match) {
            const code = parseInt(match[1], 10) || 0
            const stdout = Buffer.from(match[2].replace(/\s+/g, ''), 'base64').toString('utf8')
            const stderr = Buffer.from(match[3].replace(/\s+/g, ''), 'base64').toString('utf8')
            finish({ stdout, stderr, code })
          }
          return
        }

        const clean = stripAnsi(rawBuf)
        if (isSudoPolicyDenied(clean)) {
          finish({ stdout: '', stderr: clean.trim(), code: 1 })
          return
        }
        if (pwSent && isSudoBadPassword(clean)) {
          finish({ stdout: '', stderr: clean.trim() || 'Incorrect password.', code: 1 })
          return
        }

        const lastLine = clean.split('\n').pop() || ''
        if (!pwSent && (clean.includes('__PM_PW__') || /password(?:\s+for\s+[^\n:]+)?:\s*$/i.test(lastLine))) {
          if (!password) {
            finish({ stdout: '', stderr: clean.trim() || 'Password is required for elevation.', code: 1 })
            return
          }
          if (promptTimer) {
            clearTimeout(promptTimer)
            promptTimer = null
          }
          pwSent = true
          rawBuf = ''
          stream.write(password + '\n')
          return
        }

        if (/(?:^|\n)[^\n]*[#>$]\s*$/.test(clean) && !clean.includes('__PM_PW__')) {
          if (promptTimer) clearTimeout(promptTimer)
          promptTimer = setTimeout(() => {
            sendCommandPayload()
          }, 50)
        }
      })

      stream.on('exit', (code: number | null) => {
        if (typeof code === 'number') exitCode = code
      })

      stream.on('close', () => {
        if (!settled) {
          const clean = stripAnsi(rawBuf).trim()
          finish({ stdout: '', stderr: clean || 'Elevated PTY session closed unexpectedly.', code: exitCode ?? 1 })
        }
      })
    })
  })
}

async function probeSudoCapability(rawSsh: any, password: string): Promise<SudoCapability> {
  // 1. Probe passwordless sudo strategies (never pipes password into stdin)
  const nopwScript = [
    `if printf 'echo __PM_OK__\\nexit 0\\n' | sudo -n su 2>/dev/null | grep -q '__PM_OK__'; then echo 'PM_RES:su_stdin';`,
    `elif printf 'echo __PM_OK__\\nexit 0\\n' | sudo -n su - 2>/dev/null | grep -q '__PM_OK__'; then echo 'PM_RES:su_dash_stdin';`,
    `elif printf 'echo __PM_OK__\\nexit 0\\n' | sudo -n su root 2>/dev/null | grep -q '__PM_OK__'; then echo 'PM_RES:su_root_stdin';`,
    `elif printf 'echo __PM_OK__\\nexit 0\\n' | sudo -n -s 2>/dev/null | grep -q '__PM_OK__'; then echo 'PM_RES:sudo_s_stdin';`,
    `elif printf 'echo __PM_OK__\\nexit 0\\n' | sudo -n bash 2>/dev/null | grep -q '__PM_OK__'; then echo 'PM_RES:bash_stdin';`,
    `elif printf 'echo __PM_OK__\\nexit 0\\n' | sudo -n sh 2>/dev/null | grep -q '__PM_OK__'; then echo 'PM_RES:sh_stdin';`,
    `elif sudo -n su -c 'echo __PM_OK__' 2>/dev/null | grep -q '__PM_OK__'; then echo 'PM_RES:su_c';`,
    `elif sudo -n -- sh -c 'echo __PM_OK__' 2>/dev/null | grep -q '__PM_OK__'; then echo 'PM_RES:sh_c';`,
    `else _E=$(sudo -n su </dev/null 2>&1 || true); echo "PM_ERR:$_E"; fi`
  ].join(' ')

  const nopwRes = await rawExec(rawSsh, nopwScript, false).catch(() => ({ stdout: '', stderr: '', code: 1 }))
  const nopwOut = nopwRes.stdout + '\n' + nopwRes.stderr
  const nopwMatch = nopwOut.match(/PM_RES:([a-z0-9_]+)/)
  if (nopwMatch) {
    return { strategy: nopwMatch[1] as SudoStrategy, checkedPassword: password }
  }

  let needPty = isSudoTtyRequired(nopwOut)
  let lastError = nopwOut.replace(/^[\s\S]*PM_ERR:/, '').trim()

  // 2. If password available and non-TTY wasn't already flagged as requiretty, probe pipe strategies
  if (password && !needPty) {
    const escPass = password.replace(/'/g, "'\\''")
    const pwProbeScript = [
      `_PW='${escPass}'; _LAST=''; _DENIED=1;`,
      `_try_p() {`,
      `  _R=$( { printf '%s\\n' "$_PW"; printf 'echo __PM_OK__\\nexit 0\\n'; } | sudo -S -p '' $1 2>&1 );`,
      `  case "$_R" in`,
      `    *__PM_OK__*) echo "PM_RES:$2"; return 0 ;;`,
      `    *"try again"*|*"Try again"*|*"incorrect password"*|*"Incorrect password"*|*"Authentication failure"*|*"authentication failure"*|*"passwords do not match"*) echo "PM_BADPW:$_R"; return 2 ;;`,
      `    *"must have a tty"*|*"no tty present"*|*"standard in must be a tty"*) echo "PM_PTY:$_R"; return 3 ;;`,
      `  esac;`,
      `  _LAST="$_R"; return 1;`,
      `};`,
      `_try_c() {`,
      `  _R=$( printf '%s\\n' "$_PW" | sudo -S -p '' "$@" 2>&1 );`,
      `  case "$_R" in`,
      `    *__PM_OK__*) echo "PM_RES:$_CNAME"; return 0 ;;`,
      `    *"try again"*|*"Try again"*|*"incorrect password"*|*"Incorrect password"*|*"Authentication failure"*|*"authentication failure"*) echo "PM_BADPW:$_R"; return 2 ;;`,
      `    *"must have a tty"*|*"no tty present"*) echo "PM_PTY:$_R"; return 3 ;;`,
      `  esac;`,
      `  _LAST="$_R"; return 1;`,
      `};`,
      `_try_p "su" "su_stdin"; _RC=$?; if [ "$_RC" -eq 0 ] || [ "$_RC" -ge 2 ]; then exit 0; fi;`,
      `_try_p "su -" "su_dash_stdin"; _RC=$?; if [ "$_RC" -eq 0 ] || [ "$_RC" -ge 2 ]; then exit 0; fi;`,
      `_try_p "su root" "su_root_stdin"; _RC=$?; if [ "$_RC" -eq 0 ] || [ "$_RC" -ge 2 ]; then exit 0; fi;`,
      `_try_p "-s" "sudo_s_stdin"; _RC=$?; if [ "$_RC" -eq 0 ] || [ "$_RC" -ge 2 ]; then exit 0; fi;`,
      `_try_p "bash" "bash_stdin"; _RC=$?; if [ "$_RC" -eq 0 ] || [ "$_RC" -ge 2 ]; then exit 0; fi;`,
      `_try_p "sh" "sh_stdin"; _RC=$?; if [ "$_RC" -eq 0 ] || [ "$_RC" -ge 2 ]; then exit 0; fi;`,
      `_CNAME="su_c"; _try_c su -c "echo __PM_OK__"; _RC=$?; if [ "$_RC" -eq 0 ] || [ "$_RC" -ge 2 ]; then exit 0; fi;`,
      `_CNAME="sh_c"; _try_c -- sh -c "echo __PM_OK__"; _RC=$?; if [ "$_RC" -eq 0 ] || [ "$_RC" -ge 2 ]; then exit 0; fi;`,
      `echo "PM_LAST:$_LAST"`
    ].join(' ')

    const pwRes = await rawExec(rawSsh, pwProbeScript, false).catch(() => ({ stdout: '', stderr: '', code: 1 }))
    const pwOut = pwRes.stdout + '\n' + pwRes.stderr

    const pwMatch = pwOut.match(/PM_RES:([a-z0-9_]+)/)
    if (pwMatch) {
      return { strategy: pwMatch[1] as SudoStrategy, checkedPassword: password }
    }
    if (pwOut.includes('PM_BADPW:')) {
      const msg = pwOut.split('PM_BADPW:')[1].trim() || 'Incorrect sudo password.'
      return { strategy: 'none', checkedPassword: password, error: msg }
    }
    if (pwOut.includes('PM_PTY:')) {
      needPty = true
      lastError = pwOut.split('PM_PTY:')[1].trim()
    } else if (pwOut.includes('PM_LAST:')) {
      lastError = pwOut.split('PM_LAST:')[1].trim() || lastError
    }
  }

  // 3. If requiretty or all pipe su methods failed without explicit bad password, try PTY strategies
  const ptyCandidates: SudoStrategy[] = []
  if (needPty || !isSudoPolicyDenied(lastError)) {
    ptyCandidates.push('su_stdin_pty', 'su_dash_stdin_pty', 'su_root_stdin_pty')
  }
  if (password && !isSudoBadPassword(lastError)) {
    ptyCandidates.push('direct_su_pty')
  }

  for (const cand of ptyCandidates) {
    const ptyProbe = await execViaPtyStrategy(rawSsh, cand, 'echo __PM_OK__', password, 15000).catch((e) => ({
      stdout: '',
      stderr: e instanceof Error ? e.message : String(e),
      code: 1
    }))
    if (ptyProbe.code === 0 && ptyProbe.stdout.includes('__PM_OK__')) {
      return { strategy: cand, checkedPassword: password }
    }
    if (cand !== 'direct_su_pty' && isSudoBadPassword(ptyProbe.stderr)) {
      return { strategy: 'none', checkedPassword: password, error: ptyProbe.stderr || 'Incorrect sudo password.' }
    }
    if (ptyProbe.stderr) {
      lastError = ptyProbe.stderr
    }
  }

  return {
    strategy: 'none',
    checkedPassword: password,
    error: lastError || 'Sudo elevation is not permitted on this server.'
  }
}

export async function execElevatedCommand(
  session: SudoSessionLike,
  command: string,
  sudoPassword?: string
): Promise<ExecResult> {
  const rawSsh = session.client?.client
  if (!rawSsh || typeof rawSsh.exec !== 'function') {
    throw new Error('Underlying SSH client connection is not available.')
  }

  const password =
    sudoPassword !== undefined && sudoPassword !== null && sudoPassword !== ''
      ? sudoPassword
      : session.config?.password || ''

  // Invalidate cached strategy if a different explicit sudo password was provided
  if (sudoPassword && session.sudoCapability && session.sudoCapability.checkedPassword !== password) {
    session.sudoCapability = undefined
    session.sudoProbePromise = undefined
  }

  const ensureCapability = async (): Promise<SudoCapability> => {
    if (session.sudoCapability) return session.sudoCapability
    if (!session.sudoProbePromise) {
      session.sudoProbePromise = probeSudoCapability(rawSsh, password)
        .then((cap) => {
          session.sudoCapability = cap
          session.sudoProbePromise = undefined
          return cap
        })
        .catch((err) => {
          session.sudoProbePromise = undefined
          throw err
        })
    }
    return session.sudoProbePromise
  }

  const runWithStrategy = async (strategy: SudoStrategy): Promise<ExecResult> => {
    if (strategy === 'none') {
      return {
        stdout: '',
        stderr: session.sudoCapability?.error || 'Sudo elevation is not permitted on this server.',
        code: 1
      }
    }
    if (strategy.endsWith('_pty')) {
      return execViaPtyStrategy(rawSsh, strategy, command, password)
    }
    return execViaPipeStrategy(rawSsh, strategy, command, password)
  }

  let cap = await ensureCapability()
  if (cap.strategy === 'none') {
    return {
      stdout: '',
      stderr: cap.error || 'Sudo elevation is not permitted on this server.',
      code: 1
    }
  }

  const res = await runWithStrategy(cap.strategy)
  const combinedErr = `${res.stderr}\n${res.stdout}`
  if (
    res.code !== 0 &&
    (isSudoPolicyDenied(combinedErr) ||
      isSudoTtyRequired(combinedErr) ||
      (!password && isSudoPasswordNeeded(combinedErr)))
  ) {
    // Re-probe once in case session environment/sudoers state changed
    session.sudoCapability = undefined
    cap = await ensureCapability()
    if (cap.strategy === 'none') {
      return {
        stdout: '',
        stderr: cap.error || combinedErr.trim() || 'Sudo elevation failed.',
        code: 1
      }
    }
    return runWithStrategy(cap.strategy)
  }

  return res
}
