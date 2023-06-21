import logging

import voluptuous as vol

from .cyltek.util import get_logger, is_valid_MAC, source_hash


def MAC(msg=None):
    def f(MAC):
        if is_valid_MAC(MAC):
            return str(MAC)
        else:
            raise vol.Invalid(msg or ("incorrect MAC address !!"))
    return f
