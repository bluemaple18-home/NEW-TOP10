"""只供 TOP10 guard 本次 child：固定標準庫暫存根，不安裝至共用 Python。"""

import os
import tempfile

_root = os.environ.get("TOP10_EXTERNAL_CACHE_ROOT")
if _root:
    _tmp = os.path.join(_root, "tmp")
    if not os.path.isabs(_root) or os.environ.get("TMPDIR") != _tmp:
        # Python 會吞掉一般 sitecustomize 例外；契約錯誤須在任何 workload 前退出。
        os._exit(78)
    # 指定字串後，tempfile 不再搜尋 /tmp、HOME 或 cwd；缺碟時直接拋 OSError。
    tempfile.tempdir = _tmp
