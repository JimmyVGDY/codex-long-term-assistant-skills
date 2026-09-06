"""中文：隔离历史 schema 的服务单元测试；生产健康门禁由 V7.5 集成测试验证。

English: Isolate historical-schema service unit tests; V7.5 integration tests exercise the production health gate.
"""
from unittest.mock import patch


def legacy_service(service_type):
    class HistoricalSchemaService(service_type):
        def run(self, *args, **kwargs):
            def historical_health(project_dir, project_id, policy, *, explicit_sources=None, observed_at=None):
                return {"analysis_allowed": True, "status": "LEGACY_TEST_FIXTURE"}, self.observe(
                    explicit_sources=explicit_sources, observed_at=observed_at)
            with patch(service_type.__module__ + ".inspect_health", side_effect=historical_health):
                return super().run(*args, **kwargs)
    return HistoricalSchemaService
