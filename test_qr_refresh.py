#!/usr/bin/env python3
"""Regression test: animated BankID QR must refresh on every poll, and the
poll loop must follow the server-provided next_poll_url chain.

Run with: python3 test_qr_refresh.py
"""
import os
import sys
import time
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kivra.auth import KivraAuth


class FakeResp:
    def __init__(self, data):
        self._d = data

    def json(self):
        return self._d


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.i = 0

    def get(self, url):
        self.calls.append(url)
        d = self.responses[min(self.i, len(self.responses) - 1)]
        self.i += 1
        return FakeResp(d)


class FakeProvider:
    supports_qr_refresh = True

    def display_qr_code(self, path):
        pass

    def report_authentication_success(self):
        pass

    def report_completion(self, stats):
        pass


def main():
    time.sleep = lambda *a, **k: None  # no real waiting

    auth = KivraAuth(tempfile.mkdtemp(), FakeProvider())
    rendered = []
    auth._render_and_display_qr = lambda v: rendered.append(v)
    auth.session = FakeSession([
        {'status': 'pending', 'qr_code': 'bankid.t.3.aaa', 'next_poll_url': '/p2'},
        {'status': 'pending', 'qr_code': 'bankid.t.5.bbb', 'next_poll_url': '/p3'},
        {'status': 'stop'},  # unknown status -> sys.exit, ends loop
    ])
    try:
        auth._poll_for_auth('/p1', 'code', 'verifier')
    except SystemExit:
        pass

    assert rendered == ['bankid.t.3.aaa', 'bankid.t.5.bbb'], f"QR not refreshed: {rendered}"
    assert auth.session.calls[0] == 'https://app.api.kivra.com/p1', auth.session.calls
    assert auth.session.calls[1] == 'https://app.api.kivra.com/p2', "did not follow next_poll_url"
    print("PASS: QR refreshed per poll + next_poll_url followed ->", rendered)


if __name__ == '__main__':
    main()
