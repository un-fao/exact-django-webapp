from django import template

register = template.Library()


@register.filter
def attr(obj, attr_name):
    """Returns the attribute of an object dynamically."""
    return getattr(obj, attr_name, None)  # Return None if attribute does not exist
