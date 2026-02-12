import os
import sys
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QListWidget, QFileDialog, QGroupBox, 
                             QDoubleSpinBox, QFormLayout, QMessageBox, QSplitter, QComboBox, QTextEdit)
from PyQt6.QtCore import Qt

from nc_parser import RokuNCParser
from ui_components import DrillingPlot, ParamTable
from analysis_engine import DrillingAnalysisEngine

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ROKU-ROKU G66 參數編輯器 (微細孔專用)")
        self.resize(1200, 750)
        
        self.parser = RokuNCParser()
        self.analysis_engine = DrillingAnalysisEngine()
        self.current_file = None
        self.current_tool_index = -1
        self.parsed_data = []
        
        self.setup_ui()
        
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # --- Left ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        self.btn_load = QPushButton("讀取 NC 檔案")
        self.btn_load.clicked.connect(self.load_file)
        left_layout.addWidget(self.btn_load)
        
        self.btn_close = QPushButton("關閉檔案")
        self.btn_close.clicked.connect(self.close_file)
        self.btn_close.setEnabled(False)
        self.btn_close.setStyleSheet("background-color: #dc3545; color: white;")
        left_layout.addWidget(self.btn_close)
        
        self.lbl_file = QLabel("尚未載入檔案")
        left_layout.addWidget(self.lbl_file)
        
        # Vertical Splitter for List and Preview
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Tool List Container
        container_list = QWidget()
        layout_list = QVBoxLayout(container_list)
        layout_list.setContentsMargins(0, 0, 0, 0)
        layout_list.addWidget(QLabel("偵測到的刀具清單:"))
        
        self.tool_list = QListWidget()
        self.tool_list.currentRowChanged.connect(self.on_tool_selected)
        layout_list.addWidget(self.tool_list)
        left_splitter.addWidget(container_list)
        
        # NC Preview Container
        container_preview = QWidget()
        layout_preview = QVBoxLayout(container_preview)
        layout_preview.setContentsMargins(0, 0, 0, 0)
        layout_preview.addWidget(QLabel("NC 預覽 (變更項目標示為紅色):"))
        
        self.txt_nc_preview = QTextEdit()
        self.txt_nc_preview.setReadOnly(True)
        self.txt_nc_preview.setStyleSheet("background-color: #ffffff; font-family: Consolas, monospace; font-size: 11px;")
        layout_preview.addWidget(self.txt_nc_preview)
        left_splitter.addWidget(container_preview)
        
        left_splitter.setSizes([400, 200])
        left_layout.addWidget(left_splitter)
        splitter.addWidget(left_panel)
        
        # --- Center ---
        center_panel = QWidget()
        center_panel.setFixedWidth(420)
        center_layout = QVBoxLayout(center_panel)
        
        # Visual Group
        grp_visual = QGroupBox("視覺化與素材設定")
        grp_visual.setStyleSheet("QGroupBox { font-weight: bold; color: #0056b3; }")
        form_visual = QFormLayout()
        form_visual.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        
        origin_layout = QHBoxLayout()
        origin_layout.setSpacing(5)
        self.combo_origin_dir = QComboBox()
        self.combo_origin_dir.addItems(["加工表面上方", "加工表面下方"])
        self.combo_origin_dir.currentIndexChanged.connect(self.update_visualization)
        self.combo_origin_dir.setFixedWidth(110)
        
        self.spin_origin_dist = QDoubleSpinBox()
        self.spin_origin_dist.setRange(0, 9999)
        self.spin_origin_dist.setDecimals(3)
        self.spin_origin_dist.setValue(0.000)
        self.spin_origin_dist.setMaximumWidth(100)
        self.spin_origin_dist.valueChanged.connect(self.update_visualization)
        
        origin_layout.addWidget(self.combo_origin_dir)
        origin_layout.addWidget(self.spin_origin_dist)
        origin_layout.addStretch() # 推向左側
        form_visual.addRow("座標原點位置 (相對加工表面):", origin_layout)
        
        self.spin_thickness = QDoubleSpinBox()
        self.spin_thickness.setRange(0, 9999)
        self.spin_thickness.setDecimals(3)
        self.spin_thickness.setValue(1.000)
        self.spin_thickness.setMaximumWidth(120)
        self.spin_thickness.valueChanged.connect(self.update_visualization)
        form_visual.addRow("素材目標厚度:", self.spin_thickness)

        self.spin_tool_dia = QDoubleSpinBox()
        self.spin_tool_dia.setRange(0.0, 100)
        self.spin_tool_dia.setDecimals(3)
        self.spin_tool_dia.setValue(0.100)
        self.spin_tool_dia.setMaximumWidth(120)
        self.spin_tool_dia.valueChanged.connect(self.on_tool_dia_changed)
        form_visual.addRow("刀具直徑:", self.spin_tool_dia)
        
        self.spin_tip_angle = QDoubleSpinBox()
        self.spin_tip_angle.setRange(1, 180)
        self.spin_tip_angle.setDecimals(1)
        self.spin_tip_angle.setValue(118.0)
        self.spin_tip_angle.setMaximumWidth(120)
        self.spin_tip_angle.valueChanged.connect(self.update_visualization)
        form_visual.addRow("鑽頭尖角 (°):", self.spin_tip_angle)
        
        self.spin_spot_dia = QDoubleSpinBox()
        self.spin_spot_dia.setRange(0, 100)
        self.spin_spot_dia.setDecimals(3)
        self.spin_spot_dia.setValue(0.000)
        self.spin_spot_dia.setMaximumWidth(120)
        self.spin_spot_dia.valueChanged.connect(self.update_visualization)
        form_visual.addRow("定點孔直徑 (90°):", self.spin_spot_dia)
        
        self.spin_exit_chamfer = QDoubleSpinBox()
        self.spin_exit_chamfer.setRange(0, 100)
        self.spin_exit_chamfer.setDecimals(3)
        self.spin_exit_chamfer.setValue(0.000)
        self.spin_exit_chamfer.setMaximumWidth(120)
        self.spin_exit_chamfer.valueChanged.connect(self.update_visualization)
        form_visual.addRow("出孔預倒角直徑 (Exit Chamfer):", self.spin_exit_chamfer)
        
        grp_visual.setLayout(form_visual)
        center_layout.addWidget(grp_visual)
        
        # NC Group
        grp_nc = QGroupBox("程式參數")
        grp_nc.setStyleSheet("QGroupBox { font-weight: bold; color: #B00; }")
        nc_layout = QVBoxLayout()
        
        self.lbl_cycle_type = QLabel("")
        self.lbl_cycle_type.setStyleSheet("color: #0066cc; font-weight: bold;")
        nc_layout.addWidget(self.lbl_cycle_type)
        
        self.combo_cycle = QComboBox()
        self.combo_cycle.addItems(["G83 標準 (Q - Constant Peck)", "G83 進階 (I/J/K - Variable Peck)"])
        self.combo_cycle.currentIndexChanged.connect(self.on_cycle_type_changed)
        self.combo_cycle.setVisible(False)
        nc_layout.addWidget(self.combo_cycle)
        
        form_static = QFormLayout()
        form_static.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        
        self.spin_r = QDoubleSpinBox()
        self.spin_r.setRange(-9999, 9999)
        self.spin_r.setDecimals(4)
        self.spin_r.setSingleStep(0.1)
        self.spin_r.setMaximumWidth(120)
        self.spin_r.valueChanged.connect(self.on_param_changed)
        form_static.addRow("R (安全點 Safe Z):", self.spin_r)
        
        self.spin_z = QDoubleSpinBox()
        self.spin_z.setRange(-9999, 9999)
        self.spin_z.setDecimals(4)
        self.spin_z.setSingleStep(0.1)
        self.spin_z.setMaximumWidth(120)
        self.spin_z.valueChanged.connect(self.on_param_changed)
        form_static.addRow("Z (孔底深度 Bottom):", self.spin_z)
        
        self.spin_s = QDoubleSpinBox()
        self.spin_s.setRange(-9999, 9999)
        self.spin_s.setDecimals(4)
        self.spin_s.setMaximumWidth(120)
        self.spin_s.valueChanged.connect(self.on_param_changed)
        form_static.addRow("S (接近點 Approach Z - G66):", self.spin_s)
        
        self.spin_t = QDoubleSpinBox()
        self.spin_t.setRange(0, 999)
        self.spin_t.setDecimals(3)
        self.spin_t.setMaximumWidth(120)
        self.spin_t.valueChanged.connect(self.on_param_changed)
        form_static.addRow("T (孔底暫停 Dwell Time - G66):", self.spin_t)
        
        self.spin_q = QDoubleSpinBox()
        self.spin_q.setRange(0.0, 100)
        self.spin_q.setDecimals(4)
        self.spin_q.setValue(0.0)
        self.spin_q.setMaximumWidth(120)
        self.spin_q.valueChanged.connect(self.on_q_changed)
        self.lbl_q = QLabel("Q (啄鑽深度 - Standard):")
        form_static.addRow(self.lbl_q, self.spin_q)
        
        self.spin_g83_i = QDoubleSpinBox()
        self.spin_g83_i.setRange(0.0, 100)
        self.spin_g83_i.setDecimals(4)
        self.spin_g83_i.setMaximumWidth(120)
        self.spin_g83_i.valueChanged.connect(self.on_q_changed)
        self.lbl_g83_i = QLabel("I (初始深度 Initial):")
        form_static.addRow(self.lbl_g83_i, self.spin_g83_i)
        
        self.spin_g83_j = QDoubleSpinBox()
        self.spin_g83_j.setRange(0.000, 100)
        self.spin_g83_j.setDecimals(4)
        self.spin_g83_j.setMaximumWidth(120)
        self.spin_g83_j.valueChanged.connect(self.on_q_changed)
        self.lbl_g83_j = QLabel("J (遞減量 Reduce):")
        form_static.addRow(self.lbl_g83_j, self.spin_g83_j)
        
        self.spin_g83_k = QDoubleSpinBox()
        self.spin_g83_k.setRange(0.0, 100)
        self.spin_g83_k.setDecimals(4)
        self.spin_g83_k.setMaximumWidth(120)
        self.spin_g83_k.valueChanged.connect(self.on_q_changed)
        self.lbl_g83_k = QLabel("K (最小深度 Min):")
        form_static.addRow(self.lbl_g83_k, self.spin_g83_k)

        self.spin_f = QDoubleSpinBox()
        self.spin_f.setRange(0, 99999)
        self.spin_f.setDecimals(1)
        self.spin_f.setValue(0.0)
        self.spin_f.setMaximumWidth(120)
        self.spin_f.valueChanged.connect(self.on_param_changed)
        form_static.addRow("F (進給速度 - G83):", self.spin_f)
        
        nc_layout.addLayout(form_static)
        
        # Machine Settings (Hidden)
        form_machine = QFormLayout()
        self.spin_g0_speed = QDoubleSpinBox()
        self.spin_g0_speed.setRange(100, 40000)
        self.spin_g0_speed.setValue(5000)
        self.spin_g0_speed.setSuffix(" mm/min")
        self.spin_g0_speed.valueChanged.connect(self.on_param_changed)
        self.lbl_g0_speed = QLabel("機台快速位移速度 (G0):")
        form_machine.addRow(self.lbl_g0_speed, self.spin_g0_speed)
        self.lbl_g0_speed.setVisible(False)
        self.spin_g0_speed.setVisible(False)
        nc_layout.addLayout(form_machine)

        # Efficiency Analysis
        self.grp_efficiency = QGroupBox("加工效率分析")
        self.grp_efficiency.setStyleSheet("""
            QGroupBox { border: 1px solid #ddd; border-radius: 4px; margin-top: 1.5em; padding-top: 5px; color: #333; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)
        eff_layout = QVBoxLayout()
        self.lbl_eff_pecks = QLabel("跳數變化: --")
        self.lbl_eff_pecks.setStyleSheet("font-size: 13px; color: #666;")
        self.lbl_eff_time = QLabel("效率提升: -- %")
        self.lbl_eff_time.setStyleSheet("font-size: 15px; font-weight: bold; color: #2e7d32;")
        eff_layout.addWidget(self.lbl_eff_pecks)
        eff_layout.addWidget(self.lbl_eff_time)
        self.grp_efficiency.setLayout(eff_layout)
        self.grp_efficiency.setVisible(False)
        nc_layout.addWidget(self.grp_efficiency)
        
        self.lbl_table_items = QLabel("循環參數組 (I, J, K):")
        nc_layout.addWidget(self.lbl_table_items)
        self.table_ijk = ParamTable()
        self.table_ijk.dataChangedSignal.connect(self.on_param_changed)
        self.table_ijk.cellClicked.connect(self.on_table_row_clicked)
        nc_layout.addWidget(self.table_ijk)
        
        self.btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("+ 新增階段")
        self.btn_add.clicked.connect(self.table_ijk.add_row)
        self.btn_remove = QPushButton("- 移除階段")
        self.btn_remove.clicked.connect(self.table_ijk.remove_row)
        self.btn_layout.addWidget(self.btn_add)
        self.btn_layout.addWidget(self.btn_remove)
        nc_layout.addLayout(self.btn_layout)
        
        grp_nc.setLayout(nc_layout)
        center_layout.addWidget(grp_nc)
        
        self.btn_save = QPushButton("另存新檔 (Save As)")
        self.btn_save.clicked.connect(self.save_file_as)
        self.btn_save.setStyleSheet("background-color: #28a745; color: white; height: 40px; font-weight: bold; font-size: 14px;")
        center_layout.addWidget(self.btn_save)
        
        splitter.addWidget(center_panel)
        
        # --- Right ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.plot_widget = DrillingPlot()
        self.plot_widget.peckSelected.connect(self.on_plot_peck_selected)
        right_layout.addWidget(self.plot_widget)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([200, 420, 600])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 0) # 中心區域固定
        splitter.setStretchFactor(2, 1) # 由右側圖表區吸收所有拉伸空間

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "開啟 NC 檔案", "", "NC Files (*.nc *.tap *.txt)")
        if not path: return
        try:
            self.parsed_data = self.parser.parse_file(path)
            self.current_file = path
            self.lbl_file.setText(os.path.basename(path))
            self.tool_list.clear()
            for item in self.parsed_data:
                label = f"{item['tool_id']} (行 {item['line_index'] + 1})"
                self.tool_list.addItem(label)
            if self.parsed_data:
                self.tool_list.setCurrentRow(0)
                self.btn_close.setEnabled(True)
            else:
                QMessageBox.warning(self, "提示", "檔案中未發現 G66 P9131 或 G83 循環。")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"無法讀取檔案: {str(e)}")

    def close_file(self):
        self.parsed_data, self.current_file, self.current_tool_index = [], None, -1
        self.parser = RokuNCParser()
        self.tool_list.clear()
        self.txt_nc_preview.clear()
        self.lbl_file.setText("尚未載入檔案")
        self.lbl_cycle_type.setText("")
        self.btn_close.setEnabled(False)
        self.spin_r.blockSignals(True); self.spin_z.blockSignals(True)
        self.spin_r.setValue(0.0); self.spin_z.setValue(0.0); self.spin_s.setValue(0.0)
        self.spin_t.setValue(0.0); self.spin_q.setValue(0.0); self.spin_f.setValue(0.0)
        self.spin_g83_i.setValue(0.0); self.spin_g83_j.setValue(0.0); self.spin_g83_k.setValue(0.0)
        self.spin_r.blockSignals(False); self.spin_z.blockSignals(False)
        self.spin_q.setEnabled(False); self.spin_f.setEnabled(False)
        self.lbl_q.setVisible(False); self.spin_q.setVisible(False)
        self.lbl_g83_i.setVisible(False); self.spin_g83_i.setVisible(False)
        self.combo_cycle.setVisible(False); self.table_ijk.setRowCount(0)
        self.update_visualization()

    def on_tool_selected(self, row):
        if row < 0 or row >= len(self.parsed_data): return
        self.current_tool_index = row
        data = self.parsed_data[row]
        static, dynamic, cycle_type = data['static_params'], data['dynamic_params'], data.get('cycle_type', 'G66')
        self.lbl_cycle_type.setText(f"⚙ 循環類型: {cycle_type} " + ("深孔鑽" if cycle_type == 'G83' else "P9131"))
        
        # --- 全面阻擋訊號以防止初始化過程中的資料競爭 ---
        controls = [
            self.spin_r, self.spin_z, self.spin_s, self.spin_t, self.spin_q, self.spin_f,
            self.spin_g83_i, self.spin_g83_j, self.spin_g83_k, self.combo_cycle,
            self.spin_tool_dia, self.spin_spot_dia, self.spin_exit_chamfer,
            self.spin_tip_angle, self.spin_origin_dist, self.combo_origin_dir, self.spin_thickness
        ]
        for ctrl in controls: ctrl.blockSignals(True)
        
        # 設定基礎參數
        self.spin_r.setValue(static.get('R', 0.0))
        self.spin_z.setValue(static.get('Z', 0.0))
        
        is_fixed = (cycle_type == 'G83')
        self.combo_cycle.setVisible(is_fixed)
        
        if is_fixed:
            use_ijk = data.get('use_ijk_mode', False)
            self.combo_cycle.setCurrentIndex(1 if use_ijk else 0)
            self.spin_s.setEnabled(False); self.spin_t.setEnabled(False); self.spin_f.setEnabled(True)
            self.spin_f.setValue(static.get('F') or 0.0)
            
            self.spin_q.setVisible(not use_ijk); self.lbl_q.setVisible(not use_ijk)
            self.spin_q.setValue(static.get('Q') or 0.0)
            
            self.spin_g83_i.setVisible(use_ijk); self.lbl_g83_i.setVisible(use_ijk)
            self.spin_g83_j.setVisible(use_ijk); self.lbl_g83_j.setVisible(use_ijk)
            self.spin_g83_k.setVisible(use_ijk); self.lbl_g83_k.setVisible(use_ijk)
            self.spin_g83_i.setValue(static.get('I') or 0.0)
            self.spin_g83_j.setValue(static.get('J') or 0.0)
            self.spin_g83_k.setValue(static.get('K') or 0.0)
            self.table_ijk.setEnabled(False)
            self.lbl_table_items.setText("鑽孔階段分解預覽 (計算結果):")
            self.btn_add.setVisible(False); self.btn_remove.setVisible(False)
        else:
            self.spin_s.setEnabled(True); self.spin_t.setEnabled(True); self.spin_f.setEnabled(False)
            self.spin_s.setValue(static.get('S') or 0.0)
            self.spin_t.setValue(static.get('T') or 0.0)
            self.table_ijk.setEnabled(True)
            self.table_ijk.load_data(dynamic)
            self.lbl_table_items.setText("循環參數組 (I, J, K):")
            self.btn_add.setVisible(True); self.btn_remove.setVisible(True)

        self.table_ijk.update_headers(cycle_type)

        # 刀具直徑處理
        detected_dia = data.get('detected_diameter')
        if detected_dia is not None and detected_dia > 0:
            self.spin_tool_dia.setValue(detected_dia)
        
        # --- 解除訊號阻擋 ---
        for ctrl in controls: ctrl.blockSignals(False)
        
        # --- 正常更新視覺效果與預估分析 ---
        if is_fixed:
            # G83 模式：觸發 Q 變更邏輯以生成啄鑽清單並繪圖
            self.on_q_changed() 
        else:
            # G66 模式：直接更新繪圖與表格
            self.table_ijk.load_data(dynamic)
            self.update_visualization()
            
        self.txt_nc_preview.setHtml(self.parser.generate_html(self.current_tool_index))

    def on_param_changed(self):
        if self.current_tool_index == -1: return
        self.update_visualization(); self.update_internal_data()

    def on_tool_dia_changed(self):
        if self.current_tool_index == -1: return
        data = self.parsed_data[self.current_tool_index]
        if data.get('cycle_type') == 'G83':
            # 如果目前是 0 值，自動填入預設建議值
            use_ijk = (self.combo_cycle.currentIndex() == 1)
            dia = self.spin_tool_dia.value()
            if dia > 1e-6:
                from analysis_engine import DrillingAnalysisEngine
                i, j, k = DrillingAnalysisEngine.get_default_ijk(dia)
                if use_ijk:
                    if abs(self.spin_g83_i.value()) < 1e-6:
                        self.spin_g83_i.blockSignals(True); self.spin_g83_i.setValue(i); self.spin_g83_i.blockSignals(False)
                        self.spin_g83_j.blockSignals(True); self.spin_g83_j.setValue(j); self.spin_g83_j.blockSignals(False)
                        self.spin_g83_k.blockSignals(True); self.spin_g83_k.setValue(k); self.spin_g83_k.blockSignals(False)
                else:
                    if abs(self.spin_q.value()) < 1e-6:
                        self.spin_q.blockSignals(True); self.spin_q.setValue(i); self.spin_q.blockSignals(False)
        self.update_visualization()

    def on_cycle_type_changed(self):
        if self.current_tool_index == -1: return
        use_ijk = (self.combo_cycle.currentIndex() == 1)
        self.parsed_data[self.current_tool_index]['use_ijk_mode'] = use_ijk
        
        # 同步 UI 輸入項可見性
        self.spin_q.setVisible(not use_ijk); self.lbl_q.setVisible(not use_ijk)
        self.spin_g83_i.setVisible(use_ijk); self.lbl_g83_i.setVisible(use_ijk)
        self.spin_g83_j.setVisible(use_ijk); self.lbl_g83_j.setVisible(use_ijk)
        self.spin_g83_k.setVisible(use_ijk); self.lbl_g83_k.setVisible(use_ijk)
        
        # 如果切換後值為 0，嘗試提供預設值
        if use_ijk and abs(self.spin_g83_i.value()) < 1e-6:
            dia = self.spin_tool_dia.value()
            if dia > 1e-6:
                from analysis_engine import DrillingAnalysisEngine
                i, j, k = DrillingAnalysisEngine.get_default_ijk(dia)
                self.spin_g83_i.blockSignals(True); self.spin_g83_i.setValue(i); self.spin_g83_i.blockSignals(False)
                self.spin_g83_j.blockSignals(True); self.spin_g83_j.setValue(j); self.spin_g83_j.blockSignals(False)
                self.spin_g83_k.blockSignals(True); self.spin_g83_k.setValue(k); self.spin_g83_k.blockSignals(False)
        elif not use_ijk and abs(self.spin_q.value()) < 1e-6:
            dia = self.spin_tool_dia.value()
            if dia > 1e-6:
                from analysis_engine import DrillingAnalysisEngine
                i, _, _ = DrillingAnalysisEngine.get_default_ijk(dia)
                self.spin_q.blockSignals(True); self.spin_q.setValue(i); self.spin_q.blockSignals(False)

        # 更新標籤與標頭
        self.table_ijk.update_headers('G83')
        self.lbl_table_items.setText("鑽孔階段分解預覽 (計算結果):")
        self.btn_add.setVisible(False); self.btn_remove.setVisible(False)
        self.on_q_changed()

    def on_q_changed(self):
        if self.current_tool_index == -1: return
        data = self.parsed_data[self.current_tool_index]
        if data.get('cycle_type') != 'G83': return
        params = {'R': self.spin_r.value(), 'Z': self.spin_z.value(), 'Q': self.spin_q.value(),
                  'I': self.spin_g83_i.value(), 'J': self.spin_g83_j.value(), 'K': self.spin_g83_k.value()}
        new_ijk = self.parser._g83_to_ijk(params, 'G83', data.get('use_ijk_mode', False))
        self.table_ijk.blockSignals(True); self.table_ijk.load_data(new_ijk); self.table_ijk.blockSignals(False)
        self.update_internal_data(); self.update_visualization()

    def on_table_row_clicked(self, row, col):
        if self.current_tool_index == -1: return
        self.plot_widget.update_plot(self.spin_r.value(), self.spin_z.value(), self.table_ijk.get_data(), self.get_visual_params(), highlight_peck_idx=row)

    def on_plot_peck_selected(self, peck_idx):
        if self.current_tool_index == -1: return
        self.table_ijk.blockSignals(True); self.table_ijk.selectRow(peck_idx); self.table_ijk.blockSignals(False)

    def get_visual_params(self):
        is_below = (self.combo_origin_dir.currentIndex() == 1)
        shift = -self.spin_origin_dist.value() if is_below else self.spin_origin_dist.value()
        cycle_type = self.parsed_data[self.current_tool_index].get('cycle_type', 'G66') if self.current_tool_index != -1 else 'G66'
        return {
            'origin_z_shift': shift, 'thickness': self.spin_thickness.value(), 'tool_dia': self.spin_tool_dia.value(),
            'spot_dia': self.spin_spot_dia.value(), 'exit_chamfer_dia': self.spin_exit_chamfer.value(), 'tip_angle': self.spin_tip_angle.value(),
            'use_ijk_mode': self.parsed_data[self.current_tool_index].get('use_ijk_mode', False) if self.current_tool_index != -1 else False,
            'cycle_type': cycle_type,
            'R': self.spin_r.value(), 'S': self.spin_s.value(), 'Z': self.spin_z.value()
        }

    def update_internal_data(self):
        new_static = {'R': self.spin_r.value(), 'Z': self.spin_z.value(), 'S': self.spin_s.value(), 'T': self.spin_t.value(),
                      'F': self.spin_f.value(), 'Q': self.spin_q.value(), 'I': self.spin_g83_i.value(), 'J': self.spin_g83_j.value(), 'K': self.spin_g83_k.value()}
        self.parser.update_g66_line(self.current_tool_index, new_static, self.table_ijk.get_data())
        self.txt_nc_preview.setHtml(self.parser.generate_html(self.current_tool_index))

    def update_visualization(self):
        r_val, z_val, ijk = self.spin_r.value(), self.spin_z.value(), self.table_ijk.get_data()
        self.plot_widget.update_plot(r_val, z_val, ijk, self.get_visual_params())
        
        if self.current_tool_index != -1:
            data = self.parsed_data[self.current_tool_index]
            if data.get('cycle_type') == 'G83':
                curr_p = {'ijk_list': ijk, 'feedrate': self.spin_f.value(), 'r_point': r_val, 'is_ijk_mode': data.get('use_ijk_mode', False)}
                init_s = data.get('initial_static', {})
                init_p = {'ijk_list': data.get('initial_dynamic', []), 'feedrate': init_s.get('F', 0.0), 'r_point': init_s.get('R', r_val), 'is_ijk_mode': data.get('initial_use_ijk_mode', False)}
                res = self.analysis_engine.compare_efficiency(curr_p, init_p, self.spin_g0_speed.value())
                self.grp_efficiency.setVisible(True)
                peck_t = f"跳數變化: {res['init_pecks']} -> {res['curr_pecks']}"
                if res['curr_pecks'] < res['init_pecks']: peck_t += f" (減少 {res['init_pecks'] - res['curr_pecks']} 次)"
                elif res['curr_pecks'] > res['init_pecks']: peck_t += f" (增加 {res['curr_pecks'] - res['init_pecks']} 次)"
                self.lbl_eff_pecks.setText(peck_t)
                save = res['save_pct']
                if save > 0.001: self.lbl_eff_time.setText(f"預估效率提升: {save:.1f} %"); self.lbl_eff_time.setStyleSheet("font-size: 15px; font-weight: bold; color: #28a745;")
                elif save < -0.001: self.lbl_eff_time.setText(f"效率降低: {abs(save):.1f} %"); self.lbl_eff_time.setStyleSheet("font-size: 15px; font-weight: bold; color: #d9534f;")
                else: self.lbl_eff_time.setText("預估效率不變: 0.0 %"); self.lbl_eff_time.setStyleSheet("font-size: 15px; font-weight: bold; color: #666;")
            else: self.grp_efficiency.setVisible(False)
        else: self.grp_efficiency.setVisible(False)

    def save_file_as(self):
        if not self.parsed_data: return
        path, _ = QFileDialog.getSaveFileName(self, "另存新檔", self.current_file if self.current_file else "modified.nc", "NC Files (*.nc *.tap *.txt)")
        if not path: return
        try:
            self.parser.save_file(path); self.current_file = path; self.lbl_file.setText(os.path.basename(path))
            QMessageBox.information(self, "成功", f"檔案已儲存至:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"存檔失敗: {str(e)}")
