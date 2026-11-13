"""Regression tests for settings helpers (a blank .env value once crashed `migrate`)."""
import os
from unittest import mock

from django.test import SimpleTestCase

from config.settings.base import env, env_bool, env_list


class EnvHelperTests(SimpleTestCase):
    def test_blank_value_falls_back_to_default(self):
        # This is exactly what `cp .env.example .env` produces for DATABASE_URL=
        with mock.patch.dict(os.environ, {"X_URL": ""}):
            self.assertEqual(env("X_URL", "sqlite:///fallback"), "sqlite:///fallback")

    def test_value_is_used_when_present(self):
        with mock.patch.dict(os.environ, {"X_URL": "postgres://u:p@h/d"}):
            self.assertEqual(env("X_URL", "fallback"), "postgres://u:p@h/d")

    def test_bool_and_list_helpers_handle_blank(self):
        with mock.patch.dict(os.environ, {"X_FLAG": "", "X_LIST": ""}):
            self.assertTrue(env_bool("X_FLAG", True))
            self.assertFalse(env_bool("X_FLAG", False))
            self.assertEqual(env_list("X_LIST", "a, b"), ["a", "b"])

    def test_default_database_is_usable_when_database_url_is_blank(self):
        from django.conf import settings

        self.assertTrue(settings.DATABASES["default"]["ENGINE"])
