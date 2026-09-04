"""中文：TaskOutcomeEvent V3 公共导入面。

English: Public import surface for TaskOutcomeEvent V3.

中文：实现暂留在 ``event_v2``，确保旧导入指向 V3 写入器，同时保持 V2 记录只读。
English: The implementation remains in ``event_v2`` so legacy imports resolve to the V3
writer while V2 records remain readable. New active code should import here.
"""

from .event_v2 import *  # noqa: F401,F403
