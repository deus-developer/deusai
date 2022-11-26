from .update import Update


class Handler:
    def __init__(self, up_filter: callable, target: callable, custom_filters=None):
        if custom_filters is None:
            custom_filters = []
        self.target = target
        self.filter = up_filter
        self.custom_filters = custom_filters

    def __call__(self, update: Update):
        if self.filter(update):
            for cf in self.custom_filters:
                if not cf(update):
                    return
            self.target(update=update)
