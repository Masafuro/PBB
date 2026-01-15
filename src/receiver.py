# PBB_DECLARE: topic=status, init=LISTENING
import time
import sys
from pathlib import Path

# PBBClientが配置されているパスを動的に追加
sys.path.append(str(Path(__file__).resolve().parent.parent))
from PBB.client import PBBClient, PBBConnectionError

def run_receiver():
    try:
        # クライアントの初期化
        client = PBBClient()
        print(f"PBB Receiver unit '{client.unit_name}' started.")

        # 自身の状態を「LISTENING」から「RUNNING」に更新
        client.write("status", "RUNNING")

        last_data = None
        while True:
            try:
                # 相手（sender）のトピック（data）を読み取る
                # 内部でフラグがREADY(2)になるまで待機するロジックが含まれている
                current_data = client.read("sender", "data")

                if current_data is not None and current_data != last_data:
                    print(f"Received Update from sender: {current_data}")
                    last_data = current_data
                
            except PBBConnectionError:
                # 相手のメモリがまだ準備できていない場合の処理
                pass

            # 監視間隔の調整
            time.sleep(0.1)

    except PBBConnectionError as e:
        print(f"Error: {e}")
    except KeyboardInterrupt:
        print("Receiver stopped by user.")
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    run_receiver()