"""Display BankID's refreshing QR directly in the terminal."""

import codecs
import shutil
import sys

import qrcode

from interaction.local import LocalInteractionProvider


class TerminalInteractionProvider(LocalInteractionProvider):
    supports_qr_refresh = True

    def __init__(self):
        self._frame_drawn = False

    def display_qr_payload(self, payload):
        qr = qrcode.QRCode(border=4, box_size=1)
        qr.add_data(payload)
        qr.make(fit=True)
        matrix = qr.get_matrix()

        output = sys.stdout
        width = len(matrix[0]) * 2
        # Authentication messages need room below the first frame.
        required_rows = len(matrix) + 5
        size = shutil.get_terminal_size()
        fits = width < size.columns and required_rows <= size.lines

        if not self._frame_drawn:
            if not output.isatty():
                raise RuntimeError(
                    'Terminal QR needs an interactive terminal; '
                    'use --interaction-provider web or ntfy instead'
                )
            self._ensure_utf8(output)
            if width >= size.columns:
                raise RuntimeError(f'Terminal QR needs at least {width + 1} columns; current width is {size.columns}')
            if required_rows > size.lines:
                raise RuntimeError(f'Terminal QR needs at least {required_rows} rows; current height is {size.lines}')
            output.write('\x1b[2J\x1b[H')
            self._draw(output, matrix)
            self._frame_drawn = True
            return

        # The window may have been resized mid-login; skip this frame rather
        # than abort, and redraw once the QR fits again.
        if not fits:
            return

        # Redraw in place, keeping the status lines and progress dots below.
        output.write('\x1b7\x1b[H')
        self._draw(output, matrix, restore_cursor=True)

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
    def _draw(output, matrix, restore_cursor=False):
        try:
            output.write('\x1b[30;47m')
            for row in matrix:
                output.write(''.join('██' if module else '  ' for module in row) + '\n')
        finally:
            output.write('\x1b[0m')
            if restore_cursor:
                output.write('\x1b8')
            output.flush()
