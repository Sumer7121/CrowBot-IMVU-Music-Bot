"""Start a local virtual display, then hand PID 1 to gunicorn for SIGTERM."""
import os
import subprocess
import time
from pathlib import Path

display = subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1024x768x24', '-nolisten', 'tcp'])
for _ in range(50):
    if display.poll() is not None:
        raise SystemExit('Virtual display could not start')
    if Path('/tmp/.X11-unix/X99').exists():
        break
    time.sleep(.1)
else:
    display.terminate()
    raise SystemExit('Virtual display did not become ready')
# Probe a blank page only: no user/session data enters this startup check.
try:
    probe = subprocess.run(['chromium', '--headless', '--no-first-run',
        '--disable-dev-shm-usage', '--dump-dom', 'about:blank'],
        capture_output=True, text=True, timeout=12)
    print('CHROMIUM STARTUP CHECK: exit=' + str(probe.returncode), flush=True)
    for line in probe.stderr.splitlines()[:8]:
        print('CHROMIUM STARTUP: ' + line[:500], flush=True)
except subprocess.TimeoutExpired:
    print('CHROMIUM STARTUP CHECK: timed out', flush=True)
os.execvp('gunicorn' , ['gunicorn', '--bind', '0.0.0.0:'+os.environ.get('PORT', '10000'),
    '--workers', '1', '--threads', '16', '--timeout', '120', '--graceful-timeout', '20',
    '--access-logfile', '/dev/null', 'cloud.server:app'])
