import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import bilibili_auth_service, bilibili_resolver


class BilibiliResolverTests(unittest.TestCase):
    def test_select_bilibili_page_defaults_to_first_page(self):
        self.assertEqual(bilibili_resolver.select_bilibili_page("https://www.bilibili.com/video/BV123"), "1")

    def test_select_bilibili_page_reads_query_value(self):
        self.assertEqual(bilibili_resolver.select_bilibili_page("https://www.bilibili.com/video/BV123?p=8"), "8")

    def test_bbdown_quality_priority(self):
        self.assertIn("8K 超高清", bilibili_resolver.bbdown_quality_priority("best"))
        self.assertIn("1080P 高码率", bilibili_resolver.bbdown_quality_priority("1080p"))
        self.assertNotIn("1080P", bilibili_resolver.bbdown_quality_priority("720p"))

    def test_build_bbdown_command_contains_cookie_without_logging_it(self):
        with patch.object(bilibili_resolver, "get_bilibili_cookie", return_value="SESSDATA=secret;bili_jct=token"):
            command = bilibili_resolver.build_bbdown_command(
                "https://www.bilibili.com/video/BV123?p=2",
                "best",
                Path("downloads"),
                "BBDown",
            )
        self.assertIn("-c", command)
        self.assertIn("SESSDATA=secret;bili_jct=token", command)
        self.assertEqual(command[command.index("-p") + 1], "2")
        self.assertEqual(command[command.index("-e") + 1], "avc,hevc,av1")
        self.assertEqual(command[command.index("-F") + 1], "<videoTitle>_<dfn>_Bilibili")

    def test_bilibili_quality_options_remain_selectable_after_login(self):
        options = bilibili_resolver.build_bilibili_quality_options([], logged_in=True)
        self.assertEqual([item.value for item in options], ["best", "1080p", "720p", "audio"])
        self.assertTrue(all(item.available for item in options))

    def test_normalize_bilibili_download_file_preserves_bbdown_quality_source_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp)
            nested = target_dir / "source"
            nested.mkdir()
            source = nested / "又是中山大学，生科院副院长代表作，造假！_1080P 高清_Bilibili.mp4"
            source.write_bytes(b"video")

            normalized = bilibili_resolver.normalize_bilibili_download_file(
                source,
                target_dir,
                "fallback title",
                "1080p",
            )

            self.assertEqual(normalized.name, "又是中山大学，生科院副院长代表作，造假！_1080P 高清_Bilibili.mp4")
            self.assertTrue(normalized.exists())
            self.assertFalse(source.exists())

    def test_normalize_bilibili_download_file_falls_back_to_title_quality_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp)
            nested = target_dir / "source"
            nested.mkdir()
            source = nested / "_.mp4"
            source.write_bytes(b"video")

            normalized = bilibili_resolver.normalize_bilibili_download_file(
                source,
                target_dir,
                "又是中山大学，生科院副院长代表作，造假！",
                "1080p",
            )

            self.assertEqual(normalized.name, "又是中山大学，生科院副院长代表作，造假！_1080p_Bilibili.mp4")
            self.assertTrue(normalized.exists())
            self.assertFalse(source.exists())

    def test_safe_file_stem_does_not_return_single_underscore(self):
        self.assertEqual(bilibili_resolver.safe_file_stem("///"), "bilibili_video")


class BilibiliAuthTests(unittest.TestCase):
    def test_cookie_from_redirect_keeps_minimum_cookie_fields(self):
        redirect = "https://www.bilibili.com/?SESSDATA=abc,bcd&bili_jct=csrf&DedeUserID=42&not_needed=x"
        cookie = bilibili_auth_service.cookie_from_bilibili_redirect(redirect)
        self.assertEqual(cookie, "SESSDATA=abc%2Cbcd;bili_jct=csrf;DedeUserID=42")

    def test_redact_sensitive_text(self):
        message = "Cookie: SESSDATA=abc;bili_jct=csrf\nBBDown -c SESSDATA=abc"
        redacted = bilibili_auth_service.redact_sensitive_text(message)
        self.assertNotIn("abc", redacted)
        self.assertIn("<redacted>", redacted)

    def test_session_write_and_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            auth_file = Path(tmp) / "bilibili_session.json"
            with patch.object(bilibili_auth_service, "SAVEANY_BILIBILI_AUTH_FILE", auth_file):
                bilibili_auth_service.write_bilibili_cookie("SESSDATA=secret")
                self.assertTrue(bilibili_auth_service.get_bilibili_session().isLoggedIn)
                bilibili_auth_service.clear_bilibili_session()
                self.assertFalse(bilibili_auth_service.get_bilibili_session().isLoggedIn)


if __name__ == "__main__":
    unittest.main()
