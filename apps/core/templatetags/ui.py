from django import template

register = template.Library()


@register.filter
def auth_input(field):
    """
    Render a form field with accessible error wiring: aria-invalid, aria-describedby
    (pointing at the error list or the hint) and Bootstrap's is-invalid class.
    """
    attrs = {}
    if field.errors:
        attrs["aria-invalid"] = "true"
        attrs["aria-describedby"] = f"{field.auto_id}_err"
        existing = field.field.widget.attrs.get("class", "")
        attrs["class"] = f"{existing} is-invalid".strip()
    elif field.help_text:
        attrs["aria-describedby"] = f"{field.auto_id}_hint"
    return field.as_widget(attrs=attrs)


# ---------------------------------------------------------------- icons (Lucide sprite)
import re  # noqa: E402

from django.templatetags.static import static  # noqa: E402
from django.utils.html import format_html  # noqa: E402

_ICON_NAME = re.compile(r"^[a-z0-9-]{1,40}$")


@register.simple_tag
def icon(name, css_class=""):
    """
    {% icon "clock" %}  or  {% icon "clock" "icon-lg text-primary" %}

    Draws a Lucide icon from static/img/icons.svg. Icons are decorative (the text beside them says
    what they mean), so they are hidden from screen readers. Icon-only buttons need an aria-label.
    """
    name = str(name or "")
    if not _ICON_NAME.match(name):
        return ""
    return format_html(
        '<svg class="{}" aria-hidden="true" focusable="false"><use href="{}#{}"></use></svg>',
        f"icon {css_class}".strip(), static("img/icons.svg"), name,
    )


# ---------------------------------------------------------------- navigation
@register.simple_tag(takes_context=True)
def nav_attrs(context, *targets):
    """
    Marks the navigation link for the current page:  <a {% nav_attrs 'jobs' %} href=...>
    A target is an app name ('jobs') or 'app:url_name' ('dashboard:home') for one specific page.
    """
    match = getattr(context.get("request"), "resolver_match", None)
    current = match is not None and any(
        t == match.app_name or t == f"{match.app_name}:{match.url_name}" for t in targets
    )
    if current:
        return format_html('class="{}" {}="{}"', "nav-link active", "aria-current", "page")
    return format_html('class="{}"', "nav-link")


@register.filter
def initials(user):
    """Two letters for the avatar circle: 'Kerry Fransis' -> 'KF', 'admin' -> 'AD'."""
    first = (getattr(user, "first_name", "") or "").strip()
    last = (getattr(user, "last_name", "") or "").strip()
    if first and last:
        return (first[0] + last[0]).upper()
    name = first or last or getattr(user, "username", "") or "?"
    return name[:2].upper()
