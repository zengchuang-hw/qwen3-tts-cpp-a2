# build.exit capture incident (kept visible, not deleted)

First capture of the build exit code was polluted by the calling shell, not by the
build itself.

- Command shape used: `... ; echo $? > logs/build.exit` sent through PowerShell.
  PowerShell expanded `$?` in its own scope and rendered the boolean `True`, so
  `logs/build.exit` contained `True` instead of a numeric status.
- The build itself had already reached `[100%] Built target _qtts_native`; the
  pollution affected only the recorded status file.
- Because the verification re-run overwrote `logs/build.exit` before this note was
  written, the polluted value no longer exists as a standalone file. The verbatim
  value it held is kept in `build-exit-1-polluted.transcript.txt` (`True`), next to
  this note, rather than deleted or silently replaced.

## Verification re-run (real exit code)

```
$ cd /work/c009 && cmake --build build -j 2 > logs/build-verify.log 2>&1
$ echo $? > logs/build.exit        # captured inside bash, not PowerShell
$ cat logs/build.exit
0
```

Log evidence: `logs/build.log` (fresh configure+build, ends at
`[100%] Built target _qtts_native`), `logs/build-verify.log` (idempotent
verification build), `logs/build.exit` = `0`.

Checks:

```
$ [ "$(cat /work/c009/logs/build.exit)" = "0" ] && echo build_ok
build_ok
```

PowerShell equivalent, using the real native exit code rather than `$?`:

```
PS> cmake --build build -j 2; if ($LASTEXITCODE -eq 0) { "build_ok" }
```

## Rule adopted for the rest of this iteration

- Exit codes are captured inside the container shell that ran the command
  (`rc=$?; echo $rc > file`), or via `$LASTEXITCODE` in PowerShell.
- No boolean can reach a numeric field; the stored value must match `^[0-9]+$`
  (or a negative signal code).
