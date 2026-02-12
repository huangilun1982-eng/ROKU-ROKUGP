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
    def get_default_ijk(diameter, mode='efficient'):
        """
        整合全新比例比例常數法計算 G83 I/J/K 建議值。
        適用於 0.3mm ~ 0.8mm 微小徑鑽孔 (鋁合金 6061)。
        """
        if diameter <= 0.0001:
            return 0.0, 0.0, 0.0
            
        # 定義不同策略的比例常數 (以直徑 D 為基準)
        strategies = {
            'safety': {
                'i_ratio': 0.8,
                'j_ratio': 0.1,
                'k_ratio': 0.25
            },
            'efficient': {
                'i_ratio': 1.1,   # 提高首跳深度提升效率
                'j_ratio': 0.12,  # 適度遞減
                'k_ratio': 0.35   # 維持較大的底限以防熔焊
            },
            'deep_hole': {        # 針對 L/D > 10 的情況
                'i_ratio': 0.6,
                'j_ratio': 0.05,
                'k_ratio': 0.15
            }
        }

        # 取得選定策略，預設為 efficient
        config = strategies.get(mode, strategies['efficient'])

        # 計算數值並捨入處理 (對應機台解析度 1 微米)
        i_val = round(diameter * config['i_ratio'], 3)
        j_val = round(diameter * config['j_ratio'], 3)
        k_val = round(diameter * config['k_ratio'], 3)

        return i_val, j_val, k_val
