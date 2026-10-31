import tempfile
import unittest
import zipfile
from pathlib import Path

from create_lambda_zip import create_zip


class CreateLambdaZipTests(unittest.TestCase):
    def test_zip_is_deterministic_and_omits_python_bytecode_caches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "build"
            (source / "package" / "__pycache__").mkdir(parents=True)
            (source / "package" / "module.py").write_text("value = 1\n", encoding="utf-8")
            (source / "package" / "__pycache__" / "module.cpython-312.pyc").write_bytes(b"bytecode")
            (source / "package" / "module.pyc").write_bytes(b"bytecode")
            first = root / "first.zip"
            second = root / "second.zip"

            create_zip(source, first)
            create_zip(source, second)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), ["package/module.py"])


if __name__ == "__main__":
    unittest.main()
