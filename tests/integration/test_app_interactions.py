"""Live interaction tests that drive a real Notepad window through MCP tools.

Coverage: launch, window state, title-bar drag, random alphanumeric typing,
keyboard copy/paste, right-click context menu copy/paste, top menu click,
vertical scrollbar drag when present, and safe close. Opt-in because the tests
control a real desktop window: set WINUI_RUN_APP_INTERACTION=1.
"""
import asyncio
import os
import random
import string
import tempfile
import unittest
from pathlib import Path

from tests.integration.mcp_harness import FreshMcpSession, structured


def _random_text(length: int = 12) -> str:
    return "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(length)
    )


@unittest.skipUnless(
    os.name == "nt" and os.environ.get("WINUI_RUN_APP_INTERACTION") == "1",
    "Set WINUI_RUN_APP_INTERACTION=1 to run live app interaction tests.",
)
class NotepadInteractionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", prefix="winui-interaction-",
            delete=False, encoding="utf-8",
        )
        handle.write("winui interaction fixture\n")
        handle.close()
        self._temp_path = handle.name
        self._session_context = FreshMcpSession()
        self.session = await self._session_context.__aenter__()
        launched = structured(await self.session.call_tool("launch_app", {
            "app": "notepad",
            "arguments": self._temp_path,
            "timeout": 15,
        }))
        self.assertTrue(launched["success"], launched)
        self.window_id = launched["data"]["window"]["window_id"]

    async def asyncTearDown(self):
        try:
            await self._close_and_discard()
        except Exception:
            pass
        await self._session_context.__aexit__(None, None, None)
        Path(self._temp_path).unlink(missing_ok=True)

    async def _snapshot_elements(self, interactive_only: bool = True):
        result = structured(await self.session.call_tool("snapshot", {
            "window_id": self.window_id,
            "depth": 20,
            "max_nodes": 400,
            "interactive_only": interactive_only,
        }))
        self.assertTrue(result["success"], result)
        return result["data"]["elements"]

    async def _editor_element(self):
        elements = await self._snapshot_elements(interactive_only=True)
        return next(
            (item for item in elements
             if item.get("control_type") == "DocumentControl"),
            None,
        )

    async def _get_value(self, element_id: str) -> str:
        result = structured(await self.session.call_tool("get_value", {
            "window_id": self.window_id, "element_id": element_id,
        }))
        self.assertTrue(result["success"], result)
        return result["data"].get("value", "")

    async def _close_and_discard(self) -> bool:
        """Close Notepad and dismiss its save-changes dialog when present."""
        try:
            closed = structured(await self.session.call_tool("window_action", {
                "window_id": self.window_id, "action": "close",
            }))
        except Exception:
            return False
        if not closed.get("success"):
            return False
        for _ in range(10):
            await asyncio.sleep(0.3)
            listed = structured(await self.session.call_tool("list_windows", {
                "visible_only": True, "include_hidden": False,
            }))
            if not listed.get("success"):
                continue
            windows = listed["data"]["windows"]
            if not any(item.get("window_id") == self.window_id for item in windows):
                return True
            for window in windows:
                if window.get("window_id") == self.window_id:
                    continue
                process = str(window.get("process_name") or "").casefold()
                title = str(window.get("title") or "")
                if ("notepad" not in process
                        and "记事本" not in title
                        and "Notepad" not in title):
                    continue
                snap = structured(await self.session.call_tool("snapshot", {
                    "window_id": window["window_id"], "depth": 12,
                    "max_nodes": 200, "interactive_only": True,
                }))
                if not snap.get("success"):
                    continue
                discard = next(
                    (item for item in snap["data"]["elements"]
                     if item.get("name") in {"不保存", "Don't Save", "不儲存"}),
                    None,
                )
                if discard is None:
                    continue
                structured(await self.session.call_tool("click", {
                    "window_id": window["window_id"],
                    "element_id": discard["element_id"],
                }))
                await asyncio.sleep(0.3)
                return True
        return False

    async def test_launch_state_and_snapshot(self):
        state = structured(await self.session.call_tool("get_window_state", {
            "window_id": self.window_id,
        }))
        self.assertTrue(state["success"], state)
        self.assertGreater(state["data"]["width"], 0)
        self.assertGreater(state["data"]["height"], 0)

        elements = await self._snapshot_elements()
        self.assertTrue(elements)
        editor = await self._editor_element()
        self.assertIsNotNone(editor, "Notepad document editor was not found")

    async def test_move_window_with_title_bar_drag(self):
        before = structured(await self.session.call_tool("get_window_state", {
            "window_id": self.window_id,
        }))
        self.assertTrue(before["success"], before)

        moved = structured(await self.session.call_tool("move_window", {
            "window_id": self.window_id,
            "delta_x": 80,
            "delta_y": 60,
            "method": "mouse",
        }))
        self.assertTrue(moved["success"], moved)

        after = structured(await self.session.call_tool("get_window_state", {
            "window_id": self.window_id,
        }))
        self.assertTrue(after["success"], after)
        delta_x = after["data"]["left"] - before["data"]["left"]
        delta_y = after["data"]["top"] - before["data"]["top"]
        self.assertGreater(
            abs(delta_x), 20,
            f"window did not move horizontally: {before['data']} -> {after['data']}",
        )
        self.assertGreater(
            abs(delta_y), 20,
            f"window did not move vertically: {before['data']} -> {after['data']}",
        )

    async def test_type_random_alphanumeric_and_verify(self):
        editor = await self._editor_element()
        self.assertIsNotNone(editor)
        token = "Winui" + _random_text(12)

        typed = structured(await self.session.call_tool("type_text", {
            "window_id": self.window_id,
            "element_id": editor["element_id"],
            "text": token,
        }))
        self.assertTrue(typed["success"], typed)
        self.assertIn(token, await self._get_value(editor["element_id"]))

    async def test_keyboard_select_all_copy_paste(self):
        editor = await self._editor_element()
        self.assertIsNotNone(editor)
        token = "CopyPaste" + _random_text(8)

        await self.session.call_tool("type_text", {
            "window_id": self.window_id,
            "element_id": editor["element_id"],
            "text": token,
        })
        await self.session.call_tool("send_hotkey", {
            "window_id": self.window_id, "keys": "Ctrl+a",
        })
        await self.session.call_tool("send_hotkey", {
            "window_id": self.window_id, "keys": "Ctrl+c",
        })
        await self.session.call_tool("send_hotkey", {
            "window_id": self.window_id, "keys": "Ctrl+End",
        })
        await self.session.call_tool("send_hotkey", {
            "window_id": self.window_id, "keys": "Ctrl+v",
        })

        value = await self._get_value(editor["element_id"])
        self.assertEqual(value.count(token), 2, value[-200:])

    async def test_right_click_copy_paste(self):
        editor = await self._editor_element()
        self.assertIsNotNone(editor)
        token = "RightClick" + _random_text(8)

        await self.session.call_tool("type_text", {
            "window_id": self.window_id,
            "element_id": editor["element_id"],
            "text": token,
        })
        await self.session.call_tool("send_hotkey", {
            "window_id": self.window_id, "keys": "Ctrl+a",
        })
        await asyncio.sleep(0.3)

        right = structured(await self.session.call_tool("right_click", {
            "window_id": self.window_id,
            "element_id": editor["element_id"],
        }))
        self.assertTrue(right["success"], right)
        await asyncio.sleep(0.6)

        elements = await self._snapshot_elements(interactive_only=True)
        copy_item = next(
            (item for item in elements
             if item.get("name") in {"复制", "Copy"}
             and item.get("control_type") in {"ButtonControl", "MenuItemControl"}),
            None,
        )
        if copy_item is None:
            await self.session.call_tool("send_key", {
                "window_id": self.window_id, "key": "{Escape}",
            })
            self.skipTest("context menu copy item was not found")

        clicked = structured(await self.session.call_tool("click", {
            "window_id": self.window_id,
            "element_id": copy_item["element_id"],
        }))
        self.assertTrue(clicked["success"], clicked)

        refreshed = await self._editor_element()
        self.assertIsNotNone(refreshed)
        await self.session.call_tool("click", {
            "window_id": self.window_id,
            "element_id": refreshed["element_id"],
        })
        await self.session.call_tool("send_hotkey", {
            "window_id": self.window_id, "keys": "Ctrl+End",
        })
        await self.session.call_tool("send_hotkey", {
            "window_id": self.window_id, "keys": "Ctrl+v",
        })
        value = await self._get_value(refreshed["element_id"])
        self.assertEqual(value.count(token), 2, value[-200:])

    async def test_top_menu_click_and_escape(self):
        clicked = structured(await self.session.call_tool("click", {
            "window_id": self.window_id, "name": "文件", "partial": False,
        }))
        self.assertTrue(clicked["success"], clicked)
        await asyncio.sleep(0.5)

        elements = await self._snapshot_elements(interactive_only=True)
        expected = {"新建标签页", "打开", "保存", "退出",
                    "New tab", "Open", "Save", "Exit"}
        menu_items = [
            item for item in elements
            if item.get("control_type") == "MenuItemControl"
            and item.get("name") in expected
        ]
        self.assertTrue(menu_items, "top menu did not open")

        escaped = structured(await self.session.call_tool("send_key", {
            "window_id": self.window_id, "key": "{Escape}",
        }))
        self.assertTrue(escaped["success"], escaped)

    async def test_scrollbar_drag_when_present(self):
        editor = await self._editor_element()
        self.assertIsNotNone(editor)

        long_text = "\n".join(
            f"winui scroll probe line {index:03d}" for index in range(1, 121)
        )
        await self.session.call_tool("set_value", {
            "window_id": self.window_id,
            "element_id": editor["element_id"],
            "value": long_text,
        })
        await asyncio.sleep(0.5)
        value = await self._get_value(editor["element_id"])
        if "line 120" not in value:
            self.skipTest("long text was not applied, scrollbar not available")

        elements = await self._snapshot_elements(interactive_only=False)
        scrollbar = next(
            (item for item in elements
             if item.get("control_type") == "ScrollBarControl"
             and ("垂直" in str(item.get("name") or "")
                  or "Vertical" in str(item.get("name") or ""))),
            None,
        )
        if scrollbar is None:
            self.skipTest("vertical scrollbar was not present")

        dragged = structured(await self.session.call_tool("drag_control", {
            "window_id": self.window_id,
            "element_id": scrollbar["element_id"],
            "delta_y": 80,
        }))
        self.assertTrue(dragged["success"], dragged)

    async def test_close_window(self):
        closed = await self._close_and_discard()
        self.assertTrue(closed, "window did not close cleanly")

        listed = structured(await self.session.call_tool("list_windows", {
            "visible_only": True, "include_hidden": False,
        }))
        self.assertTrue(listed["success"], listed)
        ids = {item["window_id"] for item in listed["data"]["windows"]}
        self.assertNotIn(self.window_id, ids, "closed window is still listed")


if __name__ == "__main__":
    unittest.main()
