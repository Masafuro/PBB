import os
import re
import signal
import sys
import time
from pathlib import Path
from multiprocessing import shared_memory

class PBBRegistry:
    def __init__(self, src_dirname="src"):
        self.src_dirname = src_dirname
        self.deployed_memories = []
        self.stop_requested = False
        
        # 宣言を抽出するための正規表現
        # 例: # PBB_DECLARE: topic=status, init=START
        self.decl_pattern = re.compile(r'#\s*PBB_DECLARE:\s*topic=([^,\s]+),\s*init=(.+)')

    def find_src_path(self):
            # registry.py自身の絶対パスを取得
            current_script_path = Path(__file__).resolve()
            
            # サブモジュールとして project_root/PBB/registry.py にある場合、
            # parent.parent で project_root に到達する
            # 構造に応じて parent の数を調整、あるいは src が見つかるまで遡るロジックにする
            project_root = current_script_path.parent.parent
            
            src_path = project_root / self.src_dirname
            
            if not src_path.exists():
                # フォールバックとしてカレントディレクトリからの探索も試みる
                src_path = Path(os.getcwd()) / self.src_dirname
                
            if not src_path.exists():
                print(f"Error: Could not find {self.src_dirname} directory.")
                print(f"Searched near script: {project_root / self.src_dirname}")
                print(f"Searched CWD: {Path(os.getcwd()) / self.src_dirname}")
                sys.exit(1)
                
            return src_path

    def scan_and_register(self):
        src_path = self.find_src_path()
        print(f"PBB Registry scanning: {src_path}")
        
        for py_file in src_path.rglob("*.py"):
            unit_name = py_file.stem
            with open(py_file, 'r', encoding='utf-8') as f:
                for line in f:
                    match = self.decl_pattern.search(line)
                    if match:
                        topic_name = match.group(1).strip()
                        init_val = match.group(2).strip().encode('utf-8')
                        self.create_sm_pair(unit_name, topic_name, init_val)

    def create_sm_pair(self, unit, topic, init_data):
        # 命名規則に基づく名称生成（OSが許容する記号に置換）
        base_name = f"PBB_{unit}_{topic}"
        flag_name = f"{base_name}_f"
        size = len(init_data)

        try:
            # データ本体の作成と初期化
            shm_data = shared_memory.SharedMemory(name=base_name, create=True, size=size)
            shm_data.buf[:size] = init_data
            self.deployed_memories.append(shm_data)
            
            # フラグセグメントの作成と初期化（0: Idle）
            shm_flag = shared_memory.SharedMemory(name=flag_name, create=True, size=1)
            shm_flag.buf[0] = 0
            self.deployed_memories.append(shm_flag)
            
            print(f"Deployed: {base_name} ({size} bytes) & {flag_name}")
        except FileExistsError:
            print(f"Warning: {base_name} already exists. Skipping.")

    def cleanup(self):
        print("\nPBB Registry cleaning up...")
        for shm in self.deployed_memories:
            try:
                shm.close()
                shm.unlink()
                print(f"Unlinked: {shm.name}")
            except Exception as e:
                print(f"Failed to unlink {shm.name}: {e}")

    def run(self):
        self.scan_and_register()
        print("PBB Registry is active. Press Ctrl+C to stop.")
        
        # シグナルハンドリングの設定
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            while not self.stop_requested:
                time.sleep(1)
        finally:
            self.cleanup()

    def _signal_handler(self, signum, frame):
        self.stop_requested = True

if __name__ == "__main__":
    registry = PBBRegistry()
    registry.run()