"""Live Calculator interaction test with random continuous arithmetic."""
import asyncio
import os
import random
import re
import unittest
from decimal import Decimal

from tests.integration.mcp_harness import FreshMcpSession, structured


OPERATOR_BUTTONS = {
    "+": "plusButton",
    "-": "minusButton",
    "*": "multiplyButton",
    "/": "divideButton",
}


def _apply_operation(current: int, operator: str, operand: int) -> int:
    if operator == "+":
        return current + operand
    if operator == "-":
        return current - operand
    if operator == "*":
        return current * operand
    if operator == "/":
        return current // operand
    raise ValueError(operator)


def _build_random_calculation(rng: random.Random) -> tuple[int, list[tuple[str, int]], int]:
    """Build four random operations while keeping division integral."""
    operators = list(OPERATOR_BUTTONS)
    rng.shuffle(operators)
    current = rng.randint(2, 9)
    initial = current
    steps = []
    for operator in operators:
        if operator == "/":
            divisors = [value for value in range(2, 10) if current % value == 0]
            operand = rng.choice(divisors) if divisors else 1
        elif operator == "*":
            operand = rng.randint(2, 9)
        else:
            operand = rng.randint(1, 9)
        current = _apply_operation(current, operator, operand)
        steps.append((operator, operand))
    return initial, steps, current


@unittest.skipUnless(
    os.name == "nt" and os.environ.get("WINUI_RUN_APP_INTERACTION") == "1",
    "Set WINUI_RUN_APP_INTERACTION=1 to run live Calculator interaction tests.",
)
class CalculatorInteractionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._session_context = FreshMcpSession()
        self.session = await self._session_context.__aenter__()
        launched = structured(await self.session.call_tool("launch_app", {
            "app": "calculator",
            "timeout": 20,
        }))
        self.assertTrue(launched["success"], launched)
        self.window = launched["data"]["window"]
        self.window_id = self.window["window_id"]
        self.owned = bool(launched["data"].get("new_window"))

    async def asyncTearDown(self):
        try:
            await self._close_if_owned()
        except Exception:
            pass
        await self._session_context.__aexit__(None, None, None)

    async def _snapshot(self, interactive_only: bool = False):
        result = structured(await self.session.call_tool("snapshot", {
            "window_id": self.window_id,
            "depth": 20,
            "max_nodes": 1200,
            "interactive_only": interactive_only,
        }))
        self.assertTrue(result["success"], result)
        return result["data"]["elements"]

    async def _click_element(self, element_id: str):
        result = structured(await self.session.call_tool("click", {
            "window_id": self.window_id,
            "element_id": element_id,
        }))
        self.assertTrue(result["success"], result)
        await asyncio.sleep(0.12)

    async def _close_if_owned(self) -> bool:
        if not self.owned:
            return False
        closed = structured(await self.session.call_tool("window_action", {
            "window_id": self.window_id,
            "action": "close",
        }))
        self.assertTrue(closed["success"], closed)
        self.assertTrue(closed.get("verified"), closed)
        for _ in range(20):
            listed = structured(await self.session.call_tool("list_windows", {
                "visible_only": True,
                "include_hidden": False,
            }))
            self.assertTrue(listed["success"], listed)
            if not any(
                item.get("window_id") == self.window_id
                for item in listed["data"]["windows"]
            ):
                self.owned = False
                return True
            await asyncio.sleep(0.2)
        self.fail(f"Calculator window {self.window_id} is still listed after close: {closed}")

    async def test_random_continuous_arithmetic_and_close(self):
        rng = random.Random()
        initial, steps, expected = _build_random_calculation(rng)
        elements = await self._snapshot(interactive_only=False)
        by_auto_id = {
            str(item.get("auto_id") or ""): item
            for item in elements
        }
        required = {
            "clearButton", "equalButton", "CalculatorResults",
            *(OPERATOR_BUTTONS.values()),
            *(f"num{digit}Button" for digit in range(10)),
        }
        missing = sorted(required - set(by_auto_id))
        self.assertFalse(missing, f"Calculator controls missing: {missing}")

        await self._click_element(by_auto_id["clearButton"]["element_id"])
        for digit in str(initial):
            await self._click_element(by_auto_id[f"num{digit}Button"]["element_id"])
        for operator, operand in steps:
            await self._click_element(by_auto_id[OPERATOR_BUTTONS[operator]]["element_id"])
            for digit in str(operand):
                await self._click_element(by_auto_id[f"num{digit}Button"]["element_id"])
        await self._click_element(by_auto_id["equalButton"]["element_id"])
        await asyncio.sleep(0.5)

        refreshed = await self._snapshot(interactive_only=False)
        result_control = next(
            item for item in refreshed if item.get("auto_id") == "CalculatorResults"
        )
        read = structured(await self.session.call_tool("get_value", {
            "window_id": self.window_id,
            "element_id": result_control["element_id"],
        }))
        self.assertTrue(read["success"], read)
        display = str(read["data"].get("value") or "")
        match = re.search(r"[-+]?\d[\d,.]*", display)
        self.assertIsNotNone(match, f"Could not parse Calculator result: {display!r}")
        actual = Decimal(match.group(0).replace(",", ""))
        self.assertEqual(
            actual,
            Decimal(expected),
            f"Calculator expression {initial} {steps} produced {display!r}, "
            f"expected {expected}",
        )
        self.assertTrue(await self._close_if_owned(), "test did not own Calculator window")


if __name__ == "__main__":
    unittest.main()
