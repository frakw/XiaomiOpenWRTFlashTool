import nclib
import time
import threading

def send_file(file_path, port=1234):
    try:
        with open(file_path, 'rb') as f:
            data = f.read()

        with nclib.Netcat(listen=('0.0.0.0', port)) as nc:
            print(f"📡 [serve] Listening on port {port}, waiting for connection...")
            nc.send(data)
            print("✅ [serve] 檔案傳送完成！")

        return True, f"檔案傳送完成，監聽 port：{port}"

    except Exception as e:
        return False, f"傳送錯誤：{e}"

def receive_file(save_path, port=1234):
    try:
        with nclib.Netcat(listen=('0.0.0.0', port)) as nc:
            print(f"🔌 [recv] Listening on port {port}, waiting for connection...")
            data = nc.recv_all()
            with open(save_path, 'wb') as f:
                f.write(data)
            print(f"✅ [recv] 檔案接收完成，儲存至：{save_path}")
        return True, f"檔案接收完成，儲存至：{save_path}"

    except Exception as e:
        return False, f"接收錯誤：{e}"

if __name__ == '__main__':
    #receive_file('./received.txt')
    send_file('./upload.txt', 1234)
