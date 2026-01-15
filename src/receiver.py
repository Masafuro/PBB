# PBB_DECLARE: topic=status, init=LISTENING
import time
import sys
from pathlib import Path

# PBBClientの配置場所を解決するためのインポート
sys.path.append(str(Path(__file__).resolve().parent.parent))
from PBB.SDK.client import PBBClient, PBB

def run_receiver():
    # クライアントの初期化
    client = PBBClient()
    print(f"PBB Receiver Node '{client.my_unit}' started.")

    # 自身のアドレスと、監視対象のアドレスを定義
    my_address = f"{client.my_unit}/status"
    target_address = "sender/data"

    # 自身の状態を「RUNNING」に更新。失敗してもループ内で継続されるため、ここでは結果を深追いしない。
    client.write(my_address, "RUNNING")

    last_data = None
    try:
        while True:
            # 相手のデータを読み取り。ステータスとデータをセットで受け取る。
            status, current_data = client.read(target_address)

            if status == PBB.OK:
                # 成功時。データに変化があった場合のみ表示する。
                if current_data != last_data:
                    print(f"[{status}] Received from {target_address}: {current_data}")
                    last_data = current_data
            
            elif status == PBB.ERR_BUSY:
                # 相手が書き込み中（リトライ上限到達）。今回は処理をスキップ。
                pass

            elif status == PBB.ERR_NOT_FOUND:
                # 相手のメモリが存在しない。インフラの準備を待つ。
                print(f"[{status}] Waiting for {target_address}...        ", end="\r")

            # 監視周期の調整
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nReceiver node shutting down.")
    finally:
        # 終了前に自身の状態を更新
        client.write(my_address, "IDLE")
        client.close()

if __name__ == "__main__":
    run_receiver()
