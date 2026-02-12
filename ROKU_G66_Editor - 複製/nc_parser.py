import re
import os
import copy

class RokuNCParser:
    """
    Parser for ROKU-ROKU NC files, supporting:
    - G66 P9131 cycles (custom ROKU format)
    - G83 standard peck drilling cycles
    """
    def __init__(self):
        self.nc_lines = []
        self.tools_data = []
        self.tool_diameters = {}

    def parse_file(self, file_path):
        """
        讀取檔案並解析 G66 和 G83 循環指令。
        保留完整檔案內容於 self.nc_lines 以供修改。
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.nc_lines = f.readlines()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='cp950', errors='ignore') as f:
                self.nc_lines = f.readlines()

        self.tools_data = []
        self.tool_diameters = {}
        current_tool = "Unknown"

        for idx, line in enumerate(self.nc_lines):
            # 偵測刀具換刀
            t_match = re.search(r'T(\d+)', line)
            if t_match:
                found_id = t_match.group(1)
                dia = self._scan_for_diameter(idx, found_id)
                if dia is not None:
                    self.tool_diameters[found_id] = dia
                current_tool = found_id

            # Detect G66 P9131 or G83
            if 'G66' in line and 'P9131' in line:
                self._parse_g66_line(idx, line, current_tool)
            elif 'G83' in line:
                self._parse_fixed_cycle_line(idx, line, current_tool)

        return self.tools_data

    def _scan_for_diameter(self, current_line_idx, tool_id):
        """
        在刀具行 +/- 10 行範圍內搜尋 D 值。
        """
        start = max(0, current_line_idx - 10)
        end = min(len(self.nc_lines), current_line_idx + 11)
        
        for i in range(start, end):
            line = self.nc_lines[i]
            d_matches = re.findall(r'D\s*(\d*\.?\d+)', line)
            for d_val in d_matches:
                try:
                    val = float(d_val)
                    if val > 0: return val
                except:
                    continue
        return None

    def _parse_g66_line(self, line_index, line, tool_id):
        """
        解析 G66 P9131 循環指令。
        """
        # Updated regex to include T (Dwell Time)
        matches = re.findall(r'([RZSIJKT])\s*([-+]?(?:\d*\.\d+|\d+))', line)

        static_params = {'R': None, 'Z': None, 'S': None, 'T': None, 'F': None, 'Q': None}
        dynamic_params = []
        
        temp_ijk = {}
        
        for key, val_str in matches:
            key = key.strip()
            if not key or not val_str: continue
            
            val = float(val_str)
            
            if key in ['R', 'Z', 'S', 'T']:
                static_params[key] = val
            elif key in ['I', 'J', 'K']:
                if key in temp_ijk:
                    self._fill_missing_ijk(temp_ijk)
                    if not self._is_zero_set(temp_ijk):
                        dynamic_params.append(temp_ijk)
                    temp_ijk = {}
                temp_ijk[key] = val
        
        if temp_ijk:
            self._fill_missing_ijk(temp_ijk)
            if not self._is_zero_set(temp_ijk):
                dynamic_params.append(temp_ijk)
        
        detected_dia = self.tool_diameters.get(tool_id, None)

        data = {
            'tool_id': tool_id,
            'line_index': line_index,
            'original_line': line.strip(),
            'cycle_type': 'G66',
            'static_params': static_params,
            'dynamic_params': dynamic_params,
            'initial_static': copy.deepcopy(static_params),
            'initial_dynamic': copy.deepcopy(dynamic_params),
            'detected_diameter': detected_dia
        }
        self.tools_data.append(data)

    def _parse_fixed_cycle_line(self, line_index, line, tool_id, cycle_type='G83'):
        """
        解析 G83 固定循環 (支援 Q 模式 與 I/J/K 模式)。
        """
        matches = re.findall(r'([RZQFX YIJK])\s*([-+]?(?:\d*\.\d+|\d+))', line)
        
        static_params = {'R': None, 'Z': None, 'Q': None, 'F': None, 'P': None, 'I': None, 'J': None, 'K': None}
        
        for key, val_str in matches:
            val = float(val_str)
            static_params[key] = val
            
        detected_dia = self.tool_diameters.get(tool_id, 0.0)
        
        
        # Determine Mode
        use_ijk_mode = False
        if static_params.get('I') is not None or static_params.get('K') is not None:
             use_ijk_mode = True
        
        if static_params.get('I') is None: static_params['I'] = 0.0
        if static_params.get('J') is None: static_params['J'] = 0.0
        if static_params.get('K') is None: static_params['K'] = 0.0
        
        # 檢查 Q 模式的 Q 值是否為 0
        if not use_ijk_mode:
            if static_params.get('Q') is None or abs(static_params['Q']) < 1e-6:
                # 計算合理的預設 Q 值 (根據孔深)
                depth = abs(static_params.get('Z', 0) - static_params.get('R', 0))
                static_params['Q'] = min(1.0, depth / 3.0) if depth > 0 else 1.0
        
        # 檢查 I/J/K 模式的值是否為 0（新增）
        if use_ijk_mode and abs(static_params['I']) < 1e-6:
            # I=0 時，根據刀具直徑計算預設值
            detected_dia = self.tool_diameters.get(tool_id, 0.0)
            if detected_dia > 1e-6:
                # 使用刀具直徑計算預設值（需要導入 analysis_engine）
                from analysis_engine import DrillingAnalysisEngine
                i_val, j_val, k_val = DrillingAnalysisEngine.get_default_ijk(detected_dia)
                static_params['I'] = i_val
                static_params['J'] = j_val
                static_params['K'] = k_val
            else:
                # 無刀具直徑時，根據孔深計算
                depth = abs(static_params.get('Z', 0) - static_params.get('R', 0))
                static_params['I'] = min(0.5, depth / 3.0) if depth > 0 else 0.5
                static_params['J'] = static_params['I'] * 0.2  # 20% 遞減
                static_params['K'] = static_params['I'] * 0.5  # 50% 下限
        
        # 如果 I/J/K 全為 0,強制使用 Q 模式
        if use_ijk_mode and abs(static_params['I']) < 1e-6 and abs(static_params['K']) < 1e-6:
            use_ijk_mode = False
            if static_params.get('Q') is None or abs(static_params['Q']) < 1e-6:
                # 如果 Q 也是 0 或不存在,設一個合理的預設值
                depth = abs(static_params.get('Z', 0) - static_params.get('R', 0))
                static_params['Q'] = min(1.0, depth / 3.0) if depth > 0 else 1.0

        dynamic_params = self._g83_to_ijk(static_params, cycle_type, use_ijk_mode)
        
        detected_dia = self.tool_diameters.get(tool_id, None)
        
        data = {
            'tool_id': tool_id,
            'line_index': line_index,
            'original_line': line.strip(),
            'cycle_type': 'G83', # Always G83
            'use_ijk_mode': use_ijk_mode, # Flag for UI
            'initial_use_ijk_mode': use_ijk_mode, # Store initial state for comparison
            'static_params': static_params,
            'dynamic_params': dynamic_params,
            'initial_static': copy.deepcopy(static_params),
            'initial_dynamic': copy.deepcopy(dynamic_params),
            'detected_diameter': detected_dia,
            'original_xy': {'X': static_params.get('X'), 'Y': static_params.get('Y')}
        }
        self.tools_data.append(data)

    def _g83_to_ijk(self, params, cycle_type='G83', use_ijk_mode=False):
        """
        將 G83 的 Q 或 I/J/K 值轉換為等效的視覺化階段。
        
        Standard Mode (Q):
        - 固定每次 Q 深度
        
        Variable Mode (I/J/K):
        - I: Initial Peck
        - J: Reduction Amount
        - K: Minimum Peck
        """
        r_point = params.get('R', 0)
        z_bottom = params.get('Z', 0)
        
        ijk_list = []
        current_z = r_point
        drilling_down = z_bottom < r_point
        
        # Mode Selection
        if use_ijk_mode:
            current_peck = abs(params.get('I', 0)) # Initial Peck
            peck_reduction = abs(params.get('J', 0))
            min_peck = abs(params.get('K', 0))
            if current_peck <= 1e-6: return [] # Avoid infinite loop
        else:
            current_peck = abs(params.get('Q', 0))
            if current_peck <= 1e-6: return []
            
        while True:
            # Calculate next Z
            if drilling_down:
                next_z = max(current_z - current_peck, z_bottom)
                depth_increment = current_z - next_z
            else:
                next_z = min(current_z + current_peck, z_bottom)
                depth_increment = next_z - current_z
            
            if depth_increment < 1e-6:
                break
            
            # I parameter for visualization (Step Depth)
            i_vis = -depth_increment if drilling_down else depth_increment
            
            # J parameter for visualization (Retract to R for G83)
            j_vis = r_point - next_z 
            
            ijk_list.append({
                'I': i_vis,
                'J': j_vis,
                'K': 0.0
            })
            
            current_z = next_z
            
            # Check finish
            if drilling_down and current_z <= z_bottom: break
            if not drilling_down and current_z >= z_bottom: break
            
            # Update Peck for next pass (Variable Mode only)
            if use_ijk_mode:
                current_peck -= peck_reduction
                if current_peck < min_peck:
                    current_peck = min_peck
        
        return ijk_list

    def _is_zero_set(self, ijk):
        """檢查 I, J, K 是否全為零。"""
        return (abs(ijk.get('I', 0.0)) < 1e-6 and 
                abs(ijk.get('J', 0.0)) < 1e-6 and 
                abs(ijk.get('K', 0.0)) < 1e-6)

    def _fill_missing_ijk(self, ijk_dict):
        """確保 I, J, K 鍵存在，預設為 0.0。"""
        for k in ['I', 'J', 'K']:
            if k not in ijk_dict:
                ijk_dict[k] = 0.0

    def update_g66_line(self, data_index, new_static, new_dynamic_list):
        """
        更新指定刀具的循環指令。
        根據原始類型（G83 或 G66）重建對應格式。
        """
        if data_index < 0 or data_index >= len(self.tools_data):
            return False
        
        tool_data = self.tools_data[data_index]
        line_idx = tool_data['line_index']
        cycle_type = tool_data.get('cycle_type', 'G66')
        
        if cycle_type == 'G83':
            # Reconstruct G83
            parts = ["G83"]
            
            original_xy = tool_data.get('original_xy', {})
            if original_xy.get('X') is not None: parts.append(f"X{original_xy['X']}")
            if original_xy.get('Y') is not None: parts.append(f"Y{original_xy['Y']}")
            
            if new_static.get('Z') is not None: parts.append(f"Z{new_static['Z']}")
            if new_static.get('R') is not None: parts.append(f"R{new_static['R']}")
            
            use_ijk = tool_data.get('use_ijk_mode', False)
            if use_ijk:
                if new_static.get('I') is not None: parts.append(f"I{new_static['I']}")
                if new_static.get('J') is not None: parts.append(f"J{new_static['J']}")
                if new_static.get('K') is not None: parts.append(f"K{new_static['K']}")
            else:
                if new_static.get('Q') is not None: parts.append(f"Q{new_static['Q']}")
                
            if new_static.get('F') is not None: parts.append(f"F{new_static['F']}")
        
        else:
            # 重建 G66 P9131 格式
            parts = ["G66 P9131"]
            
            # R、Z 必須參數
            if new_static.get('R') is not None: 
                parts.append(f"R{new_static['R']}")
            if new_static.get('Z') is not None: 
                parts.append(f"Z{new_static['Z']}")
            
            # S、T 可選參數（省略 0 值）
            if new_static.get('S') is not None and abs(new_static['S']) > 1e-6:
                parts.append(f"S{new_static['S']}")
            if new_static.get('T') is not None and abs(new_static['T']) > 1e-6:
                parts.append(f"T{new_static['T']}")
            
            # 添加動態參數（省略 0 值）
            for group in new_dynamic_list:
                i_val = group.get('I', 0.0)
                j_val = group.get('J', 0.0)
                k_val = group.get('K', 0.0)
                # 只添加非 0 值
                if abs(i_val) > 1e-6 or abs(j_val) > 1e-6 or abs(k_val) > 1e-6:
                    parts.append(f"I{i_val}")
                    parts.append(f"J{j_val}")
                    parts.append(f"K{k_val}")
        
        new_line = " ".join(parts) + "\n"
        
        # 更新記憶體
        self.nc_lines[line_idx] = new_line
        
        # 更新內部資料結構
        tool_data['static_params'] = new_static
        tool_data['dynamic_params'] = new_dynamic_list
        tool_data['original_line'] = new_line.strip()
        
        return True

    def generate_html(self, data_index, context_lines=10):
        """
        Generates HTML string with changed values highlighted in red.
        Includes context_lines above and below the active line.
        """
        if data_index < 0 or data_index >= len(self.tools_data):
            return ""
            
        tool_data = self.tools_data[data_index]
        line_index = tool_data['line_index']
        
        # --- Context Above ---
        start_line = max(0, line_index - context_lines)
        context_above = []
        for i in range(start_line, line_index):
            line_str = self.nc_lines[i].strip()
            # Escape HTML special chars if needed, simpler replacement for now
            line_str = line_str.replace("<", "&lt;").replace(">", "&gt;")
            context_above.append(f"<span style='color:gray;'>{line_str}</span>")
            
        # --- Active Line Construction (Highlighed) ---
        current_static = tool_data['static_params']
        initial_static = tool_data.get('initial_static', {})
        current_dynamic = tool_data['dynamic_params']
        initial_dynamic = tool_data.get('initial_dynamic', [])
        cycle_type = tool_data.get('cycle_type', 'G66')
        
        active_parts = []
        
        def format_val(key, curr_dict, init_dict, prefix=""):
            val = curr_dict.get(key)
            init_val = init_dict.get(key)
            if val is None: return ""
            
            # Check for change (tolerance)
            changed = init_val is None or abs(val - init_val) > 1e-6
            
            # Format logic
            s_val = f"{val}".rstrip('0').rstrip('.') if isinstance(val, float) else str(val)
            
            if isinstance(val, (float, int)):
                 s_val = f"{val}"
            
            text = f"{prefix}{key}{s_val}"
            
            if changed:
                return f"<span style='color:red; font-weight:bold;'>{text}</span>"
            else:
                return text

        if cycle_type == 'G83':
            active_parts.append("G83")
            xy = tool_data.get('original_xy', {})
            if xy.get('X') is not None: active_parts.append(f"X{xy['X']}")
            if xy.get('Y') is not None: active_parts.append(f"Y{xy['Y']}")
            
            active_parts.append(format_val('Z', current_static, initial_static))
            active_parts.append(format_val('R', current_static, initial_static))
            
            use_ijk = tool_data.get('use_ijk_mode', False)
            if use_ijk:
                active_parts.append(format_val('I', current_static, initial_static))
                active_parts.append(format_val('J', current_static, initial_static))
                active_parts.append(format_val('K', current_static, initial_static))
            else:
                active_parts.append(format_val('Q', current_static, initial_static))
                
            active_parts.append(format_val('F', current_static, initial_static))
            
        else: # G66
            active_parts.append("G66 P9131")
            # R、Z 必須參數
            active_parts.append(format_val('R', current_static, initial_static))
            active_parts.append(format_val('Z', current_static, initial_static))
            
            # S、T 可選參數（省略 0 值）
            s_val = current_static.get('S')
            if s_val is None: s_val = 0.0
            t_val = current_static.get('T')
            if t_val is None: t_val = 0.0
            
            if abs(s_val) > 1e-6:
                active_parts.append(format_val('S', current_static, initial_static))
            if abs(t_val) > 1e-6:
                active_parts.append(format_val('T', current_static, initial_static))
            
            # 動態參數（省略全為 0 的組）
            for i, group in enumerate(current_dynamic):
                init_group = initial_dynamic[i] if i < len(initial_dynamic) else {}
                i_val = group.get('I'); j_val = group.get('J'); k_val = group.get('K')
                if i_val is None: i_val = 0.0
                if j_val is None: j_val = 0.0
                if k_val is None: k_val = 0.0
                # 只添加非 0 組
                if abs(i_val) > 1e-6 or abs(j_val) > 1e-6 or abs(k_val) > 1e-6:
                    active_parts.append(format_val('I', group, init_group))
                    active_parts.append(format_val('J', group, init_group))
                    active_parts.append(format_val('K', group, init_group))
        
        active_line_html = "&nbsp;".join([p for p in active_parts if p])
        active_line_html = f"<div style='background-color:#e6f3ff;'><b>{active_line_html}</b></div>"
        
        # --- Context Below ---
        end_line = min(len(self.nc_lines), line_index + 1 + context_lines)
        context_below = []
        for i in range(line_index + 1, end_line):
            line_str = self.nc_lines[i].strip()
            line_str = line_str.replace("<", "&lt;").replace(">", "&gt;")
            context_below.append(f"<span style='color:gray;'>{line_str}</span>")

        # Combine
        full_html = "<br>".join(context_above + [active_line_html] + context_below)
        return full_html

    def save_file(self, output_path):
        """將修改後的內容寫入檔案。"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(self.nc_lines)
