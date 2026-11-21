import unittest
from unittest.mock import patch

from ops import lifecycle_controller as lc


class LifecycleControllerTests(unittest.TestCase):
    @patch.object(lc.time, "sleep")
    @patch.object(lc, "graphql")
    @patch.object(lc, "health", side_effect=[False, False, True])
    def test_morning_start_allows_serverless_cold_start_before_redeploy(self, health, graphql, sleep):
        lc.start_if_needed("https://dashboard.test", "railway", "project", "env", "service")
        graphql.assert_not_called()
        self.assertEqual(sleep.call_count, 2)

    @patch.object(lc, "graphql")
    @patch.object(lc, "request_json")
    def test_shutdown_defers_for_valid_sessions(self, request, graphql):
        request.return_value = {
            "active_sessions": 1,
            "active_authenticated_requests": 0,
            "protected_jobs": {"imports": 0, "scheduled_reports": 0},
        }
        lc.stop_if_safe("https://dashboard.test", "control", "railway", "project", "env", "service")
        graphql.assert_not_called()

    @patch.object(lc, "graphql")
    @patch.object(lc, "request_json")
    def test_shutdown_defers_for_protected_import(self, request, graphql):
        request.return_value = {
            "active_sessions": 0,
            "active_authenticated_requests": 0,
            "protected_jobs": {"imports": 1, "scheduled_reports": 0},
        }
        lc.stop_if_safe("https://dashboard.test", "control", "railway", "project", "env", "service")
        graphql.assert_not_called()

    @patch.object(lc, "graphql")
    @patch.object(lc, "request_json")
    def test_shutdown_fails_safe_when_state_endpoint_is_unavailable(self, request, graphql):
        request.side_effect = OSError("unavailable")
        lc.stop_if_safe("https://dashboard.test", "control", "railway", "project", "env", "service")
        graphql.assert_not_called()

    @patch.object(lc, "graphql")
    @patch.object(lc, "health", return_value=True)
    def test_morning_start_does_not_redeploy_healthy_service(self, health, graphql):
        lc.start_if_needed("https://dashboard.test", "railway", "project", "env", "service")
        graphql.assert_not_called()

    @patch.object(lc, "graphql")
    @patch.object(lc, "request_json")
    def test_safe_shutdown_requests_stop_only_after_all_guards_clear(self, request, graphql):
        request.return_value = {
            "active_sessions": 0,
            "active_authenticated_requests": 0,
            "protected_jobs": {"imports": 0, "scheduled_reports": 0},
        }
        graphql.side_effect = [
            {"deployments": {"edges": [{"node": {"id": "dep-1", "status": "SUCCESS"}}]}},
            {"deploymentStop": True},
        ]
        lc.stop_if_safe("https://dashboard.test", "control", "railway", "project", "env", "service")
        self.assertEqual(graphql.call_count, 2)
        self.assertIn("deploymentStop", graphql.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
