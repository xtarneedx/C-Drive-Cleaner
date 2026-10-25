"""Read-only GUI smoke tests; never scan or delete real filesystem contents."""
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from i18n import i18n, display, tr
from main import CleanerApp
from backup_manager import BackupManagerWindow


class FakeCleaner:
    def __init__(self):
        self.backup_dir = '/tmp/اختبار/نسخ'
        self.max_backups = 5
        self.max_backup_size = 1024 * 1024 * 1024
        self.clean_called = False
        self.path = '/tmp/مستخدم/ملف.tmp'

    def get_disk_info(self):
        return dict(total=100, used=25, percent=25, free=75)

    def get_backup_info(self):
        return dict(backup_dir=self.backup_dir, backup_count=0, total_size=0, backups=[])

    def set_options(self, options):
        self.options = options

    def clean_selected(self, items):
        self.clean_called = True
        raise AssertionError('Deletion must never execute in this test')


@unittest.skipUnless(os.environ.get('DISPLAY') or os.name == 'nt', 'Requires a graphical display')
class UISmokeTests(unittest.TestCase):
    def test_all_languages_main_backup_and_cancelled_cleanup(self):
        previous = i18n.language
        self.addCleanup(setattr, i18n, 'language', previous)
        for code in i18n.catalogs:
            with self.subTest(language=code):
                i18n.language = code
                with patch('main.CleanerLogic', FakeCleaner):
                    app = CleanerApp()
                try:
                    app.update()
                    self.assertEqual(app.title(), display(tr('C盘清理工具')))
                    self.assertEqual(app.scan_button.cget('text'), display(tr('扫描系统')))
                    self.assertEqual(len(app.language_choice['values']), 7)
                    self.assertLess(app.simulate_check.winfo_rooty() + app.simulate_check.winfo_height(),
                                    app.winfo_rooty() + app.winfo_height())
                    self.assertEqual(int(app.scan_button.grid_info()['column']), 2 if code=='ar' else 0)
                    self.assertEqual(str(app.status_label.pack_info()['anchor']), 'e' if code=='ar' else 'w')
                    self.assertEqual(app.backup_dir_var.get(), app.cleaner.backup_dir)
                    app.scan_results = {'temp':[{'path':app.cleaner.path, 'size':2048}]}
                    app.on_scan_finished()
                    app.update()
                    category = app.result_tree.get_children()[0]
                    leaf = app.result_tree.get_children(category)[0]
                    self.assertEqual(app.result_tree.item(leaf, 'values')[2], app.cleaner.path)
                    self.assertEqual(app.result_tree.item(category, 'text'), display(tr('临时文件')))
                    app.result_tree.selection_set(leaf)
                    with patch('main.messagebox.askyesno', return_value=False) as confirm:
                        app.start_clean()
                        confirm.assert_called_once()
                        self.assertEqual(confirm.call_args.args[0], tr('确认清理'))
                    self.assertEqual(app.selected_items[0]['path'], app.cleaner.path)
                    self.assertFalse(app.cleaner.clean_called)
                    backup = BackupManagerWindow(app, app.cleaner)
                    try:
                        backup.update()
                        self.assertEqual(backup.title(), display(tr('备份管理')))
                        self.assertEqual(backup.backup_dir_entry.get(), app.cleaner.backup_dir)
                        self.assertEqual(backup.close_button.cget('text'), display(tr('关闭')))
                        with patch('backup_manager.messagebox.showinfo') as info:
                            backup.restore_backup()  # no selection: information only
                            info.assert_called_once_with(tr('提示'), tr('请先选择要恢复的备份'))
                    finally:
                        backup.destroy()
                finally:
                    app.destroy()

    def test_language_selector_saves_without_resetting_safety_settings(self):
        previous = i18n.language
        self.addCleanup(setattr, i18n, 'language', previous)
        i18n.language = 'en'
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(i18n, 'settings_path', Path(directory)/'settings.json'):
                with patch('main.CleanerLogic', FakeCleaner):
                    app = CleanerApp()
                try:
                    app.simulate_var.set(True)
                    app.language_choice.current(app.language_codes.index('ar'))
                    with patch('main.messagebox.showinfo'):
                        app.change_language()
                    self.assertTrue(app.simulate_var.get())
                    self.assertTrue(app.backup_var.get())
                    self.assertIn('"language": "ar"', i18n.settings_path.read_text())
                finally:
                    app.destroy()


if __name__ == '__main__':
    unittest.main()
