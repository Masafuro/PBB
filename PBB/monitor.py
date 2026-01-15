import os
import re
import time
from datetime import datetime
from pathlib import Path
from multiprocessing import shared_memory

class PBBMonitor:
    def __init__(self, src_dirname="src"):
        self.src_dirname = src_dirname
        self.decl_pattern = re.compile(r'#\s*PBB_DECLARE:\s*topic=([^,\s]+),\s*init=(.+)')
        self.topics = []
        self.last_states = {}

    def find_src_path(self):
        # 自身のファイル位置から遡って src を探す
        current_path = Path(__file__).resolve().parent
        
        # 最大3階層まで遡って src フォルダを探す
        for _ in range(3):
            target = current_path / self.src_dirname
            if target.exists() and target.is_dir():
                return target
            current_path = current_path.parent
            
        # 見つからない場合はカレントディレクトリを試す
        cwd_target = Path(os.getcwd()) / self.src_dirname
        if cwd_target.exists():
            return cwd_target
            
        return None

    def scan_topics(self):
        src_path = self.find_src_path()
        if not src_path:
            print(f"Error: Could not find '{self.src_dirname}' directory from {Path(__file__).name}")
            return

        print(f"PBB Monitor scanning: {src_path}")
        self.topics = []
        for py_file in src_path.rglob("*.py"):
            unit_name = py_file.stem
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        match = self.decl_pattern.search(line)
                        if match:
                            topic_name = match.group(1).strip()
                            base_name = f"PBB_{unit_name}_{topic_name}"
                            self.topics.append({
                                "unit": unit_name,
                                "topic": topic_name,
                                "name": base_name,
                                "flag_name": f"{base_name}_f"
                            })
                            print(f"Found topic: {unit_name} | {topic_name}")
            except Exception as e:
                print(f"Could not read {py_file}: {e}")

    def run(self):
        self.scan_topics()
        
        if not self.topics:
            print("No PBB declarations found. Please check your # PBB_DECLARE comments.")
            return

        print("-" * 80)
        print(f"{'TIMESTAMP':<20} | {'UNIT':<12} | {'TOPIC':<12} | {'STATUS':<7} | {'DATA'}")
        print("-" * 80)

        while True:
            for t in self.topics:
                try:
                    shm_f = shared_memory.SharedMemory(name=t['flag_name'])
                    shm_d = shared_memory.SharedMemory(name=t['name'])
                    
                    current_flag = shm_f.buf[0]
                    # データ長を動的に取得する仕組みがないため、とりあえず全領域を読み取る
                    current_data = bytes(shm_d.buf).decode('utf-8', errors='replace').rstrip('\x00')
                    
                    status = "IDLE" if current_flag == 0 else "BUSY" if current_flag == 1 else "READY"
                    state_key = t['name']
                    current_state = (current_flag, current_data)

                    if state_key not in self.last_states or self.last_states[state_key] != current_state:
                        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        print(f"{ts:<20} | {t['unit']:<12} | {t['topic']:<12} | {status:<7} | {current_data}")
                        self.last_states[state_key] = current_state
                    
                    shm_f.close()
                    shm_d.close()
                except FileNotFoundError:
                    if t['name'] not in self.last_states or self.last_states[t['name']] != "OFFLINE":
                        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        print(f"{ts:<20} | {t['unit']:<12} | {t['topic']:<12} | OFFLINE | (Waiting...)")
                        self.last_states[t['name']] = "OFFLINE"
            
            time.sleep(0.1)

if __name__ == "__main__":
    monitor = PBBMonitor()
    monitor.run()