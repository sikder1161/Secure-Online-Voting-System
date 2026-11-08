"""Regression tests: sensitive email addresses must be masked in UI."""
from django.template import Context, Template
from django.test import SimpleTestCase

from .email_masking import mask_email_address


class EmailMaskingTests(SimpleTestCase):
    def test_regular_address(self):
        self.assertEqual(
            mask_email_address("neutonsikder01@gmail.com"),
            "ne**********01@g****.com",
        )

    def test_short_address_never_shows_full_local_part(self):
        self.assertEqual(mask_email_address("a@b.co"), "*@*.co")
        self.assertEqual(mask_email_address("abc@xyz.net"), "a**@x****.net")

    def test_missing_or_invalid_address_does_not_echo_input(self):
        self.assertEqual(mask_email_address(""), "Email unavailable")
        self.assertEqual(mask_email_address(None), "Email unavailable")
        self.assertEqual(mask_email_address("confidential-email"), "Email unavailable")

    def test_template_filter_displays_mask_not_original(self):
        template = Template("{% load email_privacy %}{{ address|mask_email }}")
        result = template.render(Context({"address": "neutonsikder01@gmail.com"}))
        self.assertEqual(result, "ne**********01@g****.com")
        self.assertNotIn("neutonsikder01@gmail.com", result)
