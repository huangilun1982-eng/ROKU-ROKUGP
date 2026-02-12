
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QWidget, QFormLayout, QDoubleSpinBox, QPushButton, 
                             QLabel, QGroupBox, QScrollArea, QFrame, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt

class SettingsDialog(QDialog):
    """
    自定義優化參數的設定對話框。
    """
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("⚙️ 優化參數設定 (Optimization Options)")
        self.resize(500, 600)
        self.setup_ui()
        self.load_values()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        
        # 1. 材質設定頁面
        self.tab_materials = QWidget()
        self.setup_materials_tab()
        self.tabs.addTab(self.tab_materials, "工件材質 (Materials)")
        
        # 2. 策略比例頁面
        self.tab_strategies = QWidget()
        self.setup_strategies_tab()
        self.tabs.addTab(self.tab_strategies, "循環比例 (IJK Ratios)")
        
        # 3. 其他限制頁面
        self.tab_limits = QWidget()
        self.setup_limits_tab()
        self.tabs.addTab(self.tab_limits, "基本限制 (Limits)")
        
        layout.addWidget(self.tabs)
        
        btn_layout = QHBoxLayout()
        
        self.btn_import = QPushButton("匯入參數")
        self.btn_import.clicked.connect(self.on_import_clicked)
        
        self.btn_export = QPushButton("匯出參數")
        self.btn_export.clicked.connect(self.on_export_clicked)
        
        self.btn_reset = QPushButton("重置預設")
        self.btn_reset.clicked.connect(self.on_reset_clicked)
        
        self.btn_save = QPushButton("儲存設定")
        self.btn_save.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        self.btn_save.clicked.connect(self.on_save_clicked)
        
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_import)
        btn_layout.addWidget(self.btn_export)
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        
        layout.addLayout(btn_layout)

    def setup_materials_tab(self):
        layout = QVBoxLayout(self.tab_materials)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.material_form = QFormLayout(scroll_content)
        
        self.mat_widgets = {} # {mat_key: {'Vc': spin, 'Fr': spin}}
        
        for key, data in self.config_manager.data['materials'].items():
            group = QGroupBox(f"{data.get('desc', key)}")
            g_layout = QFormLayout()
            
            vc_spin = QDoubleSpinBox()
            vc_spin.setRange(1, 500)
            vc_spin.setSuffix(" m/min")
            
            fr_spin = QDoubleSpinBox()
            fr_spin.setRange(0.001, 0.1)
            fr_spin.setDecimals(4)
            fr_spin.setSingleStep(0.001)
            
            g_layout.addRow("切削速度 (Vc):", vc_spin)
            g_layout.addRow("進給係數 (fr_factor):", fr_spin)
            group.setLayout(g_layout)
            
            self.material_form.addRow(group)
            self.mat_widgets[key] = {'Vc': vc_spin, 'Fr': fr_spin}
            
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def setup_strategies_tab(self):
        layout = QVBoxLayout(self.tab_strategies)
        self.strat_widgets = {} # {mode: {'I': spin, 'J': spin, 'K': spin}}
        
        labels = {
            'safety': '🔒 安全優先 (Safety - 小徑鑽頭)',
            'efficient': '⚡ 高效優先 (Efficient - 標準)',
            'deep_hole': '🕳️ 極深孔模式 (Deep Hole - L/D > 10)'
        }
        
        for mode, ratios in self.config_manager.data['ijk_strategies'].items():
            group = QGroupBox(labels.get(mode, mode))
            g_layout = QFormLayout()
            
            i_spin = QDoubleSpinBox(); i_spin.setRange(0.1, 3.0); i_spin.setDecimals(2)
            j_spin = QDoubleSpinBox(); j_spin.setRange(0.01, 1.0); j_spin.setDecimals(2)
            k_spin = QDoubleSpinBox(); k_spin.setRange(0.05, 2.0); k_spin.setDecimals(2)
            
            g_layout.addRow("I 比例 (對直徑倍率):", i_spin)
            g_layout.addRow("J 比例 (每次遞減量):", j_spin)
            g_layout.addRow("K 比例 (最小保留量):", k_spin)
            group.setLayout(g_layout)
            
            layout.addWidget(group)
            self.strat_widgets[mode] = {'I': i_spin, 'J': j_spin, 'K': k_spin}
        layout.addStretch()

    def setup_limits_tab(self):
        layout = QFormLayout(self.tab_limits)
        
        self.spin_max_rpm = QDoubleSpinBox()
        self.spin_max_rpm.setRange(1000, 100000)
        self.spin_max_rpm.setSingleStep(5000)
        self.spin_max_rpm.setSuffix(" RPM")
        
        self.spin_min_q = QDoubleSpinBox()
        self.spin_min_q.setRange(0.01, 1.0)
        self.spin_min_q.setDecimals(3)
        self.spin_min_q.setSuffix(" mm")
        
        layout.addRow("機台最大主軸轉速:", self.spin_max_rpm)
        layout.addRow("最小允許 Q 值 (標準啄鑽):", self.spin_min_q)

    def load_values(self):
        # 載入材質
        for key, widgets in self.mat_widgets.items():
            data = self.config_manager.data['materials'][key]
            widgets['Vc'].setValue(data['Vc'])
            widgets['Fr'].setValue(data['fr_factor'])
            
        # 載入策略
        for mode, widgets in self.strat_widgets.items():
            data = self.config_manager.data['ijk_strategies'][mode]
            widgets['I'].setValue(data['i_ratio'])
            widgets['J'].setValue(data['j_ratio'])
            widgets['K'].setValue(data['k_ratio'])
            
        # 載入限制
        self.spin_max_rpm.setValue(self.config_manager.get_limit('max_rpm'))
        self.spin_min_q.setValue(self.config_manager.get_limit('min_q'))

    def on_reset_clicked(self):
        reply = QMessageBox.question(self, "重置確認", "是否將所有切削參數恢復為官方預設值？", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.reset_to_defaults()
            self.load_values()

    def on_import_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "匯入優化參數", "", "JSON Files (*.json)")
        if file_path:
            if self.config_manager.import_config(file_path):
                self.load_values()
                QMessageBox.information(self, "匯入成功", "優化參數已從檔案載入並生效。")
            else:
                QMessageBox.warning(self, "匯入失敗", "無法從指定的檔案載入參數。")

    def on_export_clicked(self):
        # 匯出前先將目前 UI 數值同步回 data 結構但不一定存檔
        self.sync_ui_to_data()
        file_path, _ = QFileDialog.getSaveFileName(self, "匯出優化參數", "drill_config_export.json", "JSON Files (*.json)")
        if file_path:
            if self.config_manager.save_config(file_path):
                QMessageBox.information(self, "匯出成功", f"參數已成功儲存至:\n{file_path}")
            else:
                QMessageBox.warning(self, "匯出失敗", "無法儲存設定檔案。")

    def sync_ui_to_data(self):
        """將 UI 數值同步回 config_manager.data 結構中。"""
        # 讀取回資料結構
        for key, widgets in self.mat_widgets.items():
             self.config_manager.data['materials'][key]['Vc'] = widgets['Vc'].value()
             self.config_manager.data['materials'][key]['fr_factor'] = widgets['Fr'].value()
             
        for mode, widgets in self.strat_widgets.items():
             self.config_manager.data['ijk_strategies'][mode]['i_ratio'] = widgets['I'].value()
             self.config_manager.data['ijk_strategies'][mode]['j_ratio'] = widgets['J'].value()
             self.config_manager.data['ijk_strategies'][mode]['k_ratio'] = widgets['K'].value()
             
        self.config_manager.data['limits']['max_rpm'] = self.spin_max_rpm.value()
        self.config_manager.data['limits']['min_q'] = self.spin_min_q.value()

    def on_save_clicked(self):
        self.sync_ui_to_data()
        if self.config_manager.save_config():
            self.accept()
