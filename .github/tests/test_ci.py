"""Regression checks for production CI selection."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('ci', Path(__file__).parents[1] / 'scripts/ci.py')
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class RoutingTests(unittest.TestCase):
    def test_unknown_runs_everything(self):
        for path in ['tools/new.py', 'new/code.rs', 'new config.toml', 'doc/render_demo.py', '工具/file;echo.sh']:
            self.assertTrue(all(ci.select([path])[0].values()), path)

    def test_docs(self):
        self.assertFalse(any(ci.select(['README.md', 'doc/assets/cat.gif', 'LICENSE'])[0].values()))

    def test_shared_manifest(self):
        result, _ = ci.select(['fonts/pet-cats/animations.tsv'])
        for group in ['rust', 'tmux', 'fonts']:
            self.assertTrue(result[group])

    def test_powershell(self):
        result, _ = ci.select(['fonts/new.ps1'])
        self.assertTrue(result['powershell'])
        self.assertFalse(result['fonts'])

    def test_rename_union(self):
        result, _ = ci.select(['src/deleted.rs', 'doc/moved.md'])
        self.assertTrue(result['rust'])

    def test_bad_input(self):
        for value in [None, {}, [1]]:
            with self.assertRaises(ValueError):
                ci.select(value)


class DiscoveryTests(unittest.TestCase):
    def test_repository_wide_discovery(self):
        import os
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as root:
            previous = os.getcwd()
            try:
                os.chdir(root)
                for name, content in [('doc/new script.sh', '#!/bin/sh\n'), ('tools/no-extension', '#!/usr/bin/env python3\n'), ('fonts/vendor/skip.py', ''), ('new/工具.py', '')]:
                    path = Path(name)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content)
                names = b'doc/new script.sh\0tools/no-extension\0fonts/vendor/skip.py\0new/\xe5\xb7\xa5\xe5\x85\xb7.py\0deleted.py\0'
                with patch.object(ci.subprocess, 'check_output', return_value=names):
                    self.assertEqual(ci.inventory('shell'), ['doc/new script.sh'])
                    self.assertEqual(ci.inventory('python'), ['new/工具.py', 'tools/no-extension'])
            finally:
                os.chdir(previous)
