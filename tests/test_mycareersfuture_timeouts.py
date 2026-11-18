from __future__ import annotations

from io import BytesIO
from unittest import TestCase, main
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from job_discovery.http_client import JobSourceError, JobSourceTimeout, JsonHttpClient
from job_discovery.models import SearchSpec
from job_discovery.sources.mycareersfuture import MyCareersFutureSource


class MyCareersFutureTimeoutTests(TestCase):
    def test_default_timeout_is_source_specific(self):
        self.assertEqual(MyCareersFutureSource().client.timeout, 45)
        self.assertEqual(JsonHttpClient().timeout, 25)

    def test_direct_and_wrapped_timeouts_remain_distinguishable(self):
        for error in (TimeoutError("read timed out"), URLError(TimeoutError("read timed out"))):
            with self.subTest(error=error), patch(
                "job_discovery.http_client.urlopen", side_effect=error
            ):
                with self.assertRaisesRegex(JobSourceTimeout, "after 25s"):
                    JsonHttpClient().get_json(MyCareersFutureSource.BASE_URL)

    def test_read_timeout_retries_same_page_then_normalizes_response(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"results":[{"uuid":"test-1","title":"Software Engineer","description":"Build software","postedCompany":{"name":"Example"}}]}'
        sleep = Mock()
        with patch("job_discovery.http_client.urlopen", side_effect=[
            TimeoutError("read timed out"), response,
        ]) as open_request:
            source = MyCareersFutureSource(client=JsonHttpClient(sleep_fn=sleep))
            jobs = source.fetch(SearchSpec(query="Software", max_pages=1))
        self.assertEqual([job.source_job_id for job in jobs], ["test-1"])
        self.assertEqual(open_request.call_count, 2)
        self.assertEqual(
            open_request.call_args_list[0].args[0].full_url,
            open_request.call_args_list[1].args[0].full_url,
        )
        sleep.assert_called_once_with(1.0)

    def test_repeated_timeout_is_bounded_and_reported_as_failure(self):
        client = Mock()
        client.get_json.side_effect = JobSourceTimeout("request timed out")
        with self.assertRaisesRegex(JobSourceTimeout, "timed out twice.*page 1"):
            MyCareersFutureSource(client=client).fetch(SearchSpec(query="Software"))
        self.assertEqual(client.get_json.call_count, 2)
        client.pause.assert_called_once_with(1.0)

    def test_http_denial_and_non_timeout_errors_are_not_retried(self):
        errors = [
            HTTPError(MyCareersFutureSource.BASE_URL, 403, "Forbidden", {}, BytesIO(b"Access denied")),
            HTTPError(MyCareersFutureSource.BASE_URL, 429, "Too Many Requests", {}, BytesIO(b"Rate limit")),
            URLError("DNS resolution failed"),
        ]
        for error in errors:
            with self.subTest(error=error), patch(
                "job_discovery.http_client.urlopen", side_effect=error
            ) as open_request:
                sleep = Mock()
                with self.assertRaises(JobSourceError) as raised:
                    MyCareersFutureSource(
                        client=JsonHttpClient(sleep_fn=sleep)
                    ).fetch(SearchSpec(query="Software"))
                self.assertNotIsInstance(raised.exception, JobSourceTimeout)
                open_request.assert_called_once()
                sleep.assert_not_called()


if __name__ == "__main__":
    main()
