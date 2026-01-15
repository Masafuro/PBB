import os
import sys
import time
from pathlib import Path
from multiprocessing import shared_memory

class PBBError(Exception):
    """PBBシステム全般のエラーを扱う基底クラス"""
    pass

class PBBSizeError(PBBError):
    """書き込みデータが確保サイズを超過した場合のエラー"""
    pass

class PBBConnectionError(PBBError):
    """共有メモリへの接続に失敗した場合のエラー"""
    pass

class PBBClient:
    def __init__(self):
        # 実行中のスクリプト名からユニット名を自動取得
        self.unit_name = Path(sys.argv[0]).stem
        self._cache = {}
        
    def _get_shm(self, name):
        """共有メモリへの接続を取得し、キャッシュする"""
        if name not in self._cache:
            try:
                self._cache[name] = shared_memory.SharedMemory(name=name)
            except FileNotFoundError:
                raise PBBConnectionError(f"Shared memory '{name}' not found. Is PBBRegistry running?")
        return self._cache[name]

    def write(self, topic, data):
        """自身の黒板へデータを書き込む。サイズ超過時はエラー。"""
        base_name = f"PBB_{self.unit_name}_{topic}"
        flag_name = f"{base_name}_f"
        
        # データのバイナリ変換
        encoded_data = str(data).encode('utf-8')
        data_size = len(encoded_data)
        
        # 共有メモリへのアタッチ
        shm_data = self._get_shm(base_name)
        shm_flag = self._get_shm(flag_name)
        
        # 1. サイズチェック（初期サイズを超えていれば例外を投げる）
        if data_size > shm_data.size:
            raise PBBSizeError(
                f"Data size ({data_size} bytes) exceeds the initial size ({shm_data.size} bytes) "
                f"defined for topic '{topic}' in unit '{self.unit_name}'."
            )
            
        try:
            # 2. フラグを「BUSY (1)」に設定
            shm_flag.buf[0] = 1
            
            # 3. データの書き込み（残りの領域をヌル文字で埋める）
            shm_data.buf[:data_size] = encoded_data
            if data_size < shm_data.size:
                shm_data.buf[data_size:] = b'\x00' * (shm_data.size - data_size)
                
            # 4. フラグを「READY (2)」に設定
            shm_flag.buf[0] = 2
        except Exception as e:
            # エラー時は安全のためフラグを「IDLE (0)」に戻す試みを行う
            shm_flag.buf[0] = 0
            raise PBBError(f"Failed to write to shared memory: {e}")

    def read(self, unit, topic, wait_ready=True):
        """他者の黒板からデータを読み取る。"""
        base_name = f"PBB_{unit}_{topic}"
        flag_name = f"{base_name}_f"
        
        shm_data = self._get_shm(base_name)
        shm_flag = self._get_shm(flag_name)
        
        # フラグがREADY(2)になるまで短時間待機するかどうか
        if wait_ready:
            max_retries = 100
            while shm_flag.buf[0] != 2 and max_retries > 0:
                time.sleep(0.01)
                max_retries -= 10
                
        if shm_flag.buf[0] == 2:
            # ヌル文字を取り除いてデコード
            raw_data = bytes(shm_data.buf).rstrip(b'\x00')
            return raw_data.decode('utf-8', errors='replace')
        
        return None

    def close(self):
        """開いている共有メモリのハンドルを閉じる（OS上の実体は消さない）"""
        for shm in self._cache.values():
            shm.close()
        self._cache.clear()