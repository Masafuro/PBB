import sys
import time
from pathlib import Path
from multiprocessing import shared_memory

class PBBError(Exception):
    pass

class PBBSizeError(PBBError):
    pass

class PBBConnectionError(PBBError):
    pass

class PBBClient:
    def __init__(self):
        # 自身のユニット名を保持（自動解決用）
        self.my_unit = Path(sys.argv[0]).stem
        self._cache = {}

    def _parse_address(self, address):
        """'unit/topic' 形式の文字列を解析し、物理的なメモリ名を返す"""
        if "/" not in address:
            # アドレス形式が不正な場合のガード
            raise PBBError(f"Invalid address format: '{address}'. Use 'unit/topic'.")
        
        unit, topic = address.split("/", 1)
        base_name = f"PBB_{unit}_{topic}"
        return base_name, f"{base_name}_f"

    def _get_shm(self, name):
        """共有メモリへの接続をキャッシュを介して取得"""
        if name not in self._cache:
            try:
                self._cache[name] = shared_memory.SharedMemory(name=name)
            except FileNotFoundError:
                # 診断メッセージを含む例外を送出
                raise PBBConnectionError(
                    f"Connection failed: '{name}'. Check if Registry is running and address is correct."
                )
        return self._cache[name]

    def write(self, address, data):
        """書き込みに成功すれば True、失敗すれば False を返す。"""
        try:
            base_name, flag_name = self._parse_address(address)
            encoded_data = str(data).encode('utf-8')
            
            shm_data = self._get_shm(base_name)
            shm_flag = self._get_shm(flag_name)
            
            if len(encoded_data) > shm_data.size:
                # サイズ超過は設計ミスなので例外を継続
                raise PBBSizeError(f"Data exceeds size of '{address}'.")

            shm_flag.buf[0] = 1 # BUSY
            shm_data.buf[:len(encoded_data)] = encoded_data
            if len(encoded_data) < shm_data.size:
                shm_data.buf[len(encoded_data):] = b'\x00' * (shm_data.size - len(encoded_data))
            shm_flag.buf[0] = 2 # READY
            return True
        except (PBBConnectionError, FileNotFoundError):
            # 接続失敗時は False を返し、呼び出し側に委ねる
            return False
        except Exception:
            return False

    def read(self, address):
        """成功時は文字列を、失敗時（未接続や準備中）は None を返す。"""
        try:
            base_name, flag_name = self._parse_address(address)
            shm_data = self._get_shm(base_name)
            shm_flag = self._get_shm(flag_name)
            
            if shm_flag.buf[0] == 2:
                return bytes(shm_data.buf).rstrip(b'\x00').decode('utf-8', errors='replace')
        except (PBBConnectionError, FileNotFoundError):
            pass
        return None
    

    
    def check_flag(self, address):
        """指定したアドレスの現在のフラグ状態を文字列で返す。"""
        _, flag_name = self._parse_address(address)
        shm_flag = self._get_shm(flag_name)
        
        state_map = {0: "IDLE", 1: "BUSY", 2: "READY"}
        return state_map.get(shm_flag.buf[0], "UNKNOWN")

    def close(self):
        for shm in self._cache.values():
            shm.close()
        self._cache.clear()
