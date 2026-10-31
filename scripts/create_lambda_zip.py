#!/usr/bin/env python3
"""Cria um ZIP Lambda estável entre builds com os mesmos arquivos de entrada."""

import pathlib
import stat
import sys
import zipfile


def create_zip(source_dir: pathlib.Path, output_file: pathlib.Path) -> None:
    source_dir = source_dir.resolve()
    output_file = output_file.resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(
        output_file,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for file_path in sorted(source_dir.rglob("*"), key=lambda path: path.as_posix()):
            if not file_path.is_file() or "__pycache__" in file_path.parts or file_path.suffix == ".pyc":
                continue

            archive_path = file_path.relative_to(source_dir).as_posix()
            entry = zipfile.ZipInfo(archive_path, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            entry.flag_bits = 0
            archive.writestr(entry, file_path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: create_lambda_zip.py <diretório-origem> <arquivo-zip>")
    create_zip(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
