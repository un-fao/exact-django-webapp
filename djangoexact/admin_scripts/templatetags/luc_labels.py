from django import template

from admin_scripts.luc_permutations import display_value

register = template.Library()

register.filter("luc_label", display_value)
