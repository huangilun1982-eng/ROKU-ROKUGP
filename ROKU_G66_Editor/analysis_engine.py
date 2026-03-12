import math

class DrillingAnalysisEngine:
    """
    專門處理加工效率分析與時間預估的邏輯引擎。
    將邏輯與 UI 分離。
    """
    
    @staticmethod
    def _precision_for_dia(diameter):
        """依刀徑決定適當的小數位精度 (位數)"""
        return 3 if diameter < 0.5 else 2

    @staticmethod
    def interpolate_base_life(diameter, mat_config_dict):
        """
        以對數插值計算基準壽命，取代區塊式分類。
        mat_config_dict 為字典，例如 {"nano": 5.0, "micro": 20.0, ...}
        """
        import math
        # 定義錨點直徑
        anchors = [
            (0.2, mat_config_dict.get('nano', 5.0)),
            (1.0, mat_config_dict.get('micro', 20.0)),
            (3.0, mat_config_dict.get('small', 50.0)),
            (6.0, mat_config_dict.get('medium', 100.0)),
            (12.0, mat_config_dict.get('large', 150.0))
        ]
        
        d_safe = max(0.01, diameter)
        log_d = math.log10(d_safe)
        
        if d_safe <= anchors[0][0]:
            return float(anchors[0][1])
        if d_safe >= anchors[-1][0]:
            return float(anchors[-1][1])
            
        for i in range(len(anchors) - 1):
            d1, v1 = anchors[i]
            d2, v2 = anchors[i+1]
            if d1 <= d_safe <= d2:
                # 對數線性插值
                t = (log_d - math.log10(d1)) / (math.log10(d2) - math.log10(d1))
                return float(v1 + t * (v2 - v1))
        return float(anchors[-1][1])
    
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
        
        # [FIX-8] 統一為單一啄鑽時間計算邏輯 (G83 專用)
        # G66 P9131 時間預估使用 calc_g66_drilling_time()
        for idx, peck in enumerate(ijk_list):
            # peck['I'] 是當次下鑽的增量深度 (通常為負值)
            increment = peck.get('I', 0.0)
            prev_z = current_z
            target_z = prev_z + increment
            
            if idx == 0:
                # 第一跳：從 R 點一路進給進刀
                feed_dist = abs(target_z - r_point)
                total_t += feed_dist / feedrate
            else:
                # 後續跳：快速回到 (上次深度 + 間隙)，再進給進刀
                dist_g0_down = abs(r_point - (prev_z + clearance))
                total_t += dist_g0_down / g0_speed
                feed_dist = abs(target_z - (prev_z + clearance))
                total_t += feed_dist / feedrate
            
            # 孔底快速退回 R
            dist_g0_up = abs(target_z - r_point)
            total_t += dist_g0_up / g0_speed
            
            current_z = target_z
            
        return total_t

    @classmethod
    def compare_efficiency(cls, current_params, initial_params, cycle_type='G83', g0_speed=5000):
        """
        比較兩組參數的加工效率 (支援 G83 與 G66)。
        
        Args:
            current_params (dict): 參數字典 (G83: {ijk_list, feedrate, r_point, is_ijk_mode}, G66: {segments, r_point})
            initial_params (dict): 初始參數字典
            cycle_type (str): 'G83' 或 'G66'
            g0_speed (float): 機台快速速度
            
        Returns:
            dict: {save_pct, init_pecks, curr_pecks, init_time, curr_time}
        """
        if cycle_type == 'G66':
            curr_segs = current_params.get('segments', [])
            init_segs = initial_params.get('segments', [])
            curr_r = current_params.get('r_point', 0.0)
            init_r = initial_params.get('r_point', 0.0)
            
            curr_t = cls.calc_g66_drilling_time(curr_segs, curr_r, g0_speed)
            init_t = cls.calc_g66_drilling_time(init_segs, init_r, g0_speed)
            
            # G66 實質刀數: 將每一段深度除以 J 數值向上取整的總和
            def count_g66_pecks(segs, r_pt):
                count = 0
                prev_z = r_pt
                for seg in segs:
                    seg_z, seg_q = seg['I'], abs(seg['J'])
                    if seg_q > 1e-6:
                        count += max(1, math.ceil(abs(seg_z - prev_z) / seg_q))
                    prev_z = seg_z
                return count
                
            curr_pecks = count_g66_pecks(curr_segs, curr_r)
            init_pecks = count_g66_pecks(init_segs, init_r)
        else:
            curr_t = cls.calc_drilling_time(
                current_params['ijk_list'], 
                current_params['feedrate'], 
                current_params['r_point'], 
                g0_speed, 
                current_params['is_ijk_mode']
            )
            
            init_t = cls.calc_drilling_time(
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
    def calc_g83_dynamic_pecks(i_val, k_val, target_depth, power=0.6):
        """[G83 專用] 使用冪次衰減模型生成動態 Peck 序列"""
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
    def estimate_tool_life_index(vc_adj, vc_ref, tool_mat_key, ld_ratio, feed_ratio=1.0, config=None, coolant_factor=1.0, use_ijk=False, taylor_n=None):
        """
        計算相對刀具壽命指標 (Tool Life Index)。
        基於 Taylor 公式修正，結果 clamp 在 [0, 10.0] 範圍內。
        """
        # 使用傳入的 taylor_n 或從配置讀取
        n = taylor_n
        if n is None:
            n = 0.22 if tool_mat_key == 'CARBIDE' else 0.10
            if config:
                n = config.data.get('taylor_params', {}).get(tool_mat_key, {}).get('n', n)
            
        # 1. 速度因素
        effective_vc_ref = vc_ref * coolant_factor
        life_factor = (effective_vc_ref / vc_adj) ** (1.0 / n) if vc_adj > 0 else 0
        
        # 2. 深度懲罰 (熱累積)
        depth_penalty_severity = 0.08
        if use_ijk and ld_ratio > 3:
            depth_penalty_severity = 0.04
        depth_penalty = 1.0 / (1.0 + depth_penalty_severity * (ld_ratio ** 1.3))
        
        # 3. 進給過載懲罰
        load_penalty = (1.0 / feed_ratio) ** 0.4 if feed_ratio > 0 else 0
        
        raw_index = life_factor * depth_penalty * load_penalty
        
        # [L1 修復] 物理上限 clamp：Taylor 公式在速度比過大時指數爆炸，
        # 實際壽命不可能無限延長（振動、排屑、磨損等其他失效模式會接管）
        # 上限 10.0 = 最優條件下也不超過基準壽命的 10 倍
        return min(raw_index, 10.0)

    @staticmethod
    def get_ld_sens_ijk(diameter, ld_ratio, material_key='SUS420', coolant_factor=1.0, config=None):
        """基於長徑比 L/D 與前置條件計算感應式 I, J, K 基礎值 (V6.2 高效首鑽版)"""
        r_eff = min(ld_ratio, 10.0)
        r = r_eff
        
        # 依據材質排屑性能取得修正係數 (預設 SUS420 為 1.0，AL6061 可能為 1.3)
        mat_factor = 1.0
        if config:
            mat_factor = config.data.get('peck_factors', {}).get(material_key, 1.0)
            
        # 綜合環境紅利 (排屑越好、冷卻越佳 -> 第一刀可以越深)
        env_bonus = mat_factor * coolant_factor
        
        # [V6.4] 基準首鑽倍數 (受環境紅利加成，但受刀徑分級天花板約束)
        base_i_mult = 2.0 * env_bonus
        # I 倍數隨深孔遞減 (每增 1 倍 L/D，倍數降 0.1)
        i_factor = max(0.5, min(base_i_mult, base_i_mult - 0.1 * r))
        
        # [連續型分級] 安全天花板：依 log10(D) 計算最大允許 I 倍數平滑曲線
        # 基準：D=1.0 時為 2.0D，每增/跌 10 倍直徑增加/減少 1.0D
        max_i_mult = 2.0 + 1.0 * math.log10(max(0.05, diameter))
        max_i_mult = max(0.8, min(3.0, max_i_mult))
        
        # 實際 I 值 = min(演算法算出值, 刀徑分級天花板)
        i_val_raw = diameter * i_factor
        i_val_capped = min(i_val_raw, diameter * max_i_mult)
        
        # J 遞減量保持平滑
        j_factor = max(0.02, min(0.15, 0.15 - 0.005 * r))
        # K 保底深度受冷卻加持
        # [連續型分級] K 最低保障：對數平滑曲線 (D=1.0 時為 0.4D)
        k_floor = 0.4 - 0.2 * math.log10(max(0.05, diameter))
        k_floor = max(0.2, min(0.6, k_floor))
        k_factor = max(k_floor, min(0.60 * env_bonus, 0.50 * env_bonus - 0.015 * r))
        
        # 依刀徑決定回傳精度
        prec = 3 if diameter < 0.5 else 2
        
        return (round(i_val_capped, prec), 
                round(diameter * j_factor, prec), 
                round(diameter * k_factor, prec))

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

    # =========================================================================
    # G66 P9131 專用方法
    # =========================================================================
    # 重要：G66 P9131 的 I/J/K 語意與 G83 的 I/J/K 完全不同！
    #
    # ┌──────────┬──────────────────────┬──────────────────────┐
    # │ 參數     │ G66 P9131 語意       │ G83 語意             │
    # ├──────────┼──────────────────────┼──────────────────────┤
    # │ I        │ 分段切換 Z 座標位置  │ 初始啄鑽深度         │
    # │ J        │ 該段啄鑽量 (Q)       │ 每次遞減量           │
    # │ K        │ 該段進給速度 (F)     │ 最小啄鑽深度         │
    # └──────────┴──────────────────────┴──────────────────────┘
    #
    # P9131 格式：G65 P9131 R Z (S) I1 J1 K1 ~ I4 J4 K4 (T)
    # 最多 4 組，每組定義一個獨立加工分段。
    # =========================================================================

    @classmethod
    def calc_g66_segments(cls, tool_dia, target_z, base_feed, strategy='IJK_DYNAMIC',
                          config=None, material_key='SUS420', preset='balanced'):
        """
        [G66 P9131 專用] 根據深度、材質與預設檔計算分段鑽孔參數。
        
        改進 1：首段加速、深段減速的進給策略
        改進 2：材質感知的啄鑽深度係數
        改進 4：差比數列動態分段比例
        改進 5：預設檔修正係數
        """
        total_depth = abs(target_z)
        if total_depth < 1e-6 or tool_dia <= 0:
            return []
        
        ld_ratio = total_depth / tool_dia
        
        # --- 讀取預設檔係數 [改進 5] ---
        preset_data = {'peck_mult': 1.0, 'feed_mult': 1.0, 'seg_adj': 0}
        if config:
            preset_data = config.data.get('optimization_presets', {}).get(preset, preset_data)
        
        # --- 1. 決定分段數量 (依長徑比，最多 4 段) ---
        if ld_ratio <= 2.0:
            num_segments = 1
        elif ld_ratio <= 5.0:
            num_segments = 2
        elif ld_ratio <= 8.0:
            num_segments = 3
        else:
            num_segments = 4  # P9131 上限
        
        # 保護模式額外增加一段 (但不超過 4)
        if strategy == 'DEEP_PROTECT' and num_segments < 4:
            num_segments += 1
        
        # [改進 5] 預設檔調整段數
        num_segments = max(1, min(4, num_segments + preset_data.get('seg_adj', 0)))
        
        # --- 2. 計算每段的 Z 座標位置 (I 值) [改進 4：差比數列] ---
        if num_segments == 1:
            ratios = [1.0]
        else:
            # 讀取材質專屬公比，易切削材質公比大 → 首段更長
            common_ratio = 0.70  # 預設
            if config:
                common_ratio = config.data.get('segment_common_ratios', {}).get(material_key, 0.70)
            raw = [common_ratio ** i for i in range(num_segments)]
            total = sum(raw)
            ratios = [r / total for r in raw]  # 歸一化
        
        # 累積計算每段的 Z 位置
        z_positions = []
        cumulative = 0.0
        for r in ratios:
            cumulative += total_depth * r
            z_positions.append(-round(cumulative, 4))
        # 最後一段強制對齊 target_z，避免浮點誤差
        z_positions[-1] = round(target_z, 4)
        
        # --- 3. 計算每段的啄鑽量 (J 值) [改進 2：材質感知] ---
        peck_material_factor = 1.0
        if config:
            peck_material_factor = config.data.get('peck_factors', {}).get(material_key, 1.0)
        
        base_peck = tool_dia * 0.8 * peck_material_factor * preset_data.get('peck_mult', 1.0)
        if strategy == 'DEEP_PROTECT':
            base_peck *= 0.7  # 保護模式縮減
        
        # 限制啄鑽量：不超過該段深度，不低於 0.05mm
        min_peck = max(0.05, tool_dia * 0.1)
        
        # --- 4. 計算每段的進給速度 (K 值) [改進 1：首段加速策略] ---
        feed_preset_mult = preset_data.get('feed_mult', 1.0)
        
        segments = []
        for i in range(num_segments):
            # [改進 1] 首段定心減速 (Center drilling effect)、深段保護減速
            if num_segments == 1:
                feed_factor = 1.0
            elif i == 0:
                feed_factor = 0.85   # 首段：降低軸向推力，確保定心不偏擺
            elif i < num_segments - 1:
                feed_factor = 1.0    # 中段：孔壁導引穩定，全速推進
            else:
                feed_factor = 0.80   # 末段：深孔保護，避免孔底積屑研磨
            
            # 深度衰減係數：越深的段，啄鑽量越低
            peck_decay = 1.0 - (i / max(num_segments, 1)) * 0.4
            
            # J：該段啄鑽量
            seg_depth = total_depth * ratios[i]
            peck = round(max(min_peck, min(base_peck * peck_decay, seg_depth)), 4)
            
            # --- [新增] 諧波對齊優化 ---
            # 針對 G66 的每一個分段單獨做整除對齊 (最多往下微調 15%)
            peck = cls._optimize_harmonic_peck(
                target_depth=abs(z_positions[i] - (z_positions[i-1] if i > 0 else 0)),
                current_peck=peck,
                min_allowable_peck=peck * 0.85
            )
            
            # K：該段進給速度 = 基礎進給 × 段位係數 × 預設檔係數
            feed = round(base_feed * feed_factor * feed_preset_mult, 1)
            
            segments.append({
                'I': z_positions[i],   # Z 座標位置 (絕對值，負數)
                'J': peck,             # 每次啄鑽量
                'K': feed              # 進給速度
            })
        
        return segments

    @staticmethod
    def calc_g66_drilling_time(segments, r_point, g0_speed=5000, clearance=0.1):
        """
        [改進 3] G66 P9131 專用時間預估。
        每段：快速下壓 → 在段內進行多次啄鑽 → 退刀至 R。
        
        Args:
            segments: [{'I': z_pos, 'J': peck_amount, 'K': feed_rate}, ...]
            r_point: R 安全點 Z 座標
            g0_speed: 快速移動速度 (mm/min)
            clearance: 啄鑽間雙 (mm)
        
        Returns:
            float: 預估加工時間 (minutes)
        """
        if not segments or g0_speed <= 0:
            return 0.0
        
        total_t = 0.0
        prev_seg_end = r_point  # 起始點
        
        for seg in segments:
            seg_z = seg['I']       # 段終點 Z
            seg_q = abs(seg['J'])  # 啄鑽量
            seg_f = seg['K']       # 進給速度
            
            if seg_q < 1e-6 or seg_f < 1e-6:
                continue
            
            seg_depth = abs(seg_z - prev_seg_end)
            num_pecks = max(1, math.ceil(seg_depth / seg_q))
            
            current_z = prev_seg_end
            for p in range(num_pecks):
                peck_end = max(current_z - seg_q, seg_z) if seg_z < current_z else min(current_z + seg_q, seg_z)
                actual_peck = abs(peck_end - current_z)
                
                if p == 0:
                    # 段內首跳：從 R 點進給下壓
                    total_t += abs(current_z - r_point) / g0_speed  # 快速接近
                    total_t += actual_peck / seg_f                   # 進給切削
                else:
                    # 段內後續跳：退到 R → 快速接近 → 進給切削
                    total_t += abs(current_z - clearance - r_point) / g0_speed  # 快速接近
                    total_t += (actual_peck + clearance) / seg_f                # 進給切削
                
                # 退刀至 R
                total_t += abs(peck_end - r_point) / g0_speed
                current_z = peck_end
            
            prev_seg_end = seg_z
        
        return total_t

    @staticmethod
    def _optimize_harmonic_peck(target_depth, current_peck, min_allowable_peck, precision=2):
        """
        微調最佳化 (Efficiency Optimization)：往下尋找在「不增加總加工次數」前提下，
        最小的 Q 或 J 值，以達到最高加工效率 (減少每次空行程回刀的累積總和)。
        
        Args:
            target_depth: 該段要鑽的總深度 (絕對值)，如 G83 應為 Z 扣除 R 的距離。
            current_peck: AI 算出來的初始單次啄鑽量 (Q 或是 J)
            min_allowable_peck: 允許縮小到的底線 (通常是不低於原始值的 85%)
            precision: 機台與 GUI 輸入框的小數點精度限制 (預設為 2)
        
        Returns:
            float: 最佳化後、符合精度限制的最小啄鑽量。若找不到更優值則回傳原本的數值。
        """
        if current_peck <= 0 or target_depth <= 0:
            return current_peck
            
        # 若本來就大於總深，代表一刀到底，不需要優化
        if current_peck >= target_depth:
            return round(target_depth, precision)
            
        # 1. 計算用當前深度需要幾次 (採無條件進位)
        n_steps = math.ceil(target_depth / current_peck)
        
        # 2. 如果不變刀數，數學上每一刀的完美除數是多少
        exact_min_peck = target_depth / n_steps
        
        # 3. 礙於機台或 GUI 精度限制，若遇到無法除盡或過長的小數會被捨去，導致不足以鑽完而多出一刀(效率大跌)
        # 所以對最佳數值進行精度上的無條件「進位」(Ceiling)。
        # 這樣即可得出：在該精度下，能夠用 n_steps 鑽完的「最小可行 Q 值」
        multiplier = 10.0 ** precision
        best_peck = math.ceil(exact_min_peck * multiplier) / multiplier
        
        # 4. 如果算出來的 best_peck 能縮小深度且沒有越過最小安全界線，就採納
        if best_peck < current_peck and best_peck >= min_allowable_peck:
            return best_peck
            
        return current_peck

    @classmethod
    def calculate_optimized_params(cls, 
                                   tool_dia, 
                                   target_z, 
                                   material_key='SUS304', 
                                   tool_mat_key='CARBIDE', 
                                   max_rpm=40000, 
                                   current_s=0.0,
                                   material_thickness=0.0,
                                   exit_chamfer=0.0,
                                   tip_angle=118.0,
                                   config=None,
                                   coolant_mode="Oil",
                                   prefer_ijk=None,
                                   preset='balanced',
                                   taylor_n=None):
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
        # [L3 修復] 微鑽切速修正：D<1mm 時，教科書的參考切速是給大直徑鑽頭用的
        # 微鑽散熱差、振動大，最佳切速要大幅折減
        if tool_dia < 1.0:
            micro_vc_factor = max(0.3, tool_dia)  # D=0.65 → ×0.65, D=0.1 → ×0.3
            vc_ref *= micro_vc_factor
            result['messages'].append(f"微鑽修正：參考切速折減至 {round(vc_ref, 1)} m/min (×{micro_vc_factor:.2f})")
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
        
        # [P1 修復] 進給計算：coolant 已透過 S 間接影響，此處不再重複乘入
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
        
        # [新增] 最低每轉進給率 (Min Feed per Tooth) 保障
        # 避免 F 過低導致「只有摩擦沒有切削」而產生加工硬化 (特別針對不鏽鋼)
        min_feed_per_rev = max(0.01, tool_dia * 0.01)  # 直徑的 1%，保底 0.01 mm/rev
        f_rev = f_calc / s_target if s_target > 0 else 0
        if f_rev < min_feed_per_rev and s_target > 0:
            f_calc = s_target * min_feed_per_rev
            result['messages'].append(f"進給保障：F 強制提升 (避免加工硬化)，每轉進給為 {min_feed_per_rev:.3f} mm/rev")
            
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
                # [P4 修復] Q 模式導入材質排屑因子 (peck_factors)
                peck_mat_factor = 1.0
                if config:
                    peck_mat_factor = config.data.get('peck_factors', {}).get(material_key, 1.0)
                q_val = tool_dia * 0.8 * peck_mat_factor
                
                # [連續型分級] Q 分級天花板平滑對數曲線 (D=1.0 時為 1.5D)
                max_q_mult = 1.5 + 1.0 * math.log10(max(0.05, tool_dia))
                max_q_mult = max(0.5, min(2.5, max_q_mult))
                q_val = min(q_val, tool_dia * max_q_mult)
                
                min_q = config.get_limit('min_q') if config else 0.05
                q_val = max(q_val, min_q)
                
                # [B 修復] 精度隨刀徑調整
                prec = cls._precision_for_dia(tool_dia)
                
                # --- [新增] 諧波對齊優化 ---
                # 在 G83 Q 模式，找尋能否整除總深度
                optimized_q = cls._optimize_harmonic_peck(
                    target_depth=depth, 
                    current_peck=q_val, 
                    min_allowable_peck=q_val * 0.85,
                    precision=prec
                )
                if optimized_q < q_val:
                    result['messages'].append(f"諧波對齊：Q 值由 {round(q_val, prec)} 微調至 {optimized_q} (除盡空行程)")
                
                result['Q'] = round(optimized_q, prec)
        else:
            # 進入 IJK 模式
            # --- G83 專用：計算初始/遞減/最小值 ---
            i, j, k = cls.get_ld_sens_ijk(
                diameter=tool_dia, 
                ld_ratio=ld_ratio,
                material_key=material_key,
                coolant_factor=coolant_factor,
                config=config
            )
            # 冷卻影響已在 get_ld_sens_ijk 內考量，這裡不重複疊加
            if strategy == "DEEP_PROTECT":
                i *= 0.8; k *= 0.8
                result['messages'].append("保護模式：額外縮減 Peck 深度")
            result['I'], result['J'], result['K'] = i, j, k
            
            # --- G66 P9131 專用：計算分段列表 ---
            # 注意：G66 的 IJK 語意與上面的 G83 完全不同！
            # G66 I=Z位置, J=啄鑽量, K=進給速度
            result['g66_segments'] = cls.calc_g66_segments(
                tool_dia=tool_dia,
                target_z=target_z,
                base_feed=result['F'],
                strategy=strategy,
                config=config,
                material_key=material_key,
                preset=preset
            )
            
        # 5. 壽命預估 (V6.0 $V_{ref}$ 對齊)
        # [修復] 必須使用實際的運作切削速度 (vc_actual)，而不只是演算法中途算出的 vc_final
        actual_vc = (s_target * math.pi * tool_dia) / 1000.0
        life_idx = cls.estimate_tool_life_index(
            vc_adj=actual_vc, 
            vc_ref=vc_ref, 
            tool_mat_key=tool_mat_key, 
            ld_ratio=ld_ratio, 
            feed_ratio=feed_adj_factor, 
            config=config, 
            coolant_factor=coolant_factor,
            use_ijk=final_use_ijk,
            taylor_n=taylor_n
        )
        result['life_index'] = round(life_idx, 2)
        
        # 針對 IJK 模式添加系統提醒
        if final_use_ijk and ld_ratio > 3:
            result['messages'].append("保護模式：啟用 IJK 動態啄鑽，深孔壽命獲得提昇")
        
        # 6. 綜合評分 (時間與壽命權重)
        # 簡化評分：100 / (估計時間 * 0.7 + (1/壽命) * 0.3)
        # 此處僅作為 UI 展示提示傾向
        result['score'] = round(100.0 * (0.7 * (1.0/max(0.1, ld_ratio)) + 0.3 * (life_idx/1000.0)), 1)
        
        return result
