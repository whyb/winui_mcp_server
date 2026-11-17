"""Portable catalog and launcher support for common Windows applications.

The catalog contains product identifiers and discovery strategies only. It never
stores installation directories. Executables are resolved from PATH and the
Windows App Paths registry; protocol-based applications use registered URIs.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import winreg
from dataclasses import dataclass


class AppCatalogError(RuntimeError):
    """Base error for application catalog and launch failures."""


class AppNotFoundError(AppCatalogError):
    """Raised when an application cannot be resolved on the current machine."""


class UnsupportedPlatformError(AppCatalogError):
    """Raised when Windows application discovery is used on another platform."""


@dataclass(frozen=True)
class AppProfile:
    """Agent-facing metadata for a commonly automated Windows application."""

    id: str
    name: str
    category: str
    aliases: tuple[str, ...]
    process_names: tuple[str, ...]
    launch_targets: tuple[str, ...]
    description: str
    workflow: tuple[str, ...]
    tips: tuple[str, ...]
    singleton: bool = True

    def matches(self, value: str | None) -> bool:
        """Return whether an alias, process name, or product id matches."""
        if not value:
            return False
        needle = value.casefold().strip()
        candidates = (self.id, self.name, *self.aliases, *self.process_names)
        return any(needle == candidate.casefold() for candidate in candidates)

    def as_dict(self) -> dict:
        """Return stable, path-free profile metadata for MCP clients."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "aliases": list(self.aliases),
            "process_names": list(self.process_names),
            "description": self.description,
            "workflow": list(self.workflow),
            "tips": list(self.tips),
            "singleton": self.singleton,
        }


@dataclass(frozen=True)
class LaunchPlan:
    """Resolved launch command. The target is internal and not exposed to MCP."""

    app: AppProfile
    target: str
    kind: str
    source: str


_APP_PROFILES = (
    AppProfile(
        id="notepad",
        name="Notepad",
        category="built-in",
        aliases=("notepad", "记事本"),
        process_names=("notepad.exe",),
        launch_targets=("notepad.exe",),
        description="Edit plain-text files and scratch notes through a simple UIA tree.",
        workflow=("launch_app(notepad)", "snapshot", "click or type_text", "snapshot to verify"),
        tips=(
            "Use element_id from the latest snapshot instead of the document title.",
            "Read the editor through get_value when ValuePattern is available.",
            "Save with Ctrl+S and wait for a dialog or title change.",
        ),
    ),
    AppProfile(
        id="calculator",
        name="Calculator",
        category="built-in",
        aliases=("calculator", "calc", "计算器"),
        process_names=("calculatorapp.exe", "calculator.exe", "applicationframehost.exe"),
        launch_targets=("calc.exe",),
        description="Use calculator buttons and the display through UIA.",
        workflow=("launch_app(calculator)", "snapshot", "click element_id values", "get_text for the result"),
        tips=(
            "Prefer button AutomationIds and exact names.",
            "The top-level window may be hosted by ApplicationFrameHost.",
            "Re-snapshot after switching calculator modes.",
        ),
    ),
    AppProfile(
        id="paint",
        name="Paint",
        category="built-in",
        aliases=("paint", "mspaint", "画图"),
        process_names=("mspaint.exe", "paintapp.exe", "applicationframehost.exe"),
        launch_targets=("ms-paint:", "mspaint.exe"),
        description="Automate Paint tools, colors, canvas, save, and export dialogs.",
        workflow=("launch_app(paint)", "snapshot", "select a tool", "perform canvas or menu actions"),
        tips=(
            "Canvas coordinates are acceptable only after UIA discovery is insufficient.",
            "Use Ctrl+Shift+S for Save As and Ctrl+S for Save.",
            "Confirm destructive operations such as clearing the canvas.",
        ),
    ),
    AppProfile(
        id="settings",
        name="Windows Settings",
        category="system",
        aliases=("settings", "windows settings", "设置"),
        process_names=("systemsettings.exe", "applicationframehost.exe"),
        launch_targets=("ms-settings:",),
        description="Navigate Windows Settings pages and toggle system options.",
        workflow=("launch_app(settings, arguments=display)", "snapshot", "search or click", "snapshot to verify"),
        tips=(
            "Use a deep link such as display, bluetooth, wifi, or appsfeatures when possible.",
            "Settings is a UWP app and may be hosted by ApplicationFrameHost.",
            "Do not change security, privacy, or network settings without explicit intent.",
        ),
    ),
    AppProfile(
        id="explorer",
        name="File Explorer",
        category="built-in",
        aliases=("explorer", "file explorer", "files", "文件资源管理器"),
        process_names=("explorer.exe",),
        launch_targets=("explorer.exe",),
        description="Navigate folders, select files, and open shell dialogs.",
        workflow=("launch_app(explorer, arguments=path)", "snapshot", "click a file", "double_click to open"),
        tips=(
            "Pass a folder or file path as arguments to open a deterministic location.",
            "Use Ctrl+L to focus the address bar, then type a path.",
            "Avoid deleting or moving items unless the user explicitly requested it.",
        ),
    ),
    AppProfile(
        id="vscode",
        name="Visual Studio Code",
        category="developer",
        aliases=("vscode", "vs code", "code"),
        process_names=("code.exe",),
        launch_targets=("Code.exe", "code.cmd", "vscode://"),
        description="Automate editor commands, panels, settings, and extension dialogs.",
        workflow=("launch_app(vscode, arguments=path)", "snapshot", "use command palette or element_id", "verify"),
        tips=(
            "The command palette (Ctrl+Shift+P) is often more stable than deep menu navigation.",
            "Use exact command names and wait for the command palette to settle.",
            "Avoid overwriting files without capturing their previous content.",
        ),
    ),
    AppProfile(
        id="edge",
        name="Microsoft Edge",
        category="browser",
        aliases=("edge", "microsoft edge"),
        process_names=("msedge.exe",),
        launch_targets=("msedge.exe", "microsoft-edge:"),
        description="Automate browser chrome and web content exposed through Chromium accessibility.",
        workflow=("launch_app(edge, arguments=url)", "show window", "snapshot with query", "act and verify"),
        tips=(
            "Launch with a URL argument to target a deterministic page.",
            "Chromium web content can have a very large tree; use snapshot query and interactive_only.",
            "Keyboard shortcuts are often more reliable than browser menu traversal.",
        ),
    ),
    AppProfile(
        id="chrome",
        name="Google Chrome",
        category="browser",
        aliases=("chrome", "google chrome"),
        process_names=("chrome.exe",),
        launch_targets=("chrome.exe", "chrome:"),
        description="Automate Chrome browser chrome and web content through Chromium accessibility.",
        workflow=("launch_app(chrome, arguments=url)", "show window", "snapshot with query", "act and verify"),
        tips=(
            "Launch with a URL argument to target a deterministic page.",
            "Use Ctrl+L for the address bar.",
            "Use interactive snapshots and queries for large pages.",
        ),
    ),
    AppProfile(
        id="media-player",
        name="Windows Media Player",
        category="media",
        aliases=("media player", "windows media player", "媒体播放器", "wmplayer"),
        process_names=(
            "microsoft.media.player.exe",
            "mediaplayer.exe",
            "wmplayer.exe",
            "applicationframehost.exe",
        ),
        launch_targets=("microsoft.media.player:", "wmplayer.exe"),
        description="Open and control media playback through UIA or media key shortcuts.",
        workflow=("launch_app(media-player, arguments=file)", "snapshot", "click transport controls", "verify state"),
        tips=(
            "Pass a media file path as arguments when possible.",
            "Media control keys can supplement UIA transport controls.",
            "Confirm playback state instead of assuming a click succeeded.",
        ),
    ),
)

APP_PROFILES = {profile.id: profile for profile in _APP_PROFILES}
_ALIAS_INDEX = {}
for _profile in _APP_PROFILES:
    for _alias in (_profile.id, _profile.name, *_profile.aliases, *_profile.process_names):
        _ALIAS_INDEX[_alias.casefold()] = _profile


def _ensure_windows() -> None:
    if os.name != "nt":
        raise UnsupportedPlatformError("Windows application discovery requires Windows")


def _registry_app_path(exe_name: str) -> str | None:
    """Resolve an executable from the per-user and machine App Paths keys."""
    _ensure_windows()
    subkey = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}"
    views = (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in views:
            try:
                with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | view) as key:
                    value, _ = winreg.QueryValueEx(key, "")
                    expanded = os.path.expandvars(str(value).strip().strip('"'))
                    if expanded and os.path.isfile(expanded):
                        return expanded
            except OSError:
                continue
    return None


def resolve_executable(value: str) -> str | None:
    """Resolve an executable name without storing a machine-specific path."""
    _ensure_windows()
    expanded = os.path.expandvars(os.path.expanduser(value.strip().strip('"')))
    if os.path.isfile(expanded):
        return os.path.abspath(expanded)
    found = shutil.which(expanded)
    if found:
        return os.path.abspath(found)
    if not expanded.lower().endswith(".exe"):
        found = shutil.which(expanded + ".exe")
        if found:
            return os.path.abspath(found)
    basename = os.path.basename(expanded)
    if basename and basename.lower().endswith(".exe"):
        return _registry_app_path(basename)
    return None


def get_profile(app: str) -> AppProfile:
    """Return a common application profile by id, alias, or process name."""
    profile = _ALIAS_INDEX.get((app or "").casefold().strip())
    if profile is None:
        raise AppNotFoundError(
            f"Unknown application profile {app!r}. Call list_apps to see supported app ids."
        )
    return profile


_GENERIC_UWP_HOSTS = {"applicationframehost.exe"}


def match_profile(
    window_title: str | None = None,
    process_name: str | None = None,
) -> AppProfile | None:
    """Best-effort profile match for a live window.

    ApplicationFrameHost hosts several UWP apps, so its process name cannot identify
    Calculator, Settings, or Paint. For that generic host, the window title decides
    the profile instead of whichever application happens to appear first.
    """
    proc = os.path.basename(process_name).casefold() if process_name else ""
    if proc and proc not in _GENERIC_UWP_HOSTS:
        for profile in _APP_PROFILES:
            if proc in profile.process_names:
                return profile
    if window_title:
        title = window_title.casefold()
        for profile in _APP_PROFILES:
            terms = (profile.name, *profile.aliases)
            if any(term.casefold() in title for term in terms):
                return profile
    return None


def list_app_profiles() -> list[dict]:
    """Return all profiles with path-free installation metadata."""
    result = []
    for profile in _APP_PROFILES:
        try:
            plan = resolve_launch_plan(profile.id)
            available = True
            source = plan.source
        except AppCatalogError:
            available = False
            source = None
        data = profile.as_dict()
        data.update({"available": available, "resolution_source": source})
        result.append(data)
    return result


def resolve_launch_plan(app: str) -> LaunchPlan:
    """Resolve a catalog entry to an executable or registered URI plan."""
    profile = get_profile(app)
    for candidate in profile.launch_targets:
        if ":" in candidate and not candidate.lower().endswith(".exe"):
            return LaunchPlan(profile, candidate, "uri", "protocol")
        executable = resolve_executable(candidate)
        if executable:
            return LaunchPlan(profile, executable, "executable", "path_or_app_paths")
    raise AppNotFoundError(
        f"{profile.name} is not installed or cannot be discovered. "
        f"Expected one of: {', '.join(profile.launch_targets)}. "
        "Install the application or add its executable to PATH."
    )


def launch_application(
    app: str,
    arguments: str | list[str] | tuple[str, ...] | None = None,
) -> LaunchPlan:
    """Launch a catalog application and return its path-free resolution plan.

    arguments may be one string for document/URL/deep-link launches or a list of
    command-line arguments when an app needs flags such as --new-window or
    --user-data-dir. Lists are passed without a shell.
    """
    _ensure_windows()
    plan = resolve_launch_plan(app)
    if isinstance(arguments, str) or arguments is None:
        argument_list = [arguments] if arguments else []
    else:
        argument_list = [str(item) for item in arguments if str(item)]
    if plan.kind == "uri":
        target = plan.target
        if argument_list:
            target = target.rstrip("/") + argument_list[0]
        os.startfile(target)  # type: ignore[attr-defined]
        return plan
    command = [plan.target, *argument_list]
    subprocess.Popen(command, close_fds=True)
    return plan
