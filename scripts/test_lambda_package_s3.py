import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from lambda_package_s3 import (
    AwsCliError,
    PackageError,
    package_digest,
    package_key,
    publish_package,
    validate_head,
    verify_package,
)


BUCKET = "autoflow-tfstate-test-example"
OWNER = "123456789012"
REGION = "us-east-1"


class LambdaPackageS3Tests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.archive = Path(self.tempdir.name) / "lambda.zip"
        self.archive.write_bytes(b"immutable test package")
        self.digest_hex, self.digest_b64, self.size = package_digest(self.archive)
        self.key = package_key(self.digest_hex)
        self.head = {
            "ChecksumSHA256": self.digest_b64,
            "ContentLength": self.size,
            "VersionId": "s3-version-001",
        }

    def test_key_is_content_addressed_under_isolated_prefix(self):
        self.assertEqual(self.key, f"lambda-packages/sha256/{self.digest_hex}.zip")
        self.assertEqual(len(self.digest_b64), 44)

    def test_publish_uses_conditional_write_and_pins_version(self):
        aws = Mock(side_effect=[
            {"Status": "Enabled"},
            {"LocationConstraint": None},
            {"VersionId": "s3-version-001"},
            self.head,
        ])

        metadata = publish_package(self.archive, BUCKET, REGION, OWNER, aws)

        put_args = aws.call_args_list[2].args[0]
        self.assertIn("--if-none-match", put_args)
        self.assertEqual(put_args[put_args.index("--if-none-match") + 1], "*")
        self.assertEqual(metadata["key"], self.key)
        self.assertEqual(metadata["source_code_hash"], self.digest_b64)
        self.assertEqual(metadata["version_id"], "s3-version-001")
        self.assertIn("--version-id", aws.call_args_list[3].args[0])

    def test_publish_reuses_existing_matching_object_after_conditional_conflict(self):
        aws = Mock(side_effect=[
            {"Status": "Enabled"},
            {"LocationConstraint": "us-east-1"},
            AwsCliError("PreconditionFailed"),
            self.head,
            self.head,
        ])

        metadata = publish_package(self.archive, BUCKET, REGION, OWNER, aws)

        self.assertEqual(metadata["version_id"], "s3-version-001")
        self.assertEqual(aws.call_count, 5)

    def test_publish_rejects_bucket_without_versioning(self):
        aws = Mock(return_value={"Status": "Suspended"})
        with self.assertRaisesRegex(PackageError, "Versioning habilitado"):
            publish_package(self.archive, BUCKET, REGION, OWNER, aws)
        self.assertEqual(aws.call_count, 1)

    def test_verify_requires_exact_local_hash_size_and_s3_version(self):
        metadata = {
            "bucket": BUCKET,
            "key": self.key,
            "sha256_hex": self.digest_hex,
            "source_code_hash": self.digest_b64,
            "version_id": "s3-version-001",
            "size": self.size,
            "region": REGION,
        }
        aws = Mock(side_effect=[
            {"Status": "Enabled"},
            {"LocationConstraint": None},
            self.head,
        ])

        verified = verify_package(
            self.archive, self.write_metadata(metadata), BUCKET, REGION, OWNER, aws
        )

        self.assertEqual(verified, metadata)
        self.assertEqual(aws.call_args_list[2].args[0][-2:], ["--version-id", "s3-version-001"])

    def test_verify_fails_on_modified_zip_or_s3_checksum(self):
        metadata = {
            "bucket": BUCKET,
            "key": self.key,
            "sha256_hex": self.digest_hex,
            "source_code_hash": self.digest_b64,
            "version_id": "s3-version-001",
            "size": self.size,
            "region": REGION,
        }
        metadata_path = self.write_metadata(metadata)
        self.archive.write_bytes(b"changed package")
        with self.assertRaisesRegex(PackageError, "Metadados não correspondem"):
            verify_package(self.archive, metadata_path, BUCKET, REGION, OWNER, Mock())

        with self.assertRaisesRegex(PackageError, "checksum SHA-256"):
            validate_head({**self.head, "ChecksumSHA256": base64.b64encode(hashlib.sha256(b"wrong").digest()).decode()}, self.digest_b64, self.size, "s3-version-001")

    def write_metadata(self, metadata):
        path = Path(self.tempdir.name) / "package.json"
        path.write_text(json.dumps(metadata), encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
