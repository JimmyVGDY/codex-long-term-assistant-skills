"""中文：内部构建与安装工具的兼容导入，仅使用一份运行时实现。

English: Compatibility import for internal build/install tools; one runtime implementation.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from cp_runtime.payload_integrity import (  # noqa: E402,F401
    MANIFEST_NAME, PAYLOAD_ROOTS, SCHEMA_VERSION, PayloadIntegrityError,
    _canonical, _io_path, _is_link, _sha256, _validate_relative,
    build_manifest, iter_payload_files, load_manifest, main, verify_payload, write_manifest,
)

if __name__ == "__main__":
    main()
