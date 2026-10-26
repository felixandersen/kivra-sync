#!/usr/bin/env python3
"""Offline terminal QR regression tests. Run: python -m unittest test_terminal_qr"""

import io
import logging
import os
import tempfile
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

import qrcode

from interaction.terminal import TerminalInteractionProvider
from kivra.auth import KivraAuth


class FakeTTY(io.StringIO):
    def __init__(self):
        super().__init__()
        self.tty = True
        self.output_encoding = 'utf-8'
        self.reconfigured = []

    @property
    def encoding(self):
        return self.output_encoding

    def isatty(self):
        return self.tty

    def reconfigure(self, *, encoding):
        self.reconfigured.append(encoding)
        self.output_encoding = encoding


class TerminalQRTests(unittest.TestCase):
    def setUp(self):
        self.output = FakeTTY()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch('interaction.terminal.sys.stdout', self.output))
        self.size = stack.enter_context(patch(
            'interaction.terminal.shutil.get_terminal_size',
            return_value=os.terminal_size((120, 60)),
        ))
        self.windows_console = stack.enter_context(patch('interaction.terminal.os.system'))

    def test_non_tty_fails_during_construction(self):
        self.output.tty = False
        with self.assertRaisesRegex(RuntimeError, 'interactive terminal.*web or ntfy'):
            TerminalInteractionProvider()
        self.windows_console.assert_not_called()
        self.assertEqual(self.output.getvalue(), '')

    def test_windows_console_initialized_once(self):
        with patch('interaction.terminal.os.name', 'nt'):
            provider = TerminalInteractionProvider()
            provider.display_qr_payload('first-frame')
            provider.display_qr_payload('second-frame')
        self.windows_console.assert_called_once_with('')

    def test_small_terminal_rejected_during_construction(self):
        for size in [(59, 32), (60, 31)]:
            with self.subTest(size=size):
                self.size.return_value = os.terminal_size(size)
                with self.assertRaisesRegex(RuntimeError, '60 columns and 32 rows before login'):
                    TerminalInteractionProvider()
        self.windows_console.assert_not_called()
        self.assertEqual(self.output.getvalue(), '')

    def test_preflight_minimum_fits_typical_bankid_payload(self):
        self.size.return_value = os.terminal_size((60, 32))
        provider = TerminalInteractionProvider()
        provider.display_qr_payload(
            'bankid.01234567-89ab-cdef-0123-456789abcdef.1234567890.'
            + 'abcdef0123456789' * 4
        )
        self.assertIn(TerminalInteractionProvider.STATUS, self.output.getvalue())

    def test_initial_frame_rejects_insufficient_size(self):
        for size, dimension in [((10, 60), 'columns'), ((120, 10), 'rows')]:
            with self.subTest(dimension=dimension):
                self.size.return_value = os.terminal_size((120, 60))
                provider = TerminalInteractionProvider()
                self.size.return_value = os.terminal_size(size)
                with self.assertRaisesRegex(RuntimeError, dimension):
                    provider.display_qr_payload('bankid.test-frame')
                self.assertEqual(self.output.getvalue(), '')

    def test_resize_skips_then_resumes_with_anchored_fresh_frame(self):
        provider = TerminalInteractionProvider()
        provider.display_qr_payload('bankid.first-frame')
        first = self.output.getvalue()
        self.size.return_value = os.terminal_size((10, 10))
        provider.display_qr_payload('bankid.skipped-frame')
        self.assertEqual(self.output.getvalue(), first)
        self.size.return_value = os.terminal_size((120, 60))
        provider.display_qr_payload('bankid.next-frame')
        second = self.output.getvalue()[len(first):]
        self.assertTrue(first.startswith('\x1b[2J\x1b[H'))
        self.assertTrue(second.startswith('\x1b[H'))
        self.assertNotIn('\x1b[2J', second)
        self.assertIn(f'\x1b[J{TerminalInteractionProvider.STATUS}\n', second)
        self.assertNotEqual(first, second)
        self.assertNotIn('\x1b7', second)
        self.assertNotIn('\x1b8', second)

    def test_half_blocks_preserve_matrix_colours_and_quiet_zone(self):
        payload = 'bankid.test-token.123.' + 'abcdef0123456789' * 4
        qr = qrcode.QRCode(border=4, box_size=1)
        qr.add_data(payload)
        qr.make(fit=True)
        expected = qr.get_matrix()
        TerminalInteractionProvider().display_qr_payload(payload)
        output = self.output.getvalue()
        prefix = '\x1b[2J\x1b[H\x1b[30;47m'
        self.assertTrue(output.startswith(prefix))
        lines = output[len(prefix):].split('\x1b[0m', 1)[0].splitlines()
        self.assertEqual(len(lines), (len(expected) + 1) // 2)
        # With black foreground and white background, each glyph describes
        # the dark top/bottom modules independently of the rendering code.
        modules = {' ': (False, False), '▀': (True, False),
                   '▄': (False, True), '█': (True, True)}
        decoded = []
        for line in lines:
            self.assertEqual(len(line), len(expected[0]))
            decoded.extend([[modules[char][row] for char in line] for row in (0, 1)])
        self.assertEqual(decoded[:len(expected)], expected)
        self.assertFalse(any(decoded[-1]))
        self.assertTrue(all(not any(row) for row in decoded[:4]))
        self.assertTrue(all(not any(row[:4] + row[-4:]) for row in decoded))
        self.assertTrue(output.endswith(f'\x1b[0m\x1b[J{TerminalInteractionProvider.STATUS}\n'))

    def test_poll_error_remains_visible_after_final_refresh(self):
        provider = TerminalInteractionProvider()
        with tempfile.TemporaryDirectory() as temp_dir:
            auth = KivraAuth(temp_dir, provider)
            auth.session.get = Mock(side_effect=[
                Mock(json=lambda: {'status': 'pending', 'qr_code': 'bankid.fresh-frame'}),
                Mock(json=lambda: {'status': 'stop'}),
            ])
            auth._render_and_display_qr('bankid.initial-frame')
            with patch('kivra.auth.time.sleep'), self.assertLogs(level='ERROR'):
                logging.getLogger().addHandler(logging.StreamHandler(self.output))
                with self.assertRaises(SystemExit):
                    auth._poll_for_auth('/poll', 'test-code', 'test-verifier')
        output = self.output.getvalue()
        error_position = output.index('Error during polling. Status: stop')
        self.assertNotIn('\x1b[H', output[error_position:])
        self.assertNotIn('\x1b[J', output[error_position:])
        self.assertEqual(auth.session.get.call_count, 2)
        # Auth leaves the status to the provider instead of printing below the QR.
        self.assertNotIn('Waiting for BankID', output)
        self.assertNotIn(f'{TerminalInteractionProvider.STATUS}\n.', output)

    def test_output_encoding_is_checked_before_login(self):
        self.output.output_encoding = 'UTF_8'
        TerminalInteractionProvider()
        self.assertEqual(self.output.reconfigured, [])
        self.output.output_encoding = 'cp1252'
        TerminalInteractionProvider()
        self.assertEqual(self.output.reconfigured, ['utf-8'])

    def test_image_path_cannot_open_a_viewer(self):
        with self.assertRaisesRegex(NotImplementedError, 'QR payload text'):
            TerminalInteractionProvider().display_qr_code('unused.png')

    def test_console_reports_partial_downloads(self):
        provider = TerminalInteractionProvider()
        provider.report_completion({
            'receipts_total': 0, 'receipts_fetched': 0, 'receipts_stored': 0,
            'letters_total': 3, 'letters_fetched': 1, 'letters_stored': 1,
        })
        self.assertEqual(self.output.getvalue(),
                         '\nAll done!\nReceipts: 0 new items, 0 fetched\n'
                         'Letters: 1 new items, 1 of 3 fetched\n')

    def test_console_reports_missing_counters_as_zero(self):
        TerminalInteractionProvider().report_completion({'letters_total': 3})
        self.assertEqual(self.output.getvalue(),
                         '\nAll done!\nReceipts: 0 new items, 0 fetched\n'
                         'Letters: 0 new items, 0 of 3 fetched\n')


if __name__ == '__main__':
    unittest.main()
