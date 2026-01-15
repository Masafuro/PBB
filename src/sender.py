# PBB_DECLARE: topic=data, init=000.00
import time
import sys
from pathlib import Path

# PBBClientの配置場所を解決するためのインポート
sys.path.append(str(Path(__file__).resolve().parent.parent))
from PBB.SDK.client import PBBClient, PBB

def run_sender():
    # クライアントの初期化。この時点でインフラの健全性をチェックする
    client = PBBClient()
    
    # 自身のユニット名を確定
    my_unit = client.my_unit
    address = f"{my_unit}/data"
    
    print(f"PBB Sender Node '{my_unit}' initialized.")

    count = 0.0
    try:
        while True:
            # 送信データの生成
            value = f"{count:06.2f}"
            
            # 書き込みを実行し、その結果（ステータス）を即座に評価する
            status = client.write(address, value)
            
            if status == PBB.OK:
                # 成功時はログを出してカウントを進める
                print(f"[{status}] Sent: {value} to {address}")
                count += 0.1
                if count > 999: count = 0
                
            elif status == PBB.ERR_BUSY:
                # 相手が一時的に使用中。今回は深追いせず、次の周期でリトライする
                print(f"[{status}] Resource busy, skipping this tick.")
                
            elif status == PBB.ERR_NOT_FOUND:
                # レジストリがない、あるいはトピックが未設営。インフラの回復を待つ
                print(f"[{status}] Infrastructure not ready. Waiting for Registry...", end="\r")
                
            elif status == PBB.ERR_SIZE_OVER:
                # 設計ミスによるサイズ超過。この場合は続行不能として停止
                print(f"\n[{status}] Critical Error: Data size exceeds the initial declaration.")
                break
                
            # メインループの周期を維持
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\nSender node shutting down.")
    finally:
        client.close()

if __name__ == "__main__":
    run_sender()
