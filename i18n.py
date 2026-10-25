"""Offline UTF-8 translations for the Tk application.

Translation keys are original source messages, following gettext conventions.
Paths and internal category identifiers must never be translated.
"""
import json
import locale
import logging
import os
from pathlib import Path
import re
from string import Formatter
import tempfile

import arabic_reshaper
from bidi.algorithm import get_display

LOG = logging.getLogger(__name__)
LOCALES = Path(__file__).resolve().parent / 'locales'


def fields(text):
    """Include format specifications to catch invalid translator substitutions."""
    return sorted((name, spec, conversion) for _, name, spec, conversion
                  in Formatter().parse(text) if name is not None)


class Translations:
    def __init__(self, directory=LOCALES, settings_path=None, system_locale=None):
        self.catalogs = {}
        for path in sorted(Path(directory).glob('*.json')):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(data['name'], str) or data['direction'] not in ('ltr', 'rtl'):
                    raise ValueError('Invalid locale metadata')
                if not isinstance(data['messages'], dict):
                    raise ValueError('Invalid messages')
                valid = {}
                for key, value in data['messages'].items():
                    if isinstance(value, str) and fields(key) == fields(value):
                        valid[key] = value
                    else:
                        LOG.warning('Ignoring invalid translation in %s: %s', path.name, key)
                self.catalogs[path.stem] = dict(data, messages=valid)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                LOG.warning('Could not load locale %s: %s', path.name, exc)
        if 'en' not in self.catalogs:
            raise RuntimeError('The English fallback translation catalog is missing')
        if settings_path is None:
            base = Path(os.environ.get('APPDATA') or
                        os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
            settings_path = os.environ.get('CDRIVE_CLEANER_SETTINGS') or base / 'CDriveCleaner' / 'settings.json'
        self.settings_path = Path(settings_path)
        self.settings = self._read_settings()
        if system_locale is None:
            try:
                system_locale = locale.getlocale()[0] or ''
            except ValueError:
                system_locale = ''
        preferred = os.environ.get('CDRIVE_CLEANER_LANGUAGE') or self.settings.get('language') or system_locale
        self.language = self.resolve(preferred)

    def _read_settings(self):
        try:
            data = json.loads(self.settings_path.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def resolve(self, code):
        code = str(code or '').split('.')[0].replace('-', '_')
        for available in self.catalogs:
            if available.casefold() == code.casefold():
                return available
        base = code.split('_')[0].lower()
        # Do not silently map traditional Chinese to simplified Chinese.
        if base != 'zh':
            for available in self.catalogs:
                if available.split('_')[0].lower() == base:
                    return available
        return 'en'

    @property
    def rtl(self):
        return self.catalogs[self.language]['direction'] == 'rtl'

    def translate(self, key, **values):
        fallback = self.catalogs['en']['messages'].get(key, key)
        text = self.catalogs[self.language]['messages'].get(key, fallback)
        return text.format(**values) if values else text

    def save_language(self, code):
        if code not in self.catalogs:
            raise ValueError('Unknown language: ' + str(code))
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        # Merge with current settings, preserving unrelated preferences.
        settings = dict(self._read_settings(), language=code)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=self.settings_path.parent,
                                             delete=False) as handle:
                temp_path = Path(handle.name)
                json.dump(settings, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
            os.replace(str(temp_path), str(self.settings_path))
            self.settings = settings
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()


i18n = Translations()
tr = i18n.translate


def display(text):
    """Shape Arabic and apply bidi ordering for Tk's visual text widgets.

    Call only at the presentation boundary. Native Windows dialogs receive
    logical Unicode; file paths, identifiers and editable values stay intact.
    """
    text = str(text)
    if re.search('[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]', text):
        return '\n'.join(get_display(arabic_reshaper.reshape(line), base_dir='R')
                         for line in text.split('\n'))
    return text


def apply_direction(window):
    """Mirror horizontal packing and text alignment for RTL locales."""
    import tkinter as tk
    from tkinter import ttk
    rtl = i18n.rtl
    grid_columns = window.grid_size()[0]
    for child in window.winfo_children():
        if rtl and child.winfo_manager() == 'pack':
            options = child.pack_info()
            side = options.get('side')
            anchor = str(options.get('anchor', 'center'))
            updates = {}
            if side in ('left', 'right'):
                updates['side'] = 'right' if side == 'left' else 'left'
            if anchor in ('w', 'e'):
                updates['anchor'] = 'e' if anchor == 'w' else 'w'
            if updates:
                child.pack_configure(**updates)
        if rtl and child.winfo_manager() == 'grid':
            options = child.grid_info()
            child.grid_configure(column=grid_columns - int(options['column']) - int(options.get('columnspan', 1)))
        if isinstance(child, (ttk.Label, ttk.Checkbutton, ttk.LabelFrame)) and rtl:
            if 'anchor' in child.keys():
                child.configure(anchor=tk.E)
            if 'justify' in child.keys():
                child.configure(justify=tk.RIGHT)
            if isinstance(child, ttk.LabelFrame):
                child.configure(labelanchor='ne')
        if isinstance(child, ttk.Treeview):
            for column in ('#0',) + tuple(child['columns']):
                # Leave paths and numeric values in their natural direction.
                if column not in ('path', 'size', 'time'):
                    child.column(column, anchor=tk.E if rtl else tk.W)
                    child.heading(column, anchor=tk.E if rtl else tk.W)
        apply_direction(child)


def configure_fonts(window):
    """Choose installed fonts with coverage for the selected writing system."""
    import tkinter.font as font
    from tkinter import ttk
    style = ttk.Style(window)
    # Wine may lack the native Windows visual-style service. Keep this an
    # explicit runtime override; native Windows retains its default theme.
    theme = os.environ.get('CDRIVE_CLEANER_THEME')
    if theme and theme in style.theme_names():
        style.theme_use(theme)
    available = set(font.families(window))
    preferred = {
        'ar': ('Segoe UI', 'Noto Naskh Arabic', 'Tahoma', 'Arial', 'DejaVu Sans'),
        'hi': ('Noto Sans Devanagari', 'Nirmala UI', 'Mangal'),
        'zh_CN': ('Noto Sans CJK SC', 'Microsoft YaHei', 'SimSun'),
    }.get(i18n.language, ('Segoe UI', 'Noto Sans', 'DejaVu Sans'))
    override = os.environ.get('CDRIVE_CLEANER_FONT')
    if override:
        preferred = (override,) + preferred
    family = next((name for name in preferred if name in available), None)
    if family:
        for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont',
                     'TkCaptionFont', 'TkSmallCaptionFont', 'TkIconFont', 'TkTooltipFont'):
            font.nametofont(name, root=window).configure(family=family, size=10)
        line_height = font.nametofont('TkDefaultFont', root=window).metrics('linespace')
        style.configure('Treeview', rowheight=line_height + 6)
