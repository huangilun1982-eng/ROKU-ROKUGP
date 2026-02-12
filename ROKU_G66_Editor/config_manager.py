
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
            'MQL': 0.8,        # 油霧：建議 Vc x 0.8
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
                'Internal': 0.75, 'MQL': 1.2, 'Dry': 1.6
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
        }
    }

    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.data = self.load_config()

    def load_config(self):
        """載入設定檔，若不存在則回傳預設值。"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                    # 合併預設值以確保欄位完整 (以防舊版本遺漏新欄位)
                    return self._merge_defaults(self.DEFAULT_CONFIG, user_data)
            except Exception as e:
                print(f"Error loading config: {e}")
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
