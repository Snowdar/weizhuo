"""A newer native shell must not silently ship stale web or rule code."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('runtime_check',Path(__file__).parent/'mobile/runtime_check.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class MobileResourceTests(unittest.TestCase):
    def test_existing_bundle_rejected_after_source_or_version_change(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);source=base/'app';runtime=base/'runtime'
            (source/'static').mkdir(parents=True)
            (source/'static/app.js').write_text('new editor')
            (source/'server.py').write_text('server')
            (base/'version.json').write_text(json.dumps({'version':'0.1.0','build':21}))
            shutil.copytree(source,runtime)
            (runtime/'resources').mkdir()
            shutil.copy2(base/'version.json',runtime/'resources/build-info.json')
            module.assert_runtime_current(runtime,source)
            (runtime/'static/app.js').write_text('old editor')
            with self.assertRaisesRegex(RuntimeError,'static/app.js'):module.assert_runtime_current(runtime,source)
            shutil.copy2(source/'static/app.js',runtime/'static/app.js')
            (base/'version.json').write_text(json.dumps({'version':'0.1.0','build':22}))
            with self.assertRaisesRegex(RuntimeError,'build-info.json'):module.assert_runtime_current(runtime,source)
