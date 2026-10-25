#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
C盘清理工具 - 安全高效地清理C盘不必要的文件
"""

import sys
import os
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from config import APP_NAME, VERSION
from cleaner_logic import CleanerLogic
from i18n import tr, i18n, apply_direction, display, configure_fonts
from backup_manager import BackupManagerWindow

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='cleaner.log'
)
logger = logging.getLogger('CCleaner')

class CleanerApp(tk.Tk):
    """基于tkinter的C盘清理工具主应用程序"""

    def __init__(self):
        super().__init__()
        configure_fonts(self)

        self.title(display(tr('C盘清理工具')))
        self.geometry("1000x760")
        self.minsize(850, 700)

        self.cleaner = CleanerLogic()
        self.scan_results = {}
        self.selected_items = []

        self.create_widgets()
        apply_direction(self)
        self.update_disk_info()

    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        language_frame = ttk.Frame(main_frame)
        language_frame.pack(fill=tk.X, pady=5)
        ttk.Label(language_frame, text=display(tr('Language'))).pack(side=tk.LEFT, padx=5)
        self.language_codes = list(i18n.catalogs)
        self.language_choice = ttk.Combobox(
            language_frame, state='readonly', width=24,
            values=[display(i18n.catalogs[code]['name']) for code in self.language_codes])
        self.language_choice.current(self.language_codes.index(i18n.language))
        self.language_choice.pack(side=tk.LEFT, padx=5)
        self.language_choice.bind('<<ComboboxSelected>>', self.change_language)

        # 系统信息区域
        info_frame = ttk.LabelFrame(main_frame, text=display(tr('系统信息')), padding="5")
        info_frame.pack(fill=tk.X, pady=5)

        self.disk_info_label = ttk.Label(info_frame, text=display(tr('C盘使用情况: 正在加载...')))
        self.disk_info_label.pack(anchor=tk.W)

        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)

        self.scan_button = ttk.Button(button_frame, text=display(tr('扫描系统')), command=self.start_scan)
        self.scan_button.grid(row=0, column=0, padx=5, pady=3, sticky="ew")

        self.clean_all_button = ttk.Button(button_frame, text=display(tr('一键清理')), command=self.start_clean_all)
        self.clean_all_button.grid(row=0, column=1, padx=5, pady=3, sticky="ew")

        self.clean_button = ttk.Button(button_frame, text=display(tr('清理选中项')), command=self.start_clean, state=tk.DISABLED)
        self.clean_button.grid(row=0, column=2, padx=5, pady=3, sticky="ew")

        self.select_all_button = ttk.Button(button_frame, text=display(tr('全选')), command=self.select_all_items, state=tk.DISABLED)
        self.select_all_button.grid(row=1, column=0, padx=5, pady=3, sticky="ew")

        self.deselect_all_button = ttk.Button(button_frame, text=display(tr('取消全选')), command=self.deselect_all_items, state=tk.DISABLED)
        self.deselect_all_button.grid(row=1, column=1, padx=5, pady=3, sticky="ew")

        for column in range(3):
            button_frame.columnconfigure(column, weight=1)

        # 进度条
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_frame.pack(fill=tk.X, pady=5)

        self.progress_bar = ttk.Progressbar(self.progress_frame, mode="indeterminate")
        self.progress_bar.pack(fill=tk.X)
        self.progress_bar.pack_forget()  # 初始隐藏

        self.status_label = ttk.Label(self.progress_frame, text=display(""))
        self.status_label.pack(anchor=tk.W)

        # 结果区域
        result_frame = ttk.LabelFrame(main_frame, text=display(tr('扫描结果')), padding="5")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 创建Treeview用于显示结果
        columns = ("name", "size", "path")
        self.result_tree = ttk.Treeview(result_frame, columns=columns, show="tree headings", height=6)

        # 设置列标题
        self.result_tree.heading("name", text=display(tr('项目')))
        self.result_tree.heading("size", text=display(tr('大小')))
        self.result_tree.heading("path", text=display(tr('路径')))

        # 设置列宽
        self.result_tree.column("name", width=200)
        self.result_tree.column("size", width=100)
        self.result_tree.column("path", width=400)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=scrollbar.set)

        # 放置Treeview和滚动条
        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 安全选项区域
        safety_frame = ttk.LabelFrame(main_frame, text=display(tr('安全选项')), padding="5")
        safety_frame.pack(fill=tk.X, pady=5)

        # 模拟模式选项
        simulate_frame = ttk.Frame(safety_frame)
        simulate_frame.pack(fill=tk.X, pady=2)

        self.simulate_var = tk.BooleanVar(value=False)  # 默认关闭模拟模式
        self.simulate_check = ttk.Checkbutton(simulate_frame, text=display(tr('模拟模式 (不实际删除文件)')),
                                             variable=self.simulate_var)
        self.simulate_check.pack(side=tk.LEFT)

        # 备份选项
        backup_frame = ttk.Frame(safety_frame)
        backup_frame.pack(fill=tk.X, pady=2)

        self.backup_var = tk.BooleanVar(value=True)
        self.backup_check = ttk.Checkbutton(backup_frame, text=display(tr('删除前备份文件')),
                                           variable=self.backup_var)
        self.backup_check.pack(side=tk.LEFT)

        self.backup_manager_button = ttk.Button(backup_frame, text=display(tr('备份管理')), command=self.open_backup_manager)
        self.backup_manager_button.pack(side=tk.LEFT, padx=10)

        # 备份目录选项
        backup_dir_frame = ttk.Frame(safety_frame)
        backup_dir_frame.pack(fill=tk.X, pady=2)

        ttk.Label(backup_dir_frame, text=display(tr('备份目录:'))).pack(side=tk.LEFT, padx=5)

        self.backup_dir_var = tk.StringVar(value=self.cleaner.backup_dir)
        backup_dir_entry = ttk.Entry(backup_dir_frame, textvariable=self.backup_dir_var, width=40)
        backup_dir_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        browse_button = ttk.Button(backup_dir_frame, text=display(tr('浏览...')), command=self.browse_backup_dir)
        browse_button.pack(side=tk.LEFT, padx=5)

    def change_language(self, event=None):
        code = self.language_codes[self.language_choice.current()]
        try:
            i18n.save_language(code)
        except OSError as exc:
            messagebox.showerror(tr('错误'), tr('Could not save language: {v0}', v0=exc), parent=self)
            self.language_choice.current(self.language_codes.index(i18n.language))
            return
        messagebox.showinfo(tr('Language'),
                            tr('Language saved. Restart the application to apply it.'), parent=self)

    def update_disk_info(self):
        """更新磁盘信息"""
        disk_info = self.cleaner.get_disk_info()
        self.disk_info_label.config(
            text=display(tr('C盘总空间: {v0:.2f} GB | 已用空间: {v1:.2f} GB ({v2}%) | 可用空间: {v3:.2f} GB', v0=disk_info['total'], v1=disk_info['used'], v2=disk_info['percent'], v3=disk_info['free']))
        )

    def start_scan(self):
        """开始扫描系统"""
        self.scan_button.config(state=tk.DISABLED)
        self.clean_button.config(state=tk.DISABLED)
        self.select_all_button.config(state=tk.DISABLED)
        self.deselect_all_button.config(state=tk.DISABLED)
        self.result_tree.delete(*self.result_tree.get_children())
        self.progress_bar.pack(fill=tk.X)
        self.progress_bar.start()
        self.status_label.config(text=display(tr('正在扫描系统，请稍候...')))

        # 使用after方法在后台执行扫描
        self.after(100, self.perform_scan)

    def perform_scan(self):
        """执行扫描操作"""
        try:
            self.scan_results = self.cleaner.scan_system()
            self.after(100, self.on_scan_finished)
        except Exception as e:
            logger.error(tr('扫描过程中出错: {v0}', v0=e))
            messagebox.showerror(tr('扫描错误'), tr('扫描过程中出错: {v0}', v0=e))
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self.scan_button.config(state=tk.NORMAL)

    def on_scan_finished(self):
        """扫描完成后的处理"""
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.scan_button.config(state=tk.NORMAL)

        if not any(self.scan_results.values()):
            self.status_label.config(text=display(tr('扫描完成，未发现可清理项目')))
            return

        # 计算总大小
        total_size = sum(item['size'] for category in self.scan_results.values() for item in category)
        self.status_label.config(text=display(tr('扫描完成，发现可释放空间: {v0}', v0=self.format_size(total_size))))

        # 填充结果树
        self.populate_results_tree()
        self.clean_button.config(state=tk.NORMAL)
        self.select_all_button.config(state=tk.NORMAL)
        self.deselect_all_button.config(state=tk.NORMAL)

        # 更新磁盘信息
        self.update_disk_info()

    def populate_results_tree(self):
        """填充结果树"""
        categories = {
            # 基本清理
            'temp': tr('临时文件'),
            'recycle': tr('回收站'),
            'cache': tr('浏览器缓存'),
            'logs': tr('系统日志'),
            'updates': tr('Windows更新缓存'),
            'thumbnails': tr('缩略图缓存'),

            # 扩展清理
            'prefetch': tr('预读取文件'),
            'old_windows': tr('旧Windows文件'),
            'error_reports': tr('错误报告'),
            'service_packs': tr('服务包备份'),
            'memory_dumps': tr('内存转储文件'),
            'font_cache': tr('字体缓存'),
            'disk_cleanup': tr('磁盘清理备份'),

            # 新增安全清理项
            'app_cache': tr('应用程序缓存'),
            'media_cache': tr('媒体播放器缓存'),
            'search_index': tr('搜索索引临时文件'),
            'backup_temp': tr('备份临时文件'),
            'update_temp': tr('更新临时文件'),
            'driver_backup': tr('驱动备份'),
            'app_crash': tr('应用程序崩溃转储'),
            'app_logs': tr('应用程序日志'),
            'recent_items': tr('最近使用的文件列表'),
            'notification': tr('Windows通知缓存'),
            'dns_cache': tr('DNS缓存'),
            'network_cache': tr('网络缓存'),
            'printer_temp': tr('打印机临时文件'),
            'device_temp': tr('设备临时文件'),
            'windows_defender': tr('Windows Defender缓存'),
            'store_cache': tr('Windows Store缓存'),
            'onedrive_cache': tr('OneDrive缓存'),

            # 新增用户请求的清理项
            'downloads': tr('下载文件夹(立即清理)'),
            'installer_cache': tr('安装程序缓存(30天前)'),
            'delivery_opt': tr('Windows传递优化缓存(立即清理)'),

            # 大文件扫描
            'large_files': tr('大文件 (>100MB)')
        }

        for category, items in self.scan_results.items():
            if not items:
                continue

            # 计算类别总大小
            category_size = sum(item['size'] for item in items)
            category_name = categories.get(category, category)

            # 添加类别节点
            category_id = self.result_tree.insert(
                "", "end", text=display(category_name),
                values=(display(category_name), self.format_size(category_size), "")
            )

            # 添加文件节点
            for item in items:
                file_name = os.path.basename(item['path'])

                # 大文件显示更多信息
                if category == 'large_files' and 'modified' in item and 'extension' in item:
                    # 对于大文件，显示文件名、大小、修改时间和文件类型
                    file_info = tr('{v0} [修改时间: {v1}] [类型: {v2}]', v0=file_name, v1=item['modified'], v2=item['extension'])
                    self.result_tree.insert(
                        category_id, "end", text=display(file_name),
                        values=(display(file_info), self.format_size(item['size']), item['path']),
                        tags=("item",)
                    )
                else:
                    # 对于普通文件，只显示文件名和大小
                    self.result_tree.insert(
                        category_id, "end", text=display(file_name),
                        values=(display(file_name), self.format_size(item['size']), item['path']),
                        tags=("item",)
                    )

        # 展开所有节点
        for item_id in self.result_tree.get_children():
            self.result_tree.item(item_id, open=True)

    def start_clean(self):
        """开始清理选中的项目"""
        # 获取选中的项目
        selected_ids = self.result_tree.selection()
        if not selected_ids:
            messagebox.showinfo(tr('提示'), tr('请先选择要清理的项目'))
            return

        # 收集选中的项目数据
        self.selected_items = []
        for item_id in selected_ids:
            # 检查是否是文件项目（不是类别）
            parent_id = self.result_tree.parent(item_id)
            if parent_id:  # 如果有父节点，说明是文件项目
                path = self.result_tree.item(item_id, "values")[2]
                # 在scan_results中查找对应的项目
                for category in self.scan_results.values():
                    for item in category:
                        if item['path'] == path:
                            self.selected_items.append(item)
                            break

        if not self.selected_items:
            messagebox.showinfo(tr('提示'), tr('请选择具体的文件或目录进行清理'))
            return

        # 确认对话框
        total_size = sum(item['size'] for item in self.selected_items)
        if self.simulate_var.get():
            message = tr('您选择了模拟模式，将会模拟清理 {v0} 个项目，总计 {v1}。', v0=len(self.selected_items), v1=self.format_size(total_size))
        else:
            message = tr('您确定要清理 {v0} 个项目，总计 {v1} 吗？\n此操作无法撤销！', v0=len(self.selected_items), v1=self.format_size(total_size))

        if not messagebox.askyesno(tr('确认清理'), message):
            return

        # 设置清理选项
        self.cleaner.set_options({
            'simulate': self.simulate_var.get(),
            'backup': self.backup_var.get(),
            'backup_dir': self.backup_dir_var.get()
        })

        # 开始清理
        self.scan_button.config(state=tk.DISABLED)
        self.clean_button.config(state=tk.DISABLED)
        self.select_all_button.config(state=tk.DISABLED)
        self.deselect_all_button.config(state=tk.DISABLED)
        self.progress_bar.pack(fill=tk.X)
        self.progress_bar.start()
        self.status_label.config(text=display(tr('正在清理文件，请稍候...')))

        # 使用after方法在后台执行清理
        self.after(100, self.perform_clean)

    def perform_clean(self):
        """执行清理操作"""
        try:
            results = self.cleaner.clean_selected(self.selected_items)
            self.after(100, lambda: self.on_clean_finished(results))
        except Exception as e:
            logger.error(tr('清理过程中出错: {v0}', v0=e))
            messagebox.showerror(tr('清理错误'), tr('清理过程中出错: {v0}', v0=e))
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self.scan_button.config(state=tk.NORMAL)
            self.clean_button.config(state=tk.NORMAL)
            self.clean_all_button.config(state=tk.NORMAL)

    def perform_clean_all(self):
        """执行一键清理操作"""
        try:
            # 先扫描系统
            self.scan_results = self.cleaner.scan_system()

            # 准备所有项目的列表
            all_items = []
            for category_items in self.scan_results.values():
                all_items.extend(category_items)

            # 如果没有可清理项目
            if not all_items:
                self.progress_bar.stop()
                self.progress_bar.pack_forget()
                self.scan_button.config(state=tk.NORMAL)
                self.clean_all_button.config(state=tk.NORMAL)
                self.status_label.config(text=display(tr('扫描完成，未发现可清理项目')))
                return

            # 显示清理进度
            total_size = sum(item['size'] for item in all_items)
            self.status_label.config(text=display(tr('正在清理 {v0} 个项目，总计 {v1}...', v0=len(all_items), v1=self.format_size(total_size))))

            # 执行清理
            results = self.cleaner.clean_selected(all_items)
            self.after(100, lambda: self.on_clean_all_finished(results))
        except Exception as e:
            logger.error(tr('一键清理过程中出错: {v0}', v0=e))
            messagebox.showerror(tr('清理错误'), tr('一键清理过程中出错: {v0}', v0=e))
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self.scan_button.config(state=tk.NORMAL)
            self.clean_all_button.config(state=tk.NORMAL)

    def on_clean_finished(self, results):
        """清理完成后的处理"""
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.scan_button.config(state=tk.NORMAL)
        self.clean_all_button.config(state=tk.NORMAL)

        freed_space = results.get('freed_space', 0)
        errors = results.get('errors', [])

        if self.simulate_var.get():
            message = tr('模拟清理完成，可释放空间: {v0}', v0=self.format_size(freed_space))
        else:
            message = tr('清理完成，已释放空间: {v0}', v0=self.format_size(freed_space))

        if errors:
            message += tr('，{v0} 个错误', v0=len(errors))

        self.status_label.config(text=display(message))

        # 如果有错误，显示错误日志
        if errors:
            error_details = "\n".join([f"{err['path']}: {tr(err['error'])}" for err in errors[:10]])
            if len(errors) > 10:
                error_details += tr('\n... 以及 {v0} 个其他错误', v0=len(errors) - 10)
            messagebox.showwarning(tr('清理错误'), tr('清理过程中发生 {v0} 个错误\n\n{v1}', v0=len(errors), v1=error_details))

        # 更新磁盘信息
        self.update_disk_info()

        # 重新扫描
        self.start_scan()

    def on_clean_all_finished(self, results):
        """一键清理完成后的处理"""
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.scan_button.config(state=tk.NORMAL)
        self.clean_all_button.config(state=tk.NORMAL)

        freed_space = results.get('freed_space', 0)
        errors = results.get('errors', [])

        if self.simulate_var.get():
            message = tr('模拟清理完成，可释放空间: {v0}', v0=self.format_size(freed_space))
        else:
            message = tr('一键清理完成，已释放空间: {v0}', v0=self.format_size(freed_space))

        if errors:
            message += tr('，{v0} 个错误', v0=len(errors))

        self.status_label.config(text=display(message))

        # 如果有错误，显示错误日志
        if errors:
            error_details = "\n".join([f"{err['path']}: {tr(err['error'])}" for err in errors[:10]])
            if len(errors) > 10:
                error_details += tr('\n... 以及 {v0} 个其他错误', v0=len(errors) - 10)
            messagebox.showwarning(tr('清理错误'), tr('清理过程中发生 {v0} 个错误\n\n{v1}', v0=len(errors), v1=error_details))

        # 显示清理结果
        messagebox.showinfo(tr('清理完成'), tr('一键清理完成\n\n已释放空间: {v0}\n错误数量: {v1}', v0=self.format_size(freed_space), v1=len(errors)))

        # 更新磁盘信息
        self.update_disk_info()

        # 重新扫描
        self.start_scan()

    @staticmethod
    def format_size(size_bytes):
        """格式化文件大小显示"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.2f} MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.2f} GB"

    def browse_backup_dir(self):
        """浏览选择备份目录"""
        backup_dir = filedialog.askdirectory(
            title=tr('选择备份目录'),
            initialdir=self.cleaner.backup_dir
        )

        if backup_dir:
            self.backup_dir_var.set(backup_dir)
            # 更新清理器的备份目录
            self.cleaner.set_options({'backup_dir': backup_dir})

    def open_backup_manager(self):
        """打开备份管理窗口"""
        BackupManagerWindow(self, self.cleaner)

    def select_all_items(self):
        """全选所有项目"""
        # 选中所有类别
        for category_id in self.result_tree.get_children():
            # 设置类别项为选中状态
            self.result_tree.item(category_id, open=True)  # 展开类别

            # 选中该类别下的所有文件
            for item_id in self.result_tree.get_children(category_id):
                self.result_tree.selection_add(item_id)

        # 更新清理按钮状态
        self.clean_button.config(state=tk.NORMAL)

    def deselect_all_items(self):
        """取消全选"""
        # 取消选中所有项目
        self.result_tree.selection_remove(self.result_tree.selection())

        # 更新清理按钮状态
        self.clean_button.config(state=tk.DISABLED)

    def start_clean_all(self):
        """一键清理所有项目"""
        # 确认对话框
        if not messagebox.askyesno(tr('确认清理'), tr('一键清理将清理所有可清理项目，确定要继续吗？')):
            return

        # 先扫描系统
        self.scan_button.config(state=tk.DISABLED)
        self.clean_all_button.config(state=tk.DISABLED)
        self.clean_button.config(state=tk.DISABLED)
        self.select_all_button.config(state=tk.DISABLED)
        self.deselect_all_button.config(state=tk.DISABLED)
        self.result_tree.delete(*self.result_tree.get_children())
        self.progress_bar.pack(fill=tk.X)
        self.progress_bar.start()
        self.status_label.config(text=display(tr('正在扫描系统，请稍候...')))

        # 设置清理选项
        self.cleaner.set_options({
            'simulate': self.simulate_var.get(),
            'backup': self.backup_var.get(),
            'backup_dir': self.backup_dir_var.get()
        })

        # 使用after方法在后台执行扫描和清理
        self.after(100, self.perform_clean_all)

def main():
    """应用程序入口点"""
    logger.info(tr('启动 {v0} v{v1}', v0=APP_NAME, v1=VERSION))

    app = CleanerApp()
    app.mainloop()

    logger.info(tr('{v0} 已退出', v0=APP_NAME))

if __name__ == "__main__":
    main()
