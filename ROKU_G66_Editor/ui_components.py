import sys
import platform
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QAbstractItemView)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.font_manager as fm
import numpy as np
import math

def configure_fonts():
    font_candidates = ['Microsoft JhengHei', 'Microsoft YaHei', 'PMingLiU', 'SimHei', 'Arial Unicode MS']
    selected_font = None
    system_fonts = {f.name for f in fm.fontManager.ttflist}
    for font in font_candidates:
        if font in system_fonts:
            selected_font = font
            break
    if selected_font:
        matplotlib.rcParams['font.sans-serif'] = [selected_font] + matplotlib.rcParams['font.sans-serif']
    matplotlib.rcParams['axes.unicode_minus'] = False

configure_fonts()

class DrillingPlot(QWidget):
    peckSelected = pyqtSignal(int) # Emit selected peck index
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.figure = Figure(figsize=(8, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)
        
        gs = self.figure.add_gridspec(1, 2, width_ratios=[1, 1])
        self.ax_geo = self.figure.add_subplot(gs[0])
        self.ax_cycle = self.figure.add_subplot(gs[1])
        self.figure.subplots_adjust(left=0.08, right=0.95, top=0.9, bottom=0.1, wspace=0.1)
        
        self.last_ijk_list = []
        self.last_visual_params = {}
        self.last_r = 0
        self.last_z = 0
        self.selected_z = None 
        self.feed_ijk_idx_map = []
        self.rapid_ijk_idx_map = []
        self.canvas.mpl_connect('pick_event', self.on_pick)

    def on_pick(self, event):
        if event.artist and event.artist.axes == self.ax_cycle:
            ind = event.ind[0]
            label = event.artist.get_label()
            
            if label == '快速 (Rapid)':
                if hasattr(self, 'rapid_ijk_idx_map') and ind < len(self.rapid_ijk_idx_map):
                    peck_idx = self.rapid_ijk_idx_map[ind]
                else:
                    return
            else:
                if hasattr(self, 'feed_ijk_idx_map') and ind < len(self.feed_ijk_idx_map):
                    peck_idx = self.feed_ijk_idx_map[ind]
                else:
                    peck_idx = ind // 3
            
            x_data, y_data = event.artist.get_data()
            if ind < len(y_data):
                visual_selected_y = y_data[ind]
                self.selected_z = visual_selected_y
                
                self.peckSelected.emit(peck_idx)
                
                self.draw_geometry(self.last_r, self.last_z, self.last_visual_params, self.selected_z, keep_limits=True)
                self.draw_cycle(self.last_r, self.last_z, self.last_ijk_list, self.last_visual_params, 
                                highlight_peck_idx=peck_idx, highlight_node_idx=ind, 
                                highlight_artist_label=label, keep_limits=True)
                self.canvas.draw()

    def update_plot(self, r_val, z_val, ijk_list, visual_params, highlight_peck_idx=None):
        self.last_r = r_val
        self.last_z = z_val
        self.last_ijk_list = ijk_list
        self.last_visual_params = visual_params
        
        self.ax_geo.clear()
        self.ax_cycle.clear()
        
        # Determine tool Z display (Default to bottom of peck if called from outside)
        tool_z = None
        if highlight_peck_idx is not None and highlight_peck_idx < len(ijk_list):
            cycle_type = visual_params.get('cycle_type', 'G66')
            shift = self.get_shift(visual_params)
            
            if cycle_type == 'G83':
                # G83: Cumulative relative addition
                acc_z = r_val
                for i in range(highlight_peck_idx + 1):
                    acc_z += ijk_list[i].get('I', 0.0)
                tool_z = acc_z + shift
            else:
                # G66: Absolute Z defined in 'I'
                target_z = ijk_list[highlight_peck_idx].get('I', 0.0)
                tool_z = target_z + shift
            
            self.selected_z = tool_z

        self.draw_geometry(r_val, z_val, visual_params, tool_z_override=tool_z, keep_limits=False)
        self.draw_cycle(r_val, z_val, ijk_list, visual_params, highlight_peck_idx=highlight_peck_idx, keep_limits=False)
        
        self.canvas.draw()

    def get_shift(self, visual_params):
        return visual_params.get('origin_z_shift', 0.0)

    def draw_geometry(self, r_val, z_val, visual_params, tool_z_override=None, keep_limits=False):
        prev_xlim = self.ax_geo.get_xlim() if keep_limits else None
        prev_ylim = self.ax_geo.get_ylim() if keep_limits else None
        
        self.ax_geo.clear()
        
        shift = self.get_shift(visual_params)
        thickness = visual_params.get('thickness', 10.0)
        tool_dia = visual_params.get('tool_dia', 0.1)
        spot_dia = visual_params.get('spot_dia', 0.0)
        exit_dia = visual_params.get('exit_chamfer_dia', 0.0)
        tip_angle = visual_params.get('tip_angle', 118.0)
        
        # Material Coordinates (Fixed)
        material_top = 0.0
        material_bottom = -abs(thickness)
        
        self.ax_geo.set_title("幾何預覽 (Geometry)")
        self.ax_geo.set_xlabel("直徑 X (mm)")
        self.ax_geo.set_ylabel("Z (mm)")
        self.ax_geo.set_aspect('equal', adjustable='datalim')
        
        display_width = max(tool_dia, spot_dia, exit_dia) * 2.0
        if display_width < 1.0: display_width = 1.0
        
        # Z=0 Line (Visual Y = shift)
        z0_visual = shift
        self.ax_geo.axhline(y=z0_visual, color='m', linestyle='-.', linewidth=1.2, label='程式原點 (Z=0)', zorder=1)

        # Material Body
        # 使用 axhspan 確保素材寬度充滿整個圖表視角 (無限寬度)
        self.ax_geo.axhspan(material_bottom, material_top, color='#D3D3D3', alpha=0.5, label='素材', zorder=1)
        
        # 繪製加工表面 (Top) 與 素材底面 (Bottom)
        self.ax_geo.axhline(y=material_top, color='k', linewidth=1.2, label='加工表面', zorder=2)
        self.ax_geo.axhline(y=material_bottom, color='k', linestyle='-', linewidth=1.0, alpha=0.6, zorder=2)
        
        # Spot Drill (Top)
        if spot_dia > 0:
            spot_depth = (spot_dia / 2.0)
            spot_tip_z = material_top - spot_depth
            vx = [-spot_dia/2, 0, spot_dia/2]
            vz = [material_top, spot_tip_z, material_top]
            self.ax_geo.fill(vx, vz, color='white', zorder=3)
            self.ax_geo.plot(vx, vz, color='k', linewidth=0.8, zorder=3)
            
        # Exit Chamfer (Bottom)
        if exit_dia > 0:
            chamfer_depth = exit_dia / 2.0
            chamfer_top_z = material_bottom + chamfer_depth
            vx = [-exit_dia/2, 0, exit_dia/2]
            vz = [material_bottom, chamfer_top_z, material_bottom]
            self.ax_geo.fill(vx, vz, color='white', zorder=3)
            self.ax_geo.plot(vx, vz, color='k', linewidth=0.8, zorder=3)
            
        if tool_z_override is not None:
            active_z = tool_z_override
        else:
            # G66: Default to Approach S; G83: Default to R
            cycle_type = visual_params.get('cycle_type', 'G66')
            if cycle_type == 'G66':
                active_z = visual_params.get('S', 0.0) + shift
            else:
                active_z = r_val + shift
        
        program_r_visual = r_val + shift
        program_z_visual = z_val + shift
        
        if tip_angle < 1: tip_angle = 1
        half_angle_rad = math.radians(tip_angle / 2.0)
        tip_h = (tool_dia / 2.0) / math.tan(half_angle_rad)
        
        # 繪製刀具：使其本體足夠長以穿透圖表頂部
        tool_body_top = active_z + 100.0
        tx = [-tool_dia/2, -tool_dia/2, 0, tool_dia/2, tool_dia/2]
        tz = [tool_body_top, active_z + tip_h, active_z, active_z + tip_h, tool_body_top]
        
        self.ax_geo.fill(tx, tz, color='#87CEFA', alpha=0.6, label='刀具', zorder=10)
        self.ax_geo.plot(tx, tz, color='blue', linewidth=1, zorder=11)
        
        self.ax_geo.axvline(x=0, color='k', linestyle='-.', alpha=0.3, linewidth=0.5, zorder=1)
        
        # S-Point Line
        approach_z = visual_params.get('S', 0.0) + shift
        self.ax_geo.axhline(y=approach_z, color='c', linestyle=':', linewidth=1.2, label='S點 (Approach)', zorder=2)
        
        self.ax_geo.axhline(y=program_r_visual, color='r', linestyle='--', linewidth=1, zorder=2)
        self.ax_geo.text(display_width * 0.6, program_r_visual, "R", color='r', fontsize=9, va='bottom', zorder=3)
        self.ax_geo.axhline(y=program_z_visual, color='g', linestyle='-', linewidth=1, zorder=2)
        
        self.ax_geo.grid(True, linestyle=':', alpha=0.3, zorder=0)

        if keep_limits and prev_xlim and prev_ylim:
            self.ax_geo.set_xlim(prev_xlim)
            self.ax_geo.set_ylim(prev_ylim)
        else:
            # 計算視野上限：取各參考點的最大值，並預留約 2mm 空間
            view_top = max(z0_visual, material_top, program_r_visual, approach_z) + 1.5
            
            # 計算視野下限：取加工底深點與素材底部的最小值，預留 1mm 空間
            bottom_targets = [program_z_visual, material_bottom]
            if exit_dia > 0: bottom_targets.append(material_bottom - 1.0)
            view_bottom = min(bottom_targets) - 1.0
            
            # 安全範圍檢查：至少顯示一定區域
            if view_top < z0_visual + 1: view_top = z0_visual + 1
            if view_bottom > z0_visual - 1: view_bottom = z0_visual - 1
            
            self.ax_geo.set_ylim(view_bottom, view_top)
            self.ax_geo.set_xlim(-display_width/2 - 0.5, display_width/2 + 0.5)
        
        handles, labels = self.ax_geo.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        self.ax_geo.legend(by_label.values(), by_label.keys(), loc='upper right', fontsize='x-small', framealpha=0.5)
        # self.figure.tight_layout() # 移除此行，避免覆寫自訂的 subplots_adjust 與 width_ratios
        self.figure.subplots_adjust(left=0.08, right=0.95, top=0.9, bottom=0.1, wspace=0.15)

    def draw_cycle(self, r_val, z_val, ijk_list, visual_params, highlight_peck_idx=None, 
                   highlight_node_idx=None, highlight_artist_label=None, keep_limits=False):
        prev_xlim = self.ax_cycle.get_xlim() if keep_limits else None
        prev_ylim = self.ax_cycle.get_ylim() if keep_limits else None
        
        self.ax_cycle.clear()
        
        shift = self.get_shift(visual_params)
        thickness = visual_params.get('thickness', 10.0)
        
        material_top = 0.0
        material_bottom = -abs(thickness)
        
        z0_visual = shift
        program_r_visual = r_val + shift
        program_z_visual = z_val + shift
        
        self.ax_cycle.set_title("循環動作 (點擊節點檢視)")
        self.ax_cycle.set_xlabel("步序")
        
        self.ax_cycle.axhline(y=z0_visual, color='m', linestyle='-.', linewidth=1.2, label='程式原點 (Z=0)')
        self.ax_cycle.axhline(y=material_top, color='k', linestyle='-', linewidth=1.2, label='加工表面')
        self.ax_cycle.axhline(y=material_bottom, color='k', linestyle='-', linewidth=1.0, alpha=0.6) # 素材底面
        
        # S-Point Line
        s_val = visual_params.get('S')
        if s_val is not None:
             approach_z = s_val + shift
             # 僅在 S 點不等於 R 點時繪製參考線
             if abs(s_val - visual_params.get('R', 0)) > 1e-6:
                 self.ax_cycle.axhline(y=approach_z, color='c', linestyle=':', linewidth=1.2, label='S點')
        
        self.ax_cycle.axhline(y=program_r_visual, color='r', linestyle='--', label='R點')
        self.ax_cycle.axhline(y=program_z_visual, color='g', linestyle='-', label='Z底')
        
        cycle_type = visual_params.get('cycle_type', 'G66')
        is_g83 = (cycle_type == 'G83')
        is_ijk_mode = visual_params.get('use_ijk_mode', False)
        
        self.feed_x, self.feed_z = [], []
        self.feed_ijk_idx_map = []
        self.rapid_x, self.rapid_z = [], []
        self.rapid_ijk_idx_map = []
        
        current_x = 0
        
        # --- 移除冗餘初始化位移 ---
        # 徹底移除原有的線段輸出指令，僅保留數值初始化以供後續迴圈計算
        # G66: 以 S 點為起始；G83: 以 R 點為起始
        current_z_visual = (visual_params.get('S', r_val) if not is_g83 else r_val) + shift
        
        if ijk_list:
            for idx, params in enumerate(ijk_list):
                val_i = params.get('I', 0.0)
                # Next target: G83 is relative increment, G66 is absolute Z
                if not is_g83:
                    # --- G66 P9131 專用精確模擬 (根據手冊 PXL_20260205_010052554) ---
                    target_nc_z = val_i # 本階段終點深度 (絕對值)
                    stage_peck_q = params.get('J', 0.0) # 啄鑽深度
                    if stage_peck_q <= 0: stage_peck_q = 9999.0 # 如果 J=0 則為一刀到底
                    
                    # 接近點 S 處理：若省略則預設為 R
                    approach_nc_z = visual_params.get('S')
                    if approach_nc_z is None: approach_nc_z = r_val
                    
                    gap_d = 0.1 # 安全間隙 d
                    
                    # 初始化：記錄本階段起始深度
                    if idx == 0:
                        last_drilled_nc_z = approach_nc_z
                        # 直接繪製循環最初的快速定位動作：R -> S
                        # 我們不考慮之前的刀具位置，直接由機台設定的 R 點開始模擬
                        if abs(approach_nc_z - r_val) > 1e-6:
                            # 這是第一個點，我們不需要起始 line，直接記錄線段
                            self.rapid_x.extend([current_x, current_x + 0.2, None])
                            self.rapid_z.extend([r_val + shift, approach_nc_z + shift, None])
                            self.rapid_ijk_idx_map.extend([idx, idx, idx])
                            current_x += 0.2
                        is_first_peck_of_cycle = True
                    else:
                        last_drilled_nc_z = prev_stage_end_z
                        is_first_peck_of_cycle = False
                        
                    is_drilling_down = target_nc_z < last_drilled_nc_z
                    
                    # 階段啄鑽核心迴圈
                    while True:
                        # 檢查是否到達本階段目標
                        if is_drilling_down:
                            if last_drilled_nc_z <= target_nc_z + 1e-6: break
                        else:
                            if last_drilled_nc_z >= target_nc_z - 1e-6: break

                        # 計算本次啄鑽終點深度
                        if is_drilling_down:
                            next_nc_z = last_drilled_nc_z - stage_peck_q
                            if next_nc_z < target_nc_z: next_nc_z = target_nc_z
                        else:
                            next_nc_z = last_drilled_nc_z + stage_peck_q
                            if next_nc_z > target_nc_z: next_nc_z = target_nc_z
                        
                        # A. 快速切入邏輯
                        if is_first_peck_of_cycle:
                            # 整個循環的第一刀：已經在 S 點，直接起切，不需額外快速移動
                            start_feed_nc_z = approach_nc_z
                            is_first_peck_of_cycle = False # 後續不再是第一刀
                        else:
                            # 非第一刀：必須從 R 快速降到 (上次深度 + 間隙 d)
                            clearance_nc_z = last_drilled_nc_z + (gap_d if is_drilling_down else -gap_d)
                            # 限制間隙高度不超過 R 點
                            if is_drilling_down and clearance_nc_z > r_val: clearance_nc_z = r_val
                            
                            self.rapid_x.extend([current_x, current_x + 0.5, None])
                            self.rapid_z.extend([r_val + shift, clearance_nc_z + shift, None])
                            self.rapid_ijk_idx_map.extend([idx, idx, idx])
                            current_x += 0.5
                            start_feed_nc_z = clearance_nc_z
                        
                        # B. 進給切削 (Feed)：(起切點) -> 本次目標深度
                        self.feed_x.extend([current_x, current_x + 1.0, None])
                        self.feed_z.extend([start_feed_nc_z + shift, next_nc_z + shift, None])
                        self.feed_ijk_idx_map.extend([idx, idx, idx])
                        current_x += 1.0
                        
                        # C. 快速退刀 (Retract)：本次目標深度 -> R
                        self.rapid_x.extend([current_x, current_x + 0.5, None])
                        self.rapid_z.extend([next_nc_z + shift, r_val + shift, None])
                        self.rapid_ijk_idx_map.extend([idx, idx, idx])
                        current_x += 0.5
                        
                        last_drilled_nc_z = next_nc_z
                        if current_x > 300: break # 安全閥

                    prev_stage_end_z = last_drilled_nc_z
                    current_z_visual = last_drilled_nc_z + shift

                else:
                    # --- Standard G83 / G83 IJK Logic ---
                    # Next target: G83 is relative increment
                    if is_g83:
                         target_z_visual = current_z_visual + val_i
                    else:
                         # Should not happen if G66 is handled above, but fallback
                         target_z_visual = val_i + shift

                    if is_g83 and not is_ijk_mode:
                        # 標準 Q 模式 (G83)：第一跳完整進給，後續跳快速回孔內+間隙
                        peck_clearance = 0.1  # 固定安全間隙 (FANUC 標準)
                        
                        if idx == 0:
                            # 第一跳：從 R 點完整進給
                            self.feed_x.extend([current_x, current_x + 1.0, None])
                            self.feed_z.extend([program_r_visual, target_z_visual, None])
                            self.feed_ijk_idx_map.extend([idx, idx, idx])
                            current_x += 1.0
                        else:
                            # 後續跳：快速回到 (上次深度 + 間隙)，再進給
                            clearance_z_visual = current_z_visual + peck_clearance
                            
                            # 1. 快速移動：R → (上次深度 + 間隙)
                            self.rapid_x.extend([current_x, current_x + 0.2, None])
                            self.rapid_z.extend([program_r_visual, clearance_z_visual, None])
                            self.rapid_ijk_idx_map.extend([idx, idx, idx])
                            current_x += 0.2
                            
                            # 2. 進給切削：(上次深度 + 間隙) → 目標深度
                            self.feed_x.extend([current_x, current_x + 0.8, None])
                            self.feed_z.extend([clearance_z_visual, target_z_visual, None])
                            self.feed_ijk_idx_map.extend([idx, idx, idx])
                            current_x += 0.8
                        
                        # 所有跳：退刀至 R
                        self.rapid_x.extend([current_x, current_x + 0.2, None])
                        self.rapid_z.extend([target_z_visual, program_r_visual, None])
                        self.rapid_ijk_idx_map.extend([idx, idx, idx])
                        current_x += 0.2
                    else:
                        # G83 IJK Logic (Variable) if needed, or fallback
                        peck_clearance = params.get('J', 0.1) if not is_g83 else 0.1
                        
                        if idx == 0:
                            self.feed_x.extend([current_x, current_x + 1.0, None])
                            self.feed_z.extend([current_z_visual, target_z_visual, None])
                            self.feed_ijk_idx_map.extend([idx, idx, idx])
                            current_x += 1.0
                        else:
                            clearance_z_visual = current_z_visual + peck_clearance
                            
                            self.rapid_x.extend([current_x, current_x + 0.2, None])
                            self.rapid_z.extend([program_r_visual, clearance_z_visual, None])
                            self.rapid_ijk_idx_map.extend([idx, idx, idx])
                            current_x += 0.2
                            
                            self.feed_x.extend([current_x, current_x + 0.8, None])
                            self.feed_z.extend([clearance_z_visual, target_z_visual, None])
                            self.feed_ijk_idx_map.extend([idx, idx, idx]) 
                            current_x += 0.8
                        
                        self.rapid_x.extend([current_x, current_x + 0.2, None])
                        self.rapid_z.extend([target_z_visual, program_r_visual, None])
                        self.rapid_ijk_idx_map.extend([idx, idx, idx])
                        current_x += 0.2
                    
                    current_z_visual = target_z_visual
                
        if ijk_list:
            self.ax_cycle.plot(self.feed_x, self.feed_z, color='#1f77b4', linestyle='-', linewidth=1.5, marker='.', markersize=5, label='進刀 (Feed)', picker=10)
            self.ax_cycle.plot(self.rapid_x, self.rapid_z, color='#ff7f0e', linestyle='--', linewidth=1, marker='.', markersize=4, label='快速 (Rapid)', alpha=0.8, picker=10)
            
            if highlight_peck_idx is not None or highlight_node_idx is not None:
                hx, hz = None, None
                if highlight_node_idx is not None:
                    # 如果有指定節點，根據標記來源選取資料來源
                    source_x = self.rapid_x if highlight_artist_label == '快速 (Rapid)' else self.feed_x
                    source_z = self.rapid_z if highlight_artist_label == '快速 (Rapid)' else self.feed_z
                    if highlight_node_idx < len(source_x):
                        hx = source_x[highlight_node_idx]
                        hz = source_z[highlight_node_idx]
                
                # 如果節點不可得(例如由外部觸發)，則預設高亮該 Peck 的進給點
                if hx is None and highlight_peck_idx is not None:
                    try:
                        pts = [i for i, v in enumerate(self.feed_ijk_idx_map) if v == highlight_peck_idx]
                        if pts:
                            point_idx = pts[-2] if len(pts) >= 2 else pts[0]
                            if point_idx < len(self.feed_x):
                                hx = self.feed_x[point_idx]
                                hz = self.feed_z[point_idx]
                    except:
                        pass
                
                if hx is not None and hz is not None:
                    self.ax_cycle.plot(hx, hz, 'o', color='orange', markersize=9, mfc='none', markeredgewidth=2)
                    self.ax_cycle.axhline(y=hz, color='orange', linestyle='--', alpha=0.5, linewidth=0.8)

        if keep_limits and prev_xlim and prev_ylim:
            self.ax_cycle.set_xlim(prev_xlim)
            self.ax_cycle.set_ylim(prev_ylim)
        else:
            max_step = current_x if 'current_x' in locals() else 10
            self.ax_cycle.set_xlim(-2, max_step + 4)
            
            # Y 軸範圍計算
            candidates = [program_z_visual, material_bottom, program_r_visual, material_top, z0_visual]
            valid_candidates = [v for v in candidates if v is not None and np.isfinite(v)]
            
            if not valid_candidates:
                y_min, y_max = -10, 5
            else:
                y_min = min(valid_candidates) - 1.0
                y_max = max(valid_candidates) + 1.0

            # 確保最小範圍，避免圖表壓扁
            if abs(y_max - y_min) < 1.0:
                mid = (y_max + y_min) / 2.0
                y_min = mid - 2.0
                y_max = mid + 2.0
            
            self.ax_cycle.set_ylim(y_min, y_max)
        
        cur_xlim = self.ax_cycle.get_xlim()
        self.ax_cycle.fill_between(cur_xlim, material_bottom, material_top, color='gray', alpha=0.1)
        
        handles, labels = self.ax_cycle.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        self.ax_cycle.legend(by_label.values(), by_label.keys(), loc='upper right', fontsize='small')


class ParamTable(QTableWidget):
    dataChangedSignal = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(3)
        self.update_headers('G66') # Default to G66
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.itemChanged.connect(self.on_item_changed)
        
    def update_headers(self, cycle_type='G66'):
        """動態更新表格標頭以區分模式。"""
        if cycle_type == 'G83':
            headers = ["單次深度 (Step)", "累計深度 (Total)", "進給速度 (F)"]
        else:
            headers = ["I (階段終點 Z)", "J (啄鑽深度 Q)", "K (進給速度 F)"]
        self.setHorizontalHeaderLabels(headers)
        
    def load_data(self, ijk_list):
        self.blockSignals(True)
        self.setRowCount(len(ijk_list))
        for r, row_data in enumerate(ijk_list):
            # [修正] 使用 :g 格式化數值，避免顯示長精度雜訊 (如 -0.3499999999)
            val_i = row_data.get('I', 0.0)
            val_j = row_data.get('J', 0.0)
            val_k = row_data.get('K', 0.0)
            self.setItem(r, 0, QTableWidgetItem(f"{val_i:g}"))
            self.setItem(r, 1, QTableWidgetItem(f"{val_j:g}"))
            self.setItem(r, 2, QTableWidgetItem(f"{val_k:g}"))
        self.blockSignals(False)
        
    def get_data(self):
        result = []
        for r in range(self.rowCount()):
            full_set = {}
            for c, key in enumerate(['I', 'J', 'K']):
                item = self.item(r, c)
                val = float(item.text()) if item and self.is_float(item.text()) else 0.0
                full_set[key] = val
            result.append(full_set)
        return result

    def on_item_changed(self, item):
        self.dataChangedSignal.emit()
        
    def is_float(self, s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    def add_row(self):
        r = self.rowCount()
        self.insertRow(r)
        self.blockSignals(True)
        for c in range(3): self.setItem(r, c, QTableWidgetItem("0.0"))
        self.blockSignals(False)
        self.dataChangedSignal.emit()

    def remove_row(self):
        r = self.rowCount()
        if r > 0:
            self.removeRow(r - 1)
            self.dataChangedSignal.emit()
