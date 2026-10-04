import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

root = Path(__file__).resolve().parents[1]
versioning = load('release_versioning', root / 'scripts/versioning.py')
android = load('release_android', root / 'weizhuo/mobile/configure_android.py')

class ReleaseVersionTests(unittest.TestCase):
    def test_mobile_configuration_matches_canonical_version(self):
        path, expected = versioning.mobile_config(versioning.release_identity())
        self.assertEqual(path.read_text(), expected)

    def test_invalid_versions_cannot_reach_platform_packagers(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(versioning, 'ROOT', Path(directory)):
            for identity in ({'version':'v1.0.0','build':2}, {'version':'1.0.0','build':0}, {'version':'1.0.0','build':True}):
                (Path(directory) / 'version.json').write_text(json.dumps(identity))
                with self.assertRaises(ValueError):versioning.release_identity()

    def test_generated_android_version_updates_and_missing_fields_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'build.gradle'
            path.write_text('android {\n defaultConfig {\n versionCode 1\n versionName "0.0.1"\n }\n}\n')
            android.configure(path, {'version':'0.1.0','build':2})
            self.assertIn('versionCode 2', path.read_text())
            self.assertIn('versionName "0.1.0"', path.read_text())
            original = 'android {}'
            path.write_text(original)
            with self.assertRaises(RuntimeError):android.configure(path, {'version':'0.1.0','build':2})
            self.assertEqual(path.read_text(), original)

    def test_phone_and_emulator_architectures_remain_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'build.gradle'
            path.write_text('ndk {\n abiFilters "arm64-v8a", "x86_64"\n}\n')
            android.configure_arch(path)
            self.assertIn('abiFilters "arm64-v8a"',path.read_text())
            self.assertNotIn('x86_64',path.read_text())
            android.configure_arch(path,'x86_64')
            self.assertNotIn('arm64-v8a',path.read_text())
            with self.assertRaises(ValueError):android.configure_arch(path,'universal')

    def test_alpha_label_does_not_reset_install_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'build.gradle'
            path.write_text('versionCode 38\nversionName "0.1.0"\n')
            android.configure(path,{'version':'0.1.1','build':39,'prerelease':'a1'})
            self.assertIn('versionCode 39',path.read_text())
            self.assertIn('versionName "0.1.1.a1"',path.read_text())
