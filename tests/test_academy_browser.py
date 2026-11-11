"""Real headless-browser smoke for APEX Response Lab at desktop and mobile widths.

Uses the source HTML/CSS/JS and the production static asset handler. An extra
inline QA-only script records observable results without touching the checked-in
academy source. Skips only on hosts without a browser binary.
"""
import html
from http.server import ThreadingHTTPServer
import json
import re
import shutil
import subprocess
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

import content_worker as worker

QA_SCRIPT = r'''<script>
window.addEventListener('DOMContentLoaded', function () {
  const checks = {};
  const error = (fn) => { try { return fn(); } catch (e) { return 'ERROR: ' + e.message; } };
  checks.viewport = window.innerWidth;
  checks.cssLoaded = getComputedStyle(document.documentElement).backgroundColor === 'rgb(244, 245, 238)';
  checks.heroColumns = getComputedStyle(document.querySelector('.hero')).gridTemplateColumns.split(' ').length;
  document.querySelectorAll('details').forEach(d => { d.open = true; });
  checks.noHorizontalOverflow = document.documentElement.scrollWidth <= window.innerWidth + 2;
  checks.lessons = document.querySelectorAll('[data-lesson]').length;
  checks.canonical = document.querySelector('link[rel=canonical]').href;
  checks.leadLink = document.querySelector('.next a.button').getAttribute('href');
  checks.checkoutLinks = [...document.querySelectorAll('a')].filter(a => /checkout\.stripe\.com/.test(a.href)).length;
  checks.builder = error(() => {
    const form = document.getElementById('builder');
    form.elements.business.value = 'QA Cleaning Company';
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    return !document.getElementById('drafts').hidden &&
      document.getElementById('reply-inquiry').textContent.includes('QA Cleaning Company') &&
      document.getElementById('reply-handoff').textContent.includes('QA Cleaning Company');
  });
  checks.untrustedBusinessName = error(() => {
    const form = document.getElementById('builder');
    const untrusted = 'Example <img src=x onerror=alert(1)> & Sons';
    const originalFetch = window.fetch;
    const originalXhrOpen = XMLHttpRequest.prototype.open;
    let attemptedNetworkCalls = 0;
    window.fetch = (...args) => { attemptedNetworkCalls++; return originalFetch(...args); };
    XMLHttpRequest.prototype.open = function (...args) {
      attemptedNetworkCalls++;
      return originalXhrOpen.apply(this, args);
    };
    try {
      form.elements.business.value = untrusted;
      form.dispatchEvent(new Event('input', { bubbles: true }));
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      const output = document.getElementById('reply-inquiry');
      const stored = Object.keys(localStorage).map(key => localStorage.getItem(key)).join(' ');
      return output.textContent.includes(untrusted) &&
        output.querySelector('img') === null &&
        !stored.includes(untrusted) &&
        attemptedNetworkCalls === 0;
    } finally {
      window.fetch = originalFetch;
      XMLHttpRequest.prototype.open = originalXhrOpen;
    }
  });
  checks.checklist = error(() => {
    const item = document.querySelector('[data-lesson]');
    item.checked = true;
    item.dispatchEvent(new Event('change', { bubbles: true }));
    return document.getElementById('progress').textContent.startsWith('1 of 4');
  });
  checks.download = error(() => {
    const original = URL.createObjectURL;
    let created = false;
    URL.createObjectURL = function (blob) { created = blob.size > 500; return original.call(URL, blob); };
    try { document.getElementById('download').click(); } finally { URL.createObjectURL = original; }
    return created;
  });
  const report = document.createElement('pre');
  report.id = 'apex-browser-qa';
  report.textContent = JSON.stringify(checks);
  document.body.appendChild(report);
});
</script>'''


class QAHandler(worker.Handler):
    """Patch only served HTML to append a read-only browser QA probe."""
    def do_GET(self):
        if urlsplit(self.path).path != '/academy':
            return super().do_GET()
        body = (worker.ROOT / 'sales' / 'academy.html').read_bytes()
        body = body.replace(b'https://ai-revenue-agent-seven.vercel.app', worker.PUBLIC_ORIGIN.encode())
        assert body.count(b'</body>') == 1
        body = body.replace(b'</body>', QA_SCRIPT.encode('utf-8') + b'</body>')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src https://wuzmqruxdclstezitsbf.supabase.co; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)


class AcademyBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chrome = next((shutil.which(name) for name in ('google-chrome', 'chromium', 'chromium-browser') if shutil.which(name)), None)
        if not cls.chrome:
            raise unittest.SkipTest('Chrome/Chromium is unavailable; browser acceptance remains unverified')
        cls.egress = patch.object(worker, 'reserve_egress', return_value=True)
        cls.egress.start()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), QAHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'server', None):
            cls.server.shutdown()
            cls.server.server_close()
            cls.thread.join()
        if getattr(cls, 'egress', None):
            cls.egress.stop()

    def check_width(self, width):
        origin = 'http://127.0.0.1:' + str(self.server.server_port)
        cmd = [self.chrome, '--headless=new', '--no-sandbox', '--disable-gpu',
               '--disable-dev-shm-usage', '--disable-background-networking',
               '--disable-extensions', '--no-first-run', '--force-device-scale-factor=1',
               '--virtual-time-budget=2500', '--window-size=' + str(width) + ',900',
               '--dump-dom', origin + '/academy']
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=40, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr[-2500:])
        match = re.search(r'<pre id="apex-browser-qa">([^<]+)</pre>', completed.stdout)
        self.assertIsNotNone(match, completed.stderr[-2500:] + completed.stdout[-500:])
        checks = json.loads(html.unescape(match.group(1)))
        self.assertTrue(checks['cssLoaded'], checks)
        self.assertTrue(checks['noHorizontalOverflow'], checks)
        self.assertEqual(checks['lessons'], 4)
        self.assertEqual(checks['checkoutLinks'], 0)
        self.assertEqual(checks['canonical'], worker.PUBLIC_ORIGIN + '/academy')
        self.assertIn('utm_source=academy', checks['leadLink'])
        for key in ('builder', 'untrustedBusinessName', 'checklist', 'download'):
            self.assertIs(checks[key], True, checks)
        if width < 720:
            self.assertLessEqual(checks['viewport'], 720, checks)
            self.assertEqual(checks['heroColumns'], 1, checks)
        else:
            self.assertGreater(checks['viewport'], 720, checks)
            self.assertEqual(checks['heroColumns'], 2, checks)

    def test_mobile_browser(self):
        self.check_width(390)

    def test_desktop_browser(self):
        self.check_width(1280)


if __name__ == '__main__':
    unittest.main()
