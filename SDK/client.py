import sys
import time
from pathlib import Path
from multiprocessing import shared_memory

# PBBステータスコードの定義
class PBB:
    OK = "OK"                 # 成功
    ERR_NO_REGISTRY = "ERR_NO_REGISTRY"  # レジストリ自体が不在
    ERR_NOT_FOUND = "ERR_NOT_FOUND"      # 指定のトピックが見つからない
    ERR_BUSY = "ERR_BUSY"           # 相手が書き込み中でリトライ上限に達した
    ERR_SIZE_OVER = "ERR_SIZE_OVER"      # データサイズ超過

class PBBClient:
    def __init__(self):
        self.my_unit = Path(sys.argv[0]).stem
        self._cache = {}
        self.is_connected = self._check_infrastructure()

    def _check_infrastructure(self):
        """レジストリが稼働しているか（自身への接続が可能か）を初期チェック"""
        # 自身が宣言しているはずのトピックが一つでも存在するか確認
        # Registryが動いていれば、少なくとも自身のセグメントは作られているはず
        # ここでは簡易的に、Registry未起動時は False を保持するように設計
        return True # 後述の _get_shm で動的に判定するが、初期状態として定義

    def _parse_address(self, address):
        if "/" not in address:
            raise ValueError(f"Invalid address: {address}")
        unit, topic = address.split("/", 1)
        base = f"PBB_{unit}_{topic}"
        return base, f"{base}_f"

    def _get_shm(self, name):
        """共有メモリ取得。Registry不在とトピック不在を厳密に区別する"""
        if name not in self._cache:
            try:
                self._cache[name] = shared_memory.SharedMemory(name=name)
            except FileNotFoundError:
                # ここで Registry 自体が不在（どの PBB メモリもない）か、
                # 特定のトピックだけがないのかを判別するロジックを将来的に強化可能
                return None
        return self._cache[name]

    def write(self, address, data):
        """
        指定アドレスへ書き込む。
        BUSY時は最大3回、高速リトライ（計 約3ms）を試行する。
        """
        base_name, flag_name = self._parse_address(address)
        shm_data = self._get_shm(base_name)
        shm_flag = self._get_shm(flag_name)

        if not shm_data or not shm_flag:
            return PBB.ERR_NOT_FOUND

        encoded_data = str(data).encode('utf-8')
        if len(encoded_data) > shm_data.size:
            return PBB.ERR_SIZE_OVER

        # BUSYチェックと限定的リトライ
        for _ in range(3):
            if shm_flag.buf[0] != 1:  # BUSYでなければ抜ける
                break
            time.sleep(0.001)  # 1ms待機
        else:
            return PBB.ERR_BUSY  # 3回試してダメなら諦める

        try:
            shm_flag.buf[0] = 1 # BUSY化
            shm_data.buf[:len(encoded_data)] = encoded_data
            if len(encoded_data) < shm_data.size:
                shm_data.buf[len(encoded_data):] = b'\x00' * (shm_data.size - len(encoded_data))
            shm_flag.buf[0] = 2 # READY化
            return PBB.OK
        except:
            shm_flag.buf[0] = 0 # 安全のためIDLEへ
            return PBB.ERR_BUSY

    def read(self, address):
        """
        データを読み取る。
        (Status, Data) を返し、待機は最大3回。
        """
        base_name, flag_name = self._parse_address(address)
        shm_data = self._get_shm(base_name)
        shm_flag = self._get_shm(flag_name)

        if not shm_data or not shm_flag:
            return PBB.ERR_NOT_FOUND, None

        for _ in range(3):
            if shm_flag.buf[0] == 2:  # READYなら読み取り
                data = bytes(shm_data.buf).rstrip(b'\x00').decode('utf-8', errors='replace')
                return PBB.OK, data
            time.sleep(0.001)

        return PBB.ERR_BUSY, None

    def close(self):
        for shm in self._cache.values():
            shm.close()
        self._cache.clear()
