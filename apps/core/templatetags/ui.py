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
