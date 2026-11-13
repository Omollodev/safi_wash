"""The icon system: Lucide sprite + {% icon %} tag. Fails if a page asks for an icon the sprite does not have."""
import re
from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.testing import PASSWORD, make_user
from apps.dashboard.selectors import CATEGORY_ICONS, EVENT_ICONS
from apps.notifications.models import Notification

ROOT = Path(settings.BASE_DIR)
SPRITE = (ROOT / "static/img/icons.svg").read_text()
SPRITE_IDS = set(re.findall(r'<symbol id="([a-z0-9-]+)"', SPRITE))


def source_files(*patterns):
    for pattern in patterns:
        yield from (p for p in ROOT.glob(pattern) if "tests" not in p.parts and "node_modules" not in p.parts)


class IconTagTests(SimpleTestCase):
    def render(self, source, **ctx):
        return Template(source).render(Context(ctx))

    def test_renders_sprite_reference_hidden_from_screen_readers(self):
        html = self.render('{% icon "clock" "icon-lg" %}')
        self.assertIn("icons.svg#clock", html)
        self.assertIn('class="icon icon-lg"', html)
        self.assertIn('aria-hidden="true"', html)

    def test_icon_name_from_a_variable_works(self):
        self.assertIn("icons.svg#wallet", self.render("{% icon name %}", name="wallet"))

    def test_bad_names_render_nothing(self):  # a name is never allowed to break out of the attribute
        for bad in ['x"><script>', "../etc", "UPPER", "", None, "a" * 80]:
            with self.subTest(bad=bad):
                self.assertEqual(self.render("{% icon name %}", name=bad).strip(), "")

    def test_initials_filter(self):
        class U:
            first_name, last_name, username = "Kerry", "Fransis", "kf"
        self.assertEqual(self.render("{{ u|initials }}", u=U()), "KF")

        class V:
            first_name, last_name, username = "", "", "admin"
        self.assertEqual(self.render("{{ u|initials }}", u=V()), "AD")


class SpriteCoverageTests(SimpleTestCase):
    def used_in_templates(self):
        names = set()
        for f in source_files("templates/**/*.html"):
            names |= set(re.findall(r'\{% icon "([a-z0-9-]+)"', f.read_text()))
        return names

    def test_every_template_icon_is_in_the_sprite(self):
        self.assertFalse(self.used_in_templates() - SPRITE_IDS, "add these to scripts/build_icon_sprite.py")

    def test_every_javascript_icon_is_in_the_sprite(self):
        names = set()
        for f in source_files("static/js/*.js"):
            text = f.read_text()
            names |= set(re.findall(r'\bicon(?:Html)?\("([a-z0-9-]+)"', text)) | set(re.findall(r'\bicon: "([a-z0-9-]+)"', text))
        self.assertFalse(names - SPRITE_IDS, "add these to scripts/build_icon_sprite.py")

    def test_every_python_icon_is_in_the_sprite(self):
        names = set(CATEGORY_ICONS.values()) | set(EVENT_ICONS.values()) | {"droplet", "activity"}
        names |= {Notification(type=t).icon for t, _ in Notification.Type.choices}
        self.assertFalse(names - SPRITE_IDS)

    def test_no_emoji_and_no_bootstrap_icons_left(self):
        emoji = re.compile("[\U0001F000-\U0001FAFF☀-➿⭐✅]|&#1[0-9]{4};|&#x1?[Ff][0-9A-Fa-f]{3};")
        for f in source_files("templates/**/*.html", "static/js/*.js", "static/css/*.css", "apps/**/*.py"):
            text = f.read_text()
            with self.subTest(file=str(f.relative_to(ROOT))):
                self.assertIsNone(emoji.search(text), "use a Lucide icon instead of an emoji")
                self.assertNotIn("bootstrap-icons", text)
                self.assertNotRegex(text, r"\bbi bi-|class=\"bi\b")


class NavigationTests(TestCase):
    def test_current_page_is_highlighted_for_staff(self):
        admin = make_user("admin")
        self.client.login(username=admin.username, password=PASSWORD)
        html = self.client.get(reverse("jobs:list")).content.decode()
        active = re.findall(r'<a class="nav-link active" aria-current="page" href="([^"]+)"', html)
        self.assertEqual(active, [reverse("jobs:list")])
        self.assertIn('id="bell-link"', html)

    def test_dashboard_link_is_active_on_the_dashboard_only(self):
        admin = make_user("admin")
        self.client.login(username=admin.username, password=PASSWORD)
        html = self.client.get(reverse("dashboard:home")).content.decode()
        self.assertEqual(re.findall(r'class="nav-link active" aria-current="page" href="([^"]+)"', html), [reverse("dashboard:home")])
