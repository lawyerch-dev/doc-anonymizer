"""旧版二进制 Office 抽取: 先转成 .docx/.xlsx, 再委托现代抽取器。

回写是重开 `doc.source_path`, 所以只要把 source_path 指向转换后的现代文件, 原格式分支
零改动。临时目录由本抽取器在失败时自清, 成功时交给 `process_file` 收尾(它还要重开文件)。
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from docanon_contract import ExtractedDoc, Extractor

from .. import convert


class LegacyOfficeExtractor(Extractor):
    name = "legacy_office"
    extensions = convert.LEGACY_EXTENSIONS

    def ready(self) -> str | None:
        return convert.unavailable_reason()

    def extract(self, path: Path) -> ExtractedDoc:
        from .table import TableExtractor
        from .text_file import DocxExtractor

        workdir = Path(tempfile.mkdtemp(prefix="docanon-convert-"))
        try:
            modern, out_ext = convert.to_modern(path, workdir)
            doc = (DocxExtractor() if out_ext == ".docx" else TableExtractor()).extract(modern)
        except BaseException:
            shutil.rmtree(workdir, ignore_errors=True)
            raise
        doc.meta["converted_from"] = path.suffix.lower()
        doc.meta["out_ext"] = out_ext
        # 回写还要重开 modern, 所以临时目录留到 process_file 收尾再删
        doc.meta["_convert_workdir"] = str(workdir)
        return doc
