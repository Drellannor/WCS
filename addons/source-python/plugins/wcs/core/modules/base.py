# ../wcs/core/modules/base.py

# ============================================================================
# >> IMPORTS
# ============================================================================
# Python Imports
#   Collections
from collections import OrderedDict
from collections import defaultdict
#   Errno
from errno import ENOENT
#   Importlib
from importlib import import_module
#   JSON
from json import load as json_load
from json import dump as json_dump
#   OS
from os import strerror
#   Sys
from sys import modules
#   Warnings
from warnings import warn

# Source.Python Imports
#   Core
from core import GAME_NAME
from core import AutoUnload
from core import WeakAutoUnload
#   Engines
from engines.precache import Model
from engines.server import global_vars
from engines.server import execute_server_command
#   Hooks
from hooks.exceptions import except_hooks
#   Listeners
from listeners import OnLevelInit
#   Menus
from ..menus.base import PagedOption
#   Plugins
from plugins.manager import PluginManager
#   Translations
from translations.strings import LangStrings

# WCS Imports
#   Constants
from ..constants import IS_ESC_SUPPORT_ENABLED
from ..constants import ModuleType
from ..constants.paths import CFG_PATH
#   Helpers
from ..helpers.effects import effects_manager
#   Menus
from ..menus.base import PagedPageCountMenu
#   Translations
from ..translations import categories_strings
from ..translations import menu_strings

# Is ESC supported?
if IS_ESC_SUPPORT_ENABLED:
    # EventScripts Imports
    #   ES
    import es
    #   ESC
    import esc


# ============================================================================
# >> ALL DECLARATION
# ============================================================================
__all__ = ()


# ============================================================================
# >> GLOBAL VARIABLES
# ============================================================================
_models = defaultdict(dict)


# ============================================================================
# >> CLASSES
# ============================================================================
class _BaseManager(dict):
    def __init__(self):
        super().__init__()

        self._category_to_values = defaultdict(list)
        self._category_menus = {}
        self._info_category_menus = {}

        self._refresh_config = set()

    def _load_categories_and_values(self, config):
        value_categories = OrderedDict()

        for category, data in config['categories'].items():
            if not category.startswith('_'):
                for name in data:
                    if not name.startswith('_'):
                        if self._is_valid_value_file(name):
                            if name not in value_categories:
                                value_categories[name] = []

                            value_categories[name].append(category)

        for name in config[self._module_name]:
            if not name.startswith('_'):
                if self._is_valid_value_file(name):
                    if name not in value_categories:
                        value_categories[name] = []

                        # Just to add it to the menu
                        value_categories[name].append(None)

        for name, categories in value_categories.items():
            try:
                setting = self.load(name)
            except:
                except_hooks.print_exception()
            else:
                for category in categories:
                    setting.add_to_category(category)

    def _get_or_create_config(self):
        if (CFG_PATH / f'{self._module_name}.json').isfile():
            with open(CFG_PATH / f'{self._module_name}.json') as inputfile:
                config = json_load(inputfile)

            if 'categories' not in config:
                config['categories'] = {}
            if self._module_name not in config:
                config[self._module_name] = []
        else:
            config = {'categories':{}, self._module_name:[]}

            if self._module_name == 'items':
                config['maxitems'] = {}

            for name in set(x.name for x in (self._path.listdir() + (self._es_path.listdir() if IS_ESC_SUPPORT_ENABLED else []))):
                if self._is_valid_config_files(name):
                    config[self._module_name].append(name)

            with open(CFG_PATH / f'{self._module_name}.json', 'w') as outputfile:
                json_dump(config, outputfile, indent=4)

        return config

    def _move_misplaced_files(self):
        if IS_ESC_SUPPORT_ENABLED:
            for directory in self._path.listdir():
                name = directory.name
                new_path = self._es_path / name

                if (directory / f'{name}.py').isfile():
                    new_path.makedirs_p()
                    (directory / f'{name}.py').move(new_path / f'{name}.py')

                if (directory / f'es_{name}.txt').isfile():
                    new_path.makedirs_p()
                    (directory / f'es_{name}.txt').move(new_path / f'es_{name}.txt')

    def _get_value_module_type(self, name):
        if (self._path / name / '__init__.py').isfile():
            return ModuleType.SP

        if IS_ESC_SUPPORT_ENABLED:
            path_es = self._es_path / name

            if (path_es / f'{name}.py').isfile():
                return ModuleType.ESP

            if (path_es / f'es_{name}.txt').isfile():
                return ModuleType.ESS

        return None

    def _is_valid_value_file(self, name):
        return self._get_value_module_type(name) is not None

    def _is_valid_config_files(self, name):
        path = self._path / name

        return (path / 'config.json').isfile() and (path / 'strings.ini').isfile()

    def load(self, name):
        assert name not in self, name

        try:
            instance = self._instance(name)
        except:
            warn(f'Unable to load {name}.')

            raise

        instance.type = self._get_value_module_type(name)

        if instance.type is None:
            raise FileNotFoundError(ENOENT, strerror(ENOENT), self._path / name / '__init__.py')

        self[name] = instance

        if instance.type is ModuleType.SP:
            try:
                self[name].module = import_module(f'wcs.modules.{self._module_name}.{name}')
            except:
                del self[name]

                raise
        else:
            es.load(f'wcs/modules/{self._module_name}/{name}')

        self._listener.manager.notify(name, instance)

        return instance

    def load_all(self):
        raise NotImplementedError()

    def unload(self, name):
        if self[name].type is ModuleType.SP:
            module_name = f'wcs.modules.{self._module_name}.{name}'

            _remove_unload_instances(module_name)

            del modules[module_name]
        else:
            es.unload(f'wcs/modules/{self._module_name}/{name}')

        del self[name]

    def unload_all(self):
        for x in [*self]:
            self.unload(x)

    def find(self, name):
        return self[name.rsplit('.', 1)[1]]

    @property
    def _instance(self):
        raise NotImplementedError()

    @property
    def _module_name(self):
        raise NotImplementedError()

    @property
    def _path(self):
        raise NotImplementedError()

    @property
    def _es_path(self):
        raise NotImplementedError()

    @property
    def _listener(self):
        raise NotImplementedError()


class _BaseSetting(object):
    def __init__(self, name, path):
        self.name = name
        self.type = None
        self.module = None

        with open(path / name / 'config.json') as inputfile:
            self.config = json_load(inputfile)

        self.strings = LangStrings(path / name / 'strings')

        self.config['categories'] = []

    # TODO: Could use a hand... don't hate me
    def _add_to_category(self, container, module, category, menu_choice, menu_info):
        container._category_to_values[category].append(self.name)

        if category is None:
            menu_choice.append(PagedOption(self.strings['name'], self.name))
            menu_info.append(PagedOption(self.strings['name'], self.name))
            return

        self.config['categories'].append(category)

        if module:
            from ..menus.build import changerace_menu_build as menu_choice_build
            from ..menus.close import raceinfo_menu_close as menu_info_close
            from ..menus.select import changerace_menu_select as menu_choice_select
            from ..menus.select import raceinfo_menu_select as menu_info_select

            menu_choice_name = 'changerace_menu'
            menu_info_name = 'raceinfo_menu'
        else:
            from ..menus.build import shopmenu_menu_build as menu_choice_build
            from ..menus.close import shopinfo_menu_close as menu_info_close
            from ..menus.select import shopmenu_menu_select as menu_choice_select
            from ..menus.select import shopinfo_menu_select as menu_info_select

            menu_choice_name = 'shopmenu_menu'
            menu_info_name = 'shopinfo_menu'

        if category not in container._category_menus:
            menu = container._category_menus[category] = PagedPageCountMenu()
            menu.name = category
            menu.title = menu_strings[f'{menu_choice_name} title']
            menu.parent_menu = menu_choice
            menu.build_callback = menu_choice_build
            menu.select_callback = menu_choice_select

            menu_choice.append(PagedOption(categories_strings.get(category, category), menu))

            menu = container._info_category_menus[category] = PagedPageCountMenu()
            menu.name = category
            menu.title = menu_strings[f'{menu_info_name} title']
            menu.parent_menu = menu_info
            menu.select_callback = menu_info_select
            menu.close_callback = menu_info_close

            menu_info.append(PagedOption(categories_strings.get(category, category), menu))

        container._category_menus[category].append(PagedOption(self.strings['name'], self.name))
        container._info_category_menus[category].append(PagedOption(self.strings['name'], self.name))

    def execute(self, name, *args):
        if self.type is ModuleType.SP:
            callback = self._events.get(self.name, {}).get(name, None)

            if callback is not None:
                callback(*args)
        elif self.type is ModuleType.ESP:
            callback = es.addons.Blocks.get(f'wcs/modules/{self._module_name}/{self.name}/{name}')

            if callback is not None:
                callback(*args)
        elif self.type is ModuleType.ESS:
            addon = esc.addons.get(f'wcs/modules/{self._module_name}/{self.name}')

            if addon is not None:
                executor = addon.blocks.get(name)

                if executor is not None:
                    executor.run()
        elif self.type is ModuleType.ESS_INI or self.type is ModuleType.ESS_KEY:
            commands = self.cmds.get(name)

            if commands is not None and commands:
                for cmd in commands.split(';'):
                    execute_server_command('es', cmd)

    def get_game_entry(self, entry):
        return self.config['games'].get(GAME_NAME, self.config['games']['default'])[entry]

    def get_effect_entry(self, entry):
        config = self.config['effects'][entry]
        effect = effects_manager[config['type']]

        for key, value in config['args'].items():
            if value is None:
                continue

            if isinstance(value, str):
                if value.startswith('$'):
                    current = None
                    values = value[1:].split('.')

                    for i, next_key in enumerate(values):
                        if current is None:
                            current = self.config[next_key]
                        else:
                            if next_key == 'GAME_NAME':
                                if GAME_NAME in current:
                                    if values[i + 1] in current[GAME_NAME]:
                                        next_key = GAME_NAME
                                    else:
                                        next_key = 'default'
                                else:
                                    next_key = 'default'

                            current = current[next_key]

                    value = current

                # It's probably a model
                if '/' in value or '\\' in value:
                    value = _models[effect][key] = Model(value)

                    if not global_vars.map_name:
                        continue

            setattr(effect, key, value)

        return effect

    def add_to_category(self, category):
        raise NotImplementedError()

    def usable_by(self, wcsplayer):
        raise NotImplementedError()

    @property
    def _module_name(self):
        raise NotImplementedError()

    @property
    def _events(self):
        raise NotImplementedError()


# ============================================================================
# >> FUNCTIONS
# ============================================================================
def _remove_unload_instances(name):
    """Helper cleanup function for when skills are unloaded."""
    # Does the skill have anything that should be auto unloaded?
    if name in AutoUnload._module_instances:
        # Call the PluginManager's method, so they get correctly removed
        PluginManager._unload_auto_unload_instances(AutoUnload._module_instances[name])
        # Remove the skill from the PluginManager
        del AutoUnload._module_instances[name]

    # Does the skill have anything that should be auto unloaded?
    if name in WeakAutoUnload._module_instances:
        # Call the PluginManager's method, so they get correctly removed
        PluginManager._unload_auto_unload_instances(WeakAutoUnload._module_instances[name].values())
        # Remove the skill from the PluginManager
        del WeakAutoUnload._module_instances[name]


# ============================================================================
# >> LISTENERS
# ============================================================================
@OnLevelInit
def on_level_init(map_name=None):
    for effect in _models:
        for key, value in _models[effect].items():
            setattr(effect, key, value)


if global_vars.map_name:
    on_level_init()
