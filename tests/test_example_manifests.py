import tomllib
import unittest
from pathlib import Path


class ExampleManifestTests(unittest.TestCase):
    def test_plugin_echo_manifest_is_api_v1_and_declares_capability(self) -> None:
        manifest = self._load("examples/plugin-echo/plugin.toml")
        self.assertEqual(str(manifest["api_version"]).split(".")[0], "1")
        self.assertEqual(manifest["capabilities"], ["example.echo"])

    def test_noop_domain_manifest_is_api_v1(self) -> None:
        manifest = self._load("examples/domain-noop/domain.toml")
        self.assertEqual(str(manifest["api_version"]).split(".")[0], "1")
        self.assertEqual(manifest["id"], "example.noop")

    def _load(self, path: str) -> dict[str, object]:
        with Path(path).open("rb") as stream:
            value = tomllib.load(stream)
        self.assertIsInstance(value, dict)
        return value
