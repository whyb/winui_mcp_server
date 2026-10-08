import io
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import cli_gateway


class CliGatewayTests(unittest.TestCase):
    def test_list_windows_does_not_require_target(self):
        result = {"success": True, "message": "ok", "data": {"windows": []}}
        with patch.object(sys, "argv", ["cli_gateway.py", "list-windows"]), \
             patch.object(cli_gateway.sk, "list_windows", return_value=result) as list_windows, \
             redirect_stdout(io.StringIO()):
            cli_gateway.main()

        list_windows.assert_called_once()

    def test_regular_command_still_requires_target(self):
        with patch.object(sys, "argv", ["cli_gateway.py", "state"]), \
             redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as raised:
                cli_gateway.main()

        self.assertEqual(raised.exception.code, 1)
        self.assertIn("Specify --window", output.getvalue())


if __name__ == "__main__":
    unittest.main()
