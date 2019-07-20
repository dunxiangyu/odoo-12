INHERITED_ATTRS = ('_returns',)


class Meta(type):
    def __new__(cls, name, bases, attrs):
        # parent = type.__new__(cls, name, bases, {})
        #
        # for key, value in list(attrs.items()):
        #     if not key.startswith('__') and callable(value):
        #         value = propagate(getattr(parent, key, None), value)
        #         if not hasattr(value, '_api'):
        #             try:
        #                 value = guess(value)
        #             except TypeError:
        #                 pass
        #
        #         attrs[key] = value
        return type.__new__(cls, name, bases, attrs)


def propagate(method1, method2):
    if method1:
        for attr in INHERITED_ATTRS:
            if hasattr(method1, attr) and not hasattr(method2, attr):
                setattr(method2, attr, getattr(method1, attr))
    return method2


def guess(method):
    if hasattr(method, '_api'):
        return method
