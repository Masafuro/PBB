# PBB_DECLARE: topic=data, init=000.00
import time
import sys
from pathlib import Path

# PBBClientが配置されているパスをインポート（環境に応じて調整）
# ここではPBBClientがプロジェクトルートにあると仮定
sys.path.append(str(Path(__file__).resolve().parent.parent))
from SDK.client import PBBClient, PBBSizeError, PBBConnectionError

def run_sender():
    try:
        # クライアントの初期化（ユニット名はファイル名から自動取得される）
        client = PBBClient()
        print(f"PBB Sender unit '{client.unit_name}' started.")

        count = 0
        while True:
            # 送信するデータの生成
            # 形式を整えた文字列を作成
            val = f"{count:06.2f}"
            
            try:
                # 黒板への書き込み
                # 内部でフラグ制御（BUSY -> READY）とサイズチェックが実行される
                client.write("data", val)
                print(f"Update: {val}")
                
            except PBBSizeError as e:
                # サイズ超過時はシステムを停止させる方針
                print(f"Critical Error: {e}")
                break
                
            count += 0.5
            if count > 999: count = 0
            time.sleep(1)

    except PBBConnectionError as e:
        print(f"Initial Connection Failed: {e}")
    except KeyboardInterrupt:
        print("Sender stopped by user.")
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    run_sender()