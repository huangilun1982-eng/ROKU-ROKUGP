import math

class DrillingAnalysisEngine:
    """
    專門處理加工效率分析與時間預估的邏輯引擎。
    將邏輯與 UI 分離。
    """
    
    @staticmethod
    def calc_drilling_time(ijk_list, feedrate, r_point, g0_speed, is_ijk_mode, clearance=0.1):
        """
        計算單一孔位的鑽孔循環預估時間。
        
        Args:
            ijk_list (list): 啄鑽階段列表 [{'I': depth_inc, ...}]
            feedrate (float): 進給速度 (F)
            r_point (float): R 點高度
            g0_speed (float): 機台快速下壓/退刀速度 (G0)
            is_ijk_mode (bool): 是否為進階 IJK/G66 模式
            clearance (float): 啄鑽安全間隙 (預設 0.1mm)
            
        Returns:
            float: 預估總時間 (分鐘)
        """
        if feedrate <= 0:
            return float('inf')
            
        total_t = 0
        current_z = r_point # 從 R 點開始計算
        
        for idx, peck in enumerate(ijk_list):
            # peck['I'] 是當次下鑽的增量深度 (通常為負值)
            increment = peck.get('I', 0.0)
            prev_z = current_z
            target_z = prev_z + increment
            
            if is_ijk_mode:
                # 進階 IJK 模式 (Macro P9131)：使用快速移動下壓
                if idx == 0:
                    # 第一段：從 R 點一路進給進刀
                    feed_dist = abs(target_z - r_point)
                    total_t += feed_dist / feedrate
                else:
                    # 後續段：快速移動到 (上次深度 + 間隙)，再進給進刀
                    # 1. 快速移動：R -> (上次深度 + 間隙)
                    dist_g0_down = abs(r_point - (prev_z + clearance))
                    total_t += dist_g0_down / g0_speed
                    # 2. 進給切削：(上次深度 + 間隙) -> 本次目標深度
                    feed_dist = abs(target_z - (prev_z + clearance))
                    total_t += feed_dist / feedrate
            else:
                # 標準 Q 模式 (G83)：第一跳從R點進給，後續跳快速回孔+進給切削
                if idx == 0:
                    # 第一跳：從 R 點一路進給進刀
                    feed_dist = abs(target_z - r_point)
                    total_t += feed_dist / feedrate
                else:
                    # 後續跳：快速回到 (上次深度 + 間隙)，再進給進刀
                    # 1. 快速移動：R → (上次深度 + 間隙)
                    dist_g0_down = abs(r_point - (prev_z + clearance))
                    total_t += dist_g0_down / g0_speed
                    # 2. 進給切削：(上次深度 + 間隙) → 本次目標深度
                    feed_dist = abs(target_z - (prev_z + clearance))
                    total_t += feed_dist / feedrate
            
            # 所有模式：孔底均快速退回 R
            dist_g0_up = abs(target_z - r_point)
            total_t += dist_g0_up / g0_speed
            
            current_z = target_z
            
        return total_t

    def compare_efficiency(self, current_params, initial_params, g0_speed=5000):
        """
        比較兩組參數的加工效率。
        
        Args:
            current_params (dict): {ijk_list, feedrate, r_point, is_ijk_mode}
            initial_params (dict): {ijk_list, feedrate, r_point, is_ijk_mode}
            g0_speed (float): 機台快速速度
            
        Returns:
            dict: {time_save_pct, peck_change, init_time, curr_time}
        """
        curr_t = self.calc_drilling_time(
            current_params['ijk_list'], 
            current_params['feedrate'], 
            current_params['r_point'], 
            g0_speed, 
            current_params['is_ijk_mode']
        )
        
        init_t = self.calc_drilling_time(
            initial_params['ijk_list'], 
            initial_params['feedrate'], 
            initial_params['r_point'], 
            g0_speed, 
            initial_params['is_ijk_mode']
        )
        
        curr_pecks = len(current_params['ijk_list'])
        init_pecks = len(initial_params['ijk_list'])
        
        save_pct = 0.0
        if init_t > 0 and init_t != float('inf') and curr_t != float('inf'):
            save_pct = (init_t - curr_t) / init_t * 100
            
        return {
            'save_pct': save_pct,
            'init_pecks': init_pecks,
            'curr_pecks': curr_pecks,
            'init_time': init_t,
            'curr_time': curr_t
        }

    @staticmethod
    def calculate_dri(diameter, depth, material_key, coolant_mode, tool_mat_key, config=None):
        """計算鑽孔風險指數 (Drilling Risk Index, DRI)"""
        if diameter <= 0: return 999
        
        r_ratio = depth / diameter
        # [V6.0] 深度風險 (非線性惡化，1.2 為淺孔風險偏移)
        r_depth = 1.2 + (r_ratio ** 1.4)
        
        # 2. 其他風險因子
        r_material = 1.0
        r_coolant = 1.0
        r_tool = 1.0
        
        if config:
            factors = config.data.get('dri_factors', {})
            r_material = factors.get('material', {}).get(material_key, 1.0)
            r_coolant  = factors.get('coolant', {}).get(coolant_mode, 1.0)
            r_tool     = factors.get('tool', {}).get(tool_mat_key, 1.0)
            
        return r_depth * r_material * r_coolant * r_tool

    @staticmethod
    def select_strategy(dri):
        """依據 DRI 指數判定加工策略"""
        if dri < 6:
            return "DIRECT"       # 低風險：無啄鑽
        elif dri < 18:
            return "Q_MODE"       # 中風險：固定 Peck
        elif dri < 40:
            return "IJK_DYNAMIC"  # 高風險：動態遞減 Peck
        else:
            return "DEEP_PROTECT" # 極高風險：深孔保護模式

    @staticmethod
    def calc_dynamic_pecks(i_val, k_val, target_depth, power=0.6):
        """使用冪次衰減模型生成動態 Peck 序列"""
        pecks = []
        current_depth = 0.0
        last_peck = i_val
        
        while current_depth < target_depth - 1e-6:
            # 衰減因子
            decay = 1.0 - (current_depth / target_depth) ** power
            peck = k_val + (i_val - k_val) * decay
            
            # 安全限制：確保單調遞減 (Monotonicity) 且不低於最小值
            peck = max(peck, k_val)
            peck = min(peck, last_peck)
            
            # 若剩餘深度不足一跳，則直達孔底
            if current_depth + peck > target_depth:
                peck = target_depth - current_depth
                
            pecks.append({'I': -round(peck, 4)}) # 使用負值表示下鑽增量
            current_depth += peck
            last_peck = peck
            
        return pecks

    @staticmethod
    def estimate_tool_life_index(vc_adj, vc_ref, tool_mat_key, ld_ratio, feed_ratio=1.0, config=None):
        """
        計算相對刀具壽命指標 (Tool Life Index)。
        基於 Taylor 公式修正。
        """
        n = 0.22 if tool_mat_key == 'CARBIDE' else 0.10
        if config:
            n = config.data.get('taylor_params', {}).get(tool_mat_key, {}).get('n', n)
            
        # [V6.0] 速度因素 (與材質基準速度對比，語味化修正)
        # LifeFactor = (V_ref / V_c)^(1/n)
        life_factor = (vc_ref / vc_adj) ** (1.0 / n) if vc_adj > 0 else 0
        
        # 2. 深度懲罰 (熱累積)
        depth_penalty = 1.0 / (1.0 + 0.08 * (ld_ratio ** 1.3))
        
        # 3. 進給過載懲罰
        # 假設 feed_ratio > 1.0 代表過載
        load_penalty = (1.0 / feed_ratio) ** 0.4 if feed_ratio > 0 else 0
        
        return life_factor * depth_penalty * load_penalty

    @staticmethod
    def get_ld_sens_ijk(diameter, ld_ratio):
        """基於長徑比 L/D 計算感應式 I, J, K 基礎值 (V6.0 穩定性限制版)"""
        r_eff = min(ld_ratio, 10.0) # [V6.0] 防止極深孔導致線性項崩壞
        r = r_eff
        # I(R) = D * (1.2 - 0.08R), 限制 0.4D ~ 1.2D
        i_factor = max(0.4, min(1.2, 1.2 - 0.08 * r))
        # J(R) = D * (0.18 - 0.01R), 限制 0.04D ~ 0.18D
        j_factor = max(0.04, min(0.18, 0.18 - 0.01 * r))
        # K(R) = D * (0.25 - 0.01R), 限制 0.08D ~ 0.25D
        k_factor = max(0.08, min(0.25, 0.25 - 0.01 * r))
        
        return (round(diameter * i_factor, 3), 
                round(diameter * j_factor, 3), 
                round(diameter * k_factor, 3))

    @classmethod
    def get_default_ijk(cls, diameter, mode='efficient', config=None):
        """
        整合比例比例常數法計算 G83 I/J/K 建議值。
        """
        if diameter <= 0.0001:
            return 0.0, 0.0, 0.0
            
        if config:
            ratios = config.get_ijk_ratios(mode)
            i_ratio = ratios.get('i_ratio', 1.0)
            j_ratio = ratios.get('j_ratio', 0.1)
            k_ratio = ratios.get('k_ratio', 0.3)
        else:
            # 原始寫死的預設值 (作為備援)
            strategies = {
                'safety':    {'i_ratio': 0.8, 'j_ratio': 0.1,  'k_ratio': 0.25},
                'efficient': {'i_ratio': 1.1, 'j_ratio': 0.12, 'k_ratio': 0.35},
                'deep_hole': {'i_ratio': 0.6, 'j_ratio': 0.05, 'k_ratio': 0.15}
            }
            c = strategies.get(mode, strategies['efficient'])
            i_ratio, j_ratio, k_ratio = c['i_ratio'], c['j_ratio'], c['k_ratio']

        # [專業修正] I = 初始進刀, J = 每次遞減量, K = 最小進刀量
        i_val = round(diameter * i_ratio, 3)
        j_val = round(diameter * j_ratio, 3)
        k_val = round(diameter * k_ratio, 3)

        return i_val, j_val, k_val

    @classmethod
    def calculate_optimized_params(cls, 
                                   tool_dia, 
                                   target_z, 
                                   material_key, 
                                   tool_mat_key, 
                                   max_rpm=40000, 
                                   current_s=0.0,
                                   material_thickness=0.0,
                                   exit_chamfer=0.0,
                                   tip_angle=118.0,
                                   config=None,
                                   coolant_mode="MQL",
                                   prefer_ijk=None):
        """計算最佳化切削參數 (進階工業模型版)"""
        result = {
            'S': 0.0, 'F': 0.0, 'Q': 0.0, 
            'I': 0.0, 'J': 0.0, 'K': 0.0, 'Z': target_z,
            'use_ijk': False, 'messages': [],
            'dri': 0.0, 'strategy': '', 'life_index': 0.0, 'score': 0.0
        }
        
        if tool_dia <= 0:
            result['messages'].append("錯誤：刀具直徑必須大於 0")
            return result
            
        depth = abs(target_z)
        ld_ratio = depth / tool_dia
        
        # 0. 取得基礎配置
        if config:
            mat_data = config.get_material_data(material_key)
            max_rpm = config.get_limit('max_rpm') or max_rpm
        else:
            mat_data = {'Vc': 50.0, 'fr_factor': 0.01} # 預留降級處置
            
        TOOL_MATERIALS = {
            'CARBIDE': {'speed_ratio': 1.0, 'feed_ratio': 1.0},
            'HSS':     {'speed_ratio': 0.4, 'feed_ratio': 0.8}
        }
        tool_data = TOOL_MATERIALS.get(tool_mat_key, TOOL_MATERIALS['CARBIDE'])
        
        # 1. 幾何感知修正 (倒角)
        if exit_chamfer > 0 and tip_angle > 0:
            half_angle_rad = math.radians(tip_angle / 2.0)
            extra_depth = (exit_chamfer / 2.0) / math.tan(half_angle_rad)
            calculated_z = - (material_thickness + extra_depth + 0.2)
            if calculated_z < target_z:
                result['Z'] = round(calculated_z, 4)
                depth = abs(result['Z'])
                ld_ratio = depth / tool_dia
                result['messages'].append(f"幾何感知：自動補償 Z 深度至 {result['Z']} (含倒角)")

        # 2. DRI 風險評估與戰略選取
        dri = cls.calculate_dri(tool_dia, depth, material_key, coolant_mode, tool_mat_key, config)
        strategy = cls.select_strategy(dri)
        result['dri'] = round(dri, 1)
        result['strategy'] = strategy
        result['messages'].append(f"風險評估：DRI={result['dri']} (戰略: {strategy})")
        
        # 3. 轉速與進給計算 (含二階深度修正)
        coolant_factor = 1.0
        if config:
            coolant_factor = config.data.get('coolant_factors', {}).get(coolant_mode, 1.0)
            
            
        vc_ref = mat_data['Vc'] * tool_data['speed_ratio']
        vc_base = vc_ref * coolant_factor
        # [V6.0] 隨長徑比調整 RPM 與 Feed，修正系數優化為 0.035
        rpm_adj_factor = 1.0 / (1.0 + 0.035 * ld_ratio)
        feed_adj_factor = 1.0 / (1.0 + 0.02 * ld_ratio)
        
        vc_final = vc_base * rpm_adj_factor
        
        if current_s > 0:
            s_target = current_s
            result['messages'].append(f"模式：固定轉速 {int(s_target)} RPM")
        else:
            s_calc = (vc_final * 1000) / (math.pi * tool_dia)
            s_target = min(s_calc, max_rpm)
            if s_calc > max_rpm: result['messages'].append(f"機台限制：轉速已截斷至上限 {int(max_rpm)}")
            result['messages'].append(f"深度修正：S 修正係數 {round(rpm_adj_factor, 2)}")
            
        result['S'] = round(s_target, 0)
        
        # 進給計算
        fr_base = mat_data['fr_factor'] * tool_dia * tool_data['feed_ratio']
        # 微鑽保護 (額外疊加)
        micro_threshold = 1.0
        micro_penalty = 0.8
        if config:
            micro_threshold = config.data.get('limits', {}).get('micro_drill_threshold', 1.0)
            micro_penalty = config.data.get('limits', {}).get('micro_drill_penalty', 0.8)
            
        if tool_dia < micro_threshold:
            fr_base *= micro_penalty
            result['messages'].append(f"微鑽保護：F 加乘 {micro_penalty}")
            
        f_calc = s_target * (fr_base * feed_adj_factor)
        result['F'] = round(f_calc, 1)
        if ld_ratio > 3: result['messages'].append(f"深度修正：F 修正係數 {round(feed_adj_factor, 2)}")

        # 4. 啄鑽決策應用 (尊重手動鎖定)
        # 決定最終模式：若使用者有明確偏好 (prefer_ijk)，則鎖定該模式
        final_use_ijk = result['use_ijk'] = prefer_ijk if prefer_ijk is not None else (strategy in ["IJK_DYNAMIC", "DEEP_PROTECT"])
        
        # 即使被鎖定，仍需發出風險警告
        if not final_use_ijk and strategy in ["IJK_DYNAMIC", "DEEP_PROTECT"]:
            result['messages'].append(f"警告：當前 DRI={result['dri']} 風險較高，強烈建議手動開啟 IJK 模式")
        
        if not final_use_ijk:
            # 強制進入 Q 模式或無啄鑽
            if strategy == "DIRECT" and dri < 4: 
                result['Q'] = 0.0
            else:
                q_val = tool_dia * 0.8
                min_q = config.get_limit('min_q') if config else 0.05
                result['Q'] = round(max(q_val, min_q), 4)
        else:
            # 進入 IJK 模式
            i, j, k = cls.get_ld_sens_ijk(tool_dia, ld_ratio)
            if strategy == "DEEP_PROTECT":
                i *= 0.8; k *= 0.8
                result['messages'].append("保護模式：額外縮減 Peck 深度")
            result['I'], result['J'], result['K'] = i, j, k
            
        # 5. 壽命預估 (V6.0 $V_{ref}$ 對齊)
        life_idx = cls.estimate_tool_life_index(vc_final, vc_ref, tool_mat_key, ld_ratio, feed_ratio=feed_adj_factor, config=config)
        result['life_index'] = round(life_idx, 2)
        
        # 6. 綜合評分 (時間與壽命權重)
        # 簡化評分：100 / (估計時間 * 0.7 + (1/壽命) * 0.3)
        # 此處僅作為 UI 展示提示傾向
        result['score'] = round(100.0 * (0.7 * (1.0/max(0.1, ld_ratio)) + 0.3 * (life_idx/1000.0)), 1)
        
        return result
