# Testing and Reload Workflow

The project uses standard MCP stdio transports and fresh server processes. Each
integration test starts a new process, so code changes are reloaded exactly as a
real MCP client would reload the server.

## Test layers

| Layer | Purpose | Command |
|---|---|---|
| Unit | Schemas, refs, snapshots, catalog, actions, errors | `uv run --extra dev python -m pytest tests -q` |
| MCP protocol | Real stdio client, discovery, structured output, Notepad | `WINUI_RUN_INTEGRATION=1 uv run --extra dev python -m pytest tests/integration/test_mcp_stdio.py -q` |
| Existing-app smoke | Read-only snapshots of open common apps | `WINUI_RUN_APP_SMOKE=1 uv run --extra dev python -m pytest tests/integration/test_common_app_smoke.py -q` |
| Launch matrix | Launch, bind, snapshot, and safely clean up common apps | `WINUI_RUN_APP_LAUNCH=1 uv run --extra dev python -m pytest tests/integration/test_app_launch_matrix.py -q` |
| App interaction | Notepad drag/type/copy/paste/menu/scroll/close plus random Calculator arithmetic | `WINUI_RUN_APP_INTERACTION=1 uv run --extra dev python -m pytest tests/integration/test_app_interactions.py tests/integration/test_calculator_interaction.py -q` |

For local development on Windows, a Conda environment named `winui_mcp_server`
is supported without repackaging the project:

```powershell
conda run -n winui_mcp_server python -m pytest tests -q
```

Published users continue to use `uv`, the installation method documented in the
README.

## Environment gates

Live tests are skipped by default because they control real desktop applications.

- `WINUI_RUN_INTEGRATION=1`: enable MCP stdio integration tests.
- `WINUI_RUN_APP_SMOKE=1`: enable read-only common-app inspection.
- `WINUI_SMOKE_APPS=settings,explorer,vscode,edge`: select smoke-test apps.
- `WINUI_RUN_APP_LAUNCH=1`: enable the launch matrix.
- `WINUI_RUN_APP_INTERACTION=1`: enable live Notepad and Calculator interaction tests.
- `WINUI_LAUNCH_APPS=notepad,calculator,paint,...`: select launch-matrix apps.

The launch matrix closes a window only when it was opened by the test or carries
the test's unique temporary fixture name. It does not terminate user processes.

## Live matrix coverage

The default launch matrix covers:

- Notepad
- Calculator
- Paint
- Windows Settings
- File Explorer
- Visual Studio Code
- Microsoft Edge
- Google Chrome

Each successful case verifies application launch, deterministic window binding,
a bounded snapshot, and that any test-owned window disappears after close.
VSCode, Edge, and Chrome use isolated profiles/new windows so cleanup cannot
close an existing user window. The Calculator interaction test performs random
continuous add/subtract/multiply/divide operations, presses equals, verifies the
displayed result, and then verifies the test-owned Calculator window disappears.

## Release checks

```powershell
uv lock
uv run --extra dev ruff check winui_mcp tests
uv run --extra dev python -m pytest tests -q
uv build
```

Before publishing, verify that the wheel contains the bundled OCR model files and
that no test-generated paths, logs, or local configuration files are tracked.
