"""Display BankID's refreshing QR directly in the terminal."""

import codecs
import os
import shutil
import sys

import qrcode

from interaction.base import InteractionProvider


class TerminalInteractionProvider(InteractionProvider):
    supports_qr_refresh = True

    def __init__(self):
        super().__init__()
        if not sys.stdout.isatty():
            raise RuntimeError(
                'Terminal QR needs an interactive terminal; '
                'use --interaction-provider web or ntfy instead'
            )
        size = shutil.get_terminal_size()
        if size.columns < 60 or size.lines < 32:
            raise RuntimeError(
                'Terminal QR needs at least 60 columns and 32 rows before login; '
                f'current size is {size.columns} columns and {size.lines} rows. '
                'Enlarge the terminal or use --interaction-provider web or ntfy'
            )
        self._ensure_utf8(sys.stdout)
        if os.name == 'nt':
            # Initialize Windows console ANSI handling before the first frame.
            os.system('')
        self._frame_drawn = False

    def display_qr_code(self, qr_image_path):
        raise NotImplementedError('Terminal QR requires QR payload text, not an image')

    def display_qr_payload(self, payload):
        qr = qrcode.QRCode(border=4, box_size=1)
        qr.add_data(payload)
        qr.make(fit=True)
        matrix = qr.get_matrix()

        output = sys.stdout
        width = len(matrix[0])
        # Authentication messages need room below the first frame.
        required_rows = (len(matrix) + 1) // 2 + 5
        size = shutil.get_terminal_size()
        fits = width < size.columns and required_rows <= size.lines

        if not self._frame_drawn:
            if width >= size.columns:
                raise RuntimeError(f'Terminal QR needs at least {width + 1} columns; current width is {size.columns}')
            if required_rows > size.lines:
                raise RuntimeError(f'Terminal QR needs at least {required_rows} rows; current height is {size.lines}')
        # The window may have been resized mid-login; skip this frame rather
        # than abort, and redraw once the QR fits again.
        if not fits:
            return

        # Anchor each frame so scrolling progress dots cannot move the QR.
        output.write('\x1b[H' if self._frame_drawn else '\x1b[2J\x1b[H')
        self._draw(output, matrix)
        output.write('\x1b[JScan with the BankID app.')
        output.flush()
        self._frame_drawn = True

    def report_completion(self, stats):
        print('\nAll done!')
        for label, key in [('Receipts', 'receipts'), ('Letters', 'letters')]:
            fetched = stats.get(f'{key}_fetched', 0)
            total = stats.get(f'{key}_total', 0)
            count = fetched if fetched == total else f'{fetched} of {total}'
            print(f'{label}: {stats.get(f"{key}_stored", 0)} new items, {count} fetched')

    def report_authentication_success(self):
        print('BankID authentication successful! Starting data sync...')

    @staticmethod
    def _ensure_utf8(output):
        encoding = output.encoding or 'ascii'
        try:
            is_utf8 = codecs.lookup(encoding).name == 'utf-8'
        except LookupError:
            is_utf8 = False
        if is_utf8:
            return
        if not hasattr(output, 'reconfigure'):
            raise RuntimeError(f'Terminal QR needs UTF-8 output; current encoding is {encoding}')
        output.reconfigure(encoding='utf-8')

    @staticmethod
    def _draw(output, matrix):
        # Each character holds two vertical modules; pad an odd final row white.
        rows = matrix + ([[False] * len(matrix[0])] if len(matrix) % 2 else [])
        try:
            output.write('\x1b[30;47m')
            for top, bottom in zip(rows[::2], rows[1::2]):
                output.write(''.join(' ▀▄█'[t + 2 * b] for t, b in zip(top, bottom)) + '\n')
        finally:
            output.write('\x1b[0m')
            output.flush()
