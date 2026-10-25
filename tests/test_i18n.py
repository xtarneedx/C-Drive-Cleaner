import ast
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from i18n import LOCALES, Translations, fields, display


class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings = Path(self.tmp.name) / 'settings.json'
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.t = Translations(settings_path=self.settings, system_locale='en_US')

    def test_all_seven_catalogs_are_complete(self):
        self.assertEqual(set(self.t.catalogs), {'ar', 'en', 'zh_CN', 'fr', 'es', 'hi', 'tr'})
        base = self.t.catalogs['en']['messages']
        for path in LOCALES.glob('*.json'):
            with self.subTest(locale=path.stem):
                messages = json.loads(path.read_text(encoding='utf-8'))['messages']
                self.assertEqual(set(base), set(messages))
                for key, value in messages.items():
                    self.assertEqual(fields(key), fields(value), (path.stem, key))
                    values = {field: 12.5 if spec else 'sample' for field, spec, _ in fields(key)}
                    self.assertIsInstance(value.format(**values), str)

    def test_ui_translation_keys_exist(self):
        for file in ('main.py', 'backup_manager.py'):
            tree = ast.parse((LOCALES.parent / file).read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == 'tr' and node.args and isinstance(node.args[0], ast.Constant)):
                    self.assertIn(node.args[0].value, self.t.catalogs['en']['messages'])

    def test_regional_locale_resolution(self):
        for code, expected in [('ar-LY','ar'), ('fr_CA','fr'), ('es_MX','es'),
                               ('hi_IN','hi'), ('tr_TR','tr'), ('zh_CN','zh_CN'),
                               ('de_DE','en'), ('zh_TW','en'), ('','en')]:
            self.assertEqual(self.t.resolve(code), expected)

    def test_language_save_is_used_after_restart_and_keeps_settings(self):
        self.settings.write_text('{"theme":"dark"}', encoding='utf-8')
        self.t.save_language('ar')
        restored = Translations(settings_path=self.settings, system_locale='fr_FR')
        self.assertEqual(restored.language, 'ar')
        self.assertTrue(restored.rtl)
        self.assertEqual(restored.settings['theme'], 'dark')
        self.assertEqual(self.t.language, 'en')  # apply on restart, preserve current UI

    def test_environment_override(self):
        self.t.save_language('ar')
        with patch.dict(os.environ, {'CDRIVE_CLEANER_LANGUAGE':'tr_TR'}):
            t = Translations(settings_path=self.settings, system_locale='fr_FR')
            self.assertEqual(t.language, 'tr')

    def test_missing_or_corrupt_settings_fall_back_to_system(self):
        self.settings.write_text('not-json', encoding='utf-8')
        t = Translations(settings_path=self.settings, system_locale='hi_IN')
        self.assertEqual(t.language, 'hi')

    def test_missing_or_invalid_translation_falls_back_to_english(self):
        directory = Path(self.tmp.name) / 'locales'
        directory.mkdir()
        for code in ('en', 'ar'):
            data = json.loads((LOCALES / (code + '.json')).read_text(encoding='utf-8'))
            if code == 'ar':
                data['messages'].pop('扫描系统')
                data['messages']['备份数量: {v0}'] = 'invalid {missing}'
            (directory / (code + '.json')).write_text(json.dumps(data), encoding='utf-8')
        with self.assertLogs('i18n', level='WARNING'):
            t = Translations(directory, self.settings, 'ar')
        self.assertEqual(t.translate('扫描系统'), 'Scan system')
        self.assertEqual(t.translate('备份数量: {v0}', v0=4), 'Backup count: 4')

    def test_arabic_presentation_does_not_modify_logical_text(self):
        self.t.language = 'ar'
        logical = self.t.translate('备份目录: {v0}', v0=r'C:\Users\مستخدم\نسخة')
        visual = display(logical)
        self.assertNotEqual(visual, logical)
        self.assertIn(r'C:\Users\مستخدم\نسخة', logical)
        self.assertEqual(display('C:\\Windows\\Temp'), 'C:\\Windows\\Temp')
        self.assertEqual(display('العربية\nالعربية').count('\n'), 1)

    def test_failed_atomic_save_preserves_previous_preferences(self):
        self.t.save_language('en')
        before = self.settings.read_bytes()
        with patch('i18n.os.replace', side_effect=PermissionError('read only')):
            with self.assertRaises(PermissionError):
                self.t.save_language('ar')
        self.assertEqual(self.settings.read_bytes(), before)
        self.assertEqual(list(self.settings.parent.iterdir()), [self.settings])

    def test_new_language_can_be_discovered_without_code_changes(self):
        directory = Path(self.tmp.name) / 'locales'
        directory.mkdir()
        (directory/'en.json').write_bytes((LOCALES/'en.json').read_bytes())
        (directory/'de.json').write_text(json.dumps({
            'name':'Deutsch', 'direction':'ltr', 'messages':{'扫描系统':'System scannen'}}), encoding='utf-8')
        t = Translations(directory, self.settings, 'de_DE')
        self.assertEqual(t.language, 'de')
        self.assertEqual(t.translate('扫描系统'), 'System scannen')
        self.assertEqual(t.translate('大小'), 'Size')


if __name__ == '__main__':
    unittest.main()
