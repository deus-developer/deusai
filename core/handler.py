from typing import Callable, Any, Optional, List

from .update import InnerUpdate

FilterType = Callable[[InnerUpdate], bool]
CallbackType = Callable[[InnerUpdate], Any]


class InnerHandler:
    def __init__(
        self,
        up_filter: FilterType,
        target: CallbackType,
        custom_filters: Optional[List[FilterType]] = None
    ):
        if custom_filters is None:
            custom_filters = []

        self.target = target
        self.filter = up_filter
        self.custom_filters = custom_filters

    def __call__(self, update: InnerUpdate):
        if not self.filter(update):
            return

        if all(
            custom_filter(update)
            for custom_filter in self.custom_filters
        ):
            return self.target(update)
