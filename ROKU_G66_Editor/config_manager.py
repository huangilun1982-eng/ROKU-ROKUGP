
import json
import os
import copy

class ConfigManager:
    """
    管理切削參數優化邏輯的設定檔讀取與儲存。
    """
    DEFAULT_CONFIG = {
        "materials": {
            "AL6061": {"Vc": 100.0, "fr_factor": 0.015, "desc": "鋁合金 6061 (Aluminum)"},
            "SUS304": {"Vc": 25.0,  "fr_factor": 0.008, "desc": "不鏽鋼 304 (Stainless)"},
            "SUS420": {"Vc": 35.0,  "fr_factor": 0.009, "desc": "不鏽鋼 420J2 (Stainless)"},
            "TI6AL4V":{"Vc": 18.0,  "fr_factor": 0.006, "desc": "鈦合金 (Titanium)"},
            "CERAMIC":{"Vc": 15.0,  "fr_factor": 0.003, "desc": "工程陶瓷 (Ceramic)"}
        },
        'coolant_factors': {
            'Oil': 1.2, 'Air': 0.8,
            'Internal': 1.1,   # 內冷：建議 Vc x 1.1 (保守值)
            'Dry': 0.6         # 乾式：建議 Vc x 0.6
        },
        'ijk_strategies': {
            'safety':    {'i_ratio': 0.5, 'j_ratio': 0.1, 'k_ratio': 0.2}, # J 為遞減量比率
            'efficient': {'i_ratio': 0.8, 'j_ratio': 0.15, 'k_ratio': 0.3},
            'deep_hole': {'i_ratio': 0.4, 'j_ratio': 0.05, 'k_ratio': 0.1}
        },
        'limits': {
            'max_rpm': 40000.0,
            'min_q': 0.05,
            'micro_drill_threshold': 1.0,
            'micro_drill_penalty': 0.8
        },
        'dri_factors': {
            'material': {
                'AL6061': 0.8, 'SUS304': 1.4, 'SUS420': 1.2, 'TI6AL4V': 1.6, 'CERAMIC': 2.0
            },
            'coolant': {
                'Oil': 0.8, 'Air': 1.3
            },
            'tool': {
                'CARBIDE': 0.9, 'HSS': 1.4
            }
        },
        'taylor_params': {
            'CARBIDE': {'n': 0.22},
            'HSS': {'n': 0.10}
        },
        'optimization_weights': {
            'time': 0.7,
            'life': 0.3
        },
        # [改進 2] 材質感知啄鑽修正係數：排屑容易的材質可增大啄鑽量
        'peck_factors': {
            'AL6061': 1.3,    # 鋁合金：排屑流暢
            'SUS304': 0.9,    # 不鏽鋼 304
            'SUS420': 1.0,    # 不鏽鋼 420J2（基準）
            'TI6AL4V': 0.7,   # 鈦合金：黏性高
            'CERAMIC': 0.5    # 陶瓷：脆性材料
        },
        # [改進 4] 分段公比：控制 G66 各段長度比例 (易切削→首段更長)
        'segment_common_ratios': {
            'AL6061': 0.80,
            'SUS304': 0.70,
            'SUS420': 0.72,
            'TI6AL4V': 0.65,
            'CERAMIC': 0.55
        },
        # [改進 5] 優化預設檔：效率/均衡/安全
        'optimization_presets': {
            'efficiency': {'peck_mult': 1.2, 'feed_mult': 1.1, 'seg_adj': -1, 'desc': '⚡ 效率優先'},
            'balanced':   {'peck_mult': 1.0, 'feed_mult': 1.0, 'seg_adj':  0, 'desc': '⚖️ 均衡'},
            'safety':     {'peck_mult': 0.7, 'feed_mult': 0.85,'seg_adj':  1, 'desc': '🛡️ 安全優先'}
        },
        # [V2.2 補齊] 加入基準壽命映射表，避免檔案缺失時產生 20.0m 的回退偏差
        "base_life_meters": {
            "CARBIDE": {
                "AL6061":  {"nano": 5.0, "micro": 20.0, "small": 100.0, "medium": 150.0, "large": 200.0},
                "SUS304":  {"nano": 2.0, "micro": 5.0,  "small": 12.0,  "medium": 20.0,  "large": 30.0},
                "SUS420":  {"nano": 3.0, "micro": 8.0,  "small": 18.0,  "medium": 30.0,  "large": 45.0},
                "TI6AL4V": {"nano": 2.0, "micro": 4.0,  "small": 10.0,  "medium": 15.0,  "large": 20.0},
                "CERAMIC": {"nano": 1.0, "micro": 2.0,  "small": 5.0,   "medium": 8.0,   "large": 12.0}
            },
            "HSS": {
                "AL6061":  {"nano": 3.0, "micro": 10.0, "small": 50.0, "medium": 80.0, "large": 120.0},
                "SUS304":  {"nano": 1.0, "micro": 2.0,  "small": 5.0,  "medium": 8.0,  "large": 12.0},
                "SUS420":  {"nano": 1.5, "micro": 3.0,  "small": 8.0,  "medium": 12.0, "large": 18.0},
                "TI6AL4V": {"nano": 0.5, "micro": 1.5,  "small": 3.0,  "medium": 5.0,  "large": 8.0},
                "CERAMIC": {"nano": 0.5, "micro": 1.0,  "small": 1.5,  "medium": 2.0,  "large": 3.0}
            }
        }
    }

    def __init__(self, config_path="config.json"):
        # [V2.2 打包修正] 獲取目前執行檔的實際路徑與資源暫存路徑
        import sys
        self.config_filename = config_path
        
        # 1. 外部實體路徑 (EXE 同級目錄) - 使用者自訂優先
        if getattr(sys, 'frozen', False):
            self.ext_path = os.path.join(os.path.dirname(sys.executable), config_path)
        else:
            self.ext_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_path)
            
        # 2. 內部資源路徑 (_MEIPASS) - 打包時封裝的預設值
        self.int_path = None
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            self.int_path = os.path.join(sys._MEIPASS, config_path)

        self.config_path = self.ext_path # 預設存檔路徑設為外部，以便持久化
        self.data = self.load_config()

    def load_config(self):
        """載入設定檔。優先順序：(1) 外部檔案 -> (2) 內部封裝檔案 -> (3) 代碼預設值"""
        # 嘗試 (1) 外部檔案
        if os.path.exists(self.ext_path):
            try:
                with open(self.ext_path, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                    return self._merge_defaults(self.DEFAULT_CONFIG, user_data)
            except Exception as e:
                print(f"Error loading external config: {e}")

        # 嘗試 (2) 內部封裝檔案 (打包版適用)
        if self.int_path and os.path.exists(self.int_path):
            try:
                with open(self.int_path, 'r', encoding='utf-8') as f:
                    bundle_data = json.load(f)
                    return self._merge_defaults(self.DEFAULT_CONFIG, bundle_data)
            except Exception as e:
                print(f"Error loading bundled config: {e}")
                
        # (3) 使用硬編碼預設值
        return copy.deepcopy(self.DEFAULT_CONFIG)

    def _merge_defaults(self, defaults, user):
        """遞迴地將用戶設定合併到預設值中。"""
        res = defaults.copy()
        for k, v in user.items():
            if k in res and isinstance(v, dict) and isinstance(res[k], dict):
                res[k] = self._merge_defaults(res[k], v)
            else:
                res[k] = v
        return res

    def save_config(self, file_path=None):
        """將目前設定儲存到指定的 JSON 檔案，預設為內建設定路徑。"""
        target_path = file_path if file_path else self.config_path
        try:
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving config to {target_path}: {e}")
            return False

    def import_config(self, file_path):
        """從指定路徑匯入設定。"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
                # 使用 merge_defaults 確保匯入的資料結構完整，避免版本衝突
                self.data = self._merge_defaults(self.DEFAULT_CONFIG, user_data)
            # 匯入後自動存回預設的 config_path 讓程式下次啟動生效
            return self.save_config()
        except Exception as e:
            print(f"Error importing config from {file_path}: {e}")
            return False

    def reset_to_defaults(self):
        """重置為原始預設值。"""
        self.data = copy.deepcopy(self.DEFAULT_CONFIG)
        return self.save_config()

    # Getters
    def get_material_data(self, key):
        return self.data["materials"].get(key, self.DEFAULT_CONFIG["materials"]["AL6061"])

    def get_ijk_ratios(self, mode):
        return self.data["ijk_strategies"].get(mode, self.DEFAULT_CONFIG["ijk_strategies"]["efficient"])

    def get_limit(self, key):
        return self.data["limits"].get(key, self.DEFAULT_CONFIG["limits"].get(key))
