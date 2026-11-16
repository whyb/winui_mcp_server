import io
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from winui_mcp import cli_gateway


class CliGatewayTests(unittest.TestCase):
    def test_list_windows_does_not_require_target(self):
        result = {"success": True, "message": "ok", "data": {"windows": []}}
        with patch.object(sys, "argv", ["cli_gateway.py", "list-windows"]), \
             patch.object(cli_gateway.sk, "list_windows", return_value=result) as list_windows, \
             redirect_stdout(io.StringIO()):
            cli_gateway.main()

        list_windows.assert_called_once()

    def test_window_id_is_forwarded_to_driver(self):
        result = {"success": True, "message": "ok", "data": {}}
        with patch.object(sys, "argv", [
                 "cli_gateway.py", "--window-id", "0x1234", "state"
             ]),              patch.object(cli_gateway, "AppDriver") as app_driver,              patch.object(cli_gateway.sk, "get_window_state", return_value=result),              redirect_stdout(io.StringIO()):
            cli_gateway.main()

        app_driver.assert_called_once_with(
            window_title=None,
            window_class=None,
            process_name=None,
            window_id="0x1234",
        )

    def test_click_accepts_stable_element_id(self):
        result = {"success": True, "message": "ok", "data": {}}
        with patch.object(sys, "argv", [
                 "cli_gateway.py", "--window-id", "0x1234", "click",
                 "--element-id", "e42",
             ]),              patch.object(cli_gateway, "AppDriver"),              patch.object(cli_gateway.sk, "activate_reference", return_value=result) as action,              redirect_stdout(io.StringIO()):
            cli_gateway.main()

        self.assertEqual(action.call_args.args[1], "click")
        self.assertEqual(action.call_args.args[2], "e42")

    def test_regular_command_still_requires_target(self):
        with patch.object(sys, "argv", ["cli_gateway.py", "state"]), \
             redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as raised:
                cli_gateway.main()

        self.assertEqual(raised.exception.code, 1)
        self.assertIn("Specify --window", output.getvalue())


if __name__ == "__main__":
    unittest.main()
