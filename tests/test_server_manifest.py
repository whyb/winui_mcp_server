import json
import unittest
from importlib.metadata import version
from pathlib import Path


class ServerManifestTests(unittest.TestCase):
    def test_registry_manifest_matches_package_version(self):
        manifest = json.loads(Path("server.json").read_text(encoding="utf-8"))
        package_version = version("winui-mcp-server")
        self.assertEqual(manifest["version"], package_version)
        self.assertEqual(
            manifest["packages"][0]["version"],
            package_version,
        )
        self.assertEqual(manifest["packages"][0]["transport"]["type"], "stdio")
        self.assertEqual(manifest["packages"][0]["runtimeHint"], "uvx")


if __name__ == "__main__":
    unittest.main()
