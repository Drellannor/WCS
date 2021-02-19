# ../wcs/core/modules/items/manager.py

# ============================================================================
# >> IMPORTS
# ============================================================================
# Python Imports
#   Warnings
from warnings import warn

# WCS Imports
#   Constants
from ...constants import ItemReason
from ...constants.paths import ITEM_PATH_ES
from ...constants.paths import ITEM_PATH
#   Listeners
from ...listeners import OnIsItemUsable
from ...listeners import OnPluginItemLoad
#   Menus
from ...menus import shopmenu_menu
from ...menus import shopinfo_menu
#   Modules
from . import _callbacks
from ..base import _BaseManager
from ..base import _BaseSetting


# ============================================================================
# >> ALL DECLARATION
# ============================================================================
__all__ = (
    'item_manager',
)


# ============================================================================
# >> CLASSES
# ============================================================================
class ItemSetting(_BaseSetting):
    _module_name = 'items'
    _events = _callbacks

    def __init__(self, name):
        super().__init__(name, ITEM_PATH)

        if isinstance(self.config.get('event'), str):
            self.config['event'] = [self.config['event']]

    def usable_by(self, wcsplayer):
        data = {'reason':None}

        OnIsItemUsable.manager.notify(wcsplayer, self, data)

        if data['reason'] is not None:
            return data['reason']

        if item_manager._round_restart:
            return ItemReason.ROUND_RESTART

        required = self.config.get('required')

        if required:
            if wcsplayer.total_level < required:
                return ItemReason.REQUIRED_LEVEL

        dab = self.config.get('dab')

        if dab is not None:
            if not dab == 2:
                player = wcsplayer.player

                if dab == player.dead:
                    return ItemReason.WRONG_STATUS

        maxitems = wcsplayer.items._maxitems

        for category in self.config['categories']:
            if maxitems[category] >= item_manager._category_max_items[category]:
                return ItemReason.TOO_MANY_CATEGORY

        if self.name in wcsplayer.active_race.settings.config['restrictitem']:
            return ItemReason.RACE_RESTRICTED

        cost = self.config.get('cost')

        if cost is not None:
            player = wcsplayer.player

            if cost > player.cash:
                return ItemReason.CANNOT_AFFORD

        count = self.config.get('count')

        if count:
            item = wcsplayer.items.get(self.name)

            if item is not None:
                if item.count >= count:
                    return ItemReason.TOO_MANY

        return ItemReason.ALLOWED

    def add_to_category(self, category):
        self._add_to_category(item_manager, 0, category, shopmenu_menu, shopinfo_menu)


class _ItemManager(_BaseManager):
    _instance = ItemSetting
    _module_name = 'items'
    _path = ITEM_PATH
    _es_path = ITEM_PATH_ES
    _listener = OnPluginItemLoad

    def __init__(self):
        super().__init__()

        self._category_max_items = {}
        self._round_restart = False

    def load_all(self):
        self._move_misplaced_files()

        config = self._get_or_create_config()

        for category, value in config.get('maxitems', {}).items():
            self._category_max_items[category] = value

        self._load_categories_and_values(config)

        for category in self._info_category_menus:
            if category not in self._category_max_items:
                warn(f'The category "{category}" was not found in items.json under "maxitems" - setting it to 1')
                self._category_max_items[category] = 1
item_manager = _ItemManager()
