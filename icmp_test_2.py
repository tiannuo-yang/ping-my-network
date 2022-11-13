# reference: https://blog.csdn.net/du159539/article/details/117297039
import socket
import struct
import time
import array
import random
import string
from threading import Thread
from math import ceil
import PySimpleGUI as sg

class IcmpRequest:
    def __init__(self, addr, pack_byte, timeout, result_list) -> None:
        self.addr = addr
        self.pack_byte = pack_byte
        self.timeout = timeout
        self.result_list = result_list

        self.finished = False
        self.socket = self.rawSocket
        self.__id = random.randint(1000, 65535)
        self.__data = self.create_string_number(self.pack_byte)

        self.recv_addr, self.ttl = '', -1
        self.send_time, self.recv_time = -1, -1
    
    @property
    def rawSocket(self):
        try:
            Sock = socket.socket(
                socket.AF_INET, socket.SOCK_RAW, socket.getprotobyname("icmp"))
            Sock.settimeout(self.timeout)
        except:
            Sock = self.rawSocket
        return Sock

    def inCksum(self, packet):
        if len(packet) & 1:
            packet = packet + '\0'
        words = array.array('h', packet)
        sum = 0
        for word in words:
            sum += (word & 0xffff)
        sum = (sum >> 16) + (sum & 0xffff)
        sum = sum + (sum >> 16)
        return (~sum) & 0xffff

    def create_string_number(self, n):
        """生成一串指定位数的字符+数组混合的字符串"""
        m = random.randint(1, n)
        a = "".join([str(random.randint(0, 9)) for _ in range(m)])
        b = "".join([random.choice(string.ascii_letters) for _ in range(n - m)])
        return bytes(''.join(random.sample(list(a + b), n)), encoding='utf-8')

    def create_packet(self):
        header = struct.pack('bbHHh', 8, 0, 0, self.__id, 0)
        packet = header + self.__data
        chkSum = self.inCksum(packet)
        header = struct.pack('bbHHh', 8, 0, chkSum, self.__id, 0)
        return header + self.__data

    def recv_packet(self):
        while 1:
            try:
                recv_packet, addr = self.socket.recvfrom(10240)
                type, code, checksum, packet_ID, sequence = struct.unpack(
                    "bbHHh", recv_packet[20:28])
                if packet_ID == self.__id:
                    self.recv_time = time.time()
                    self.ttl = struct.unpack("!BBHHHBBHII", recv_packet[:20])[5]
                    self.recv_addr = addr[0]
            except:
                if self.finished:
                    break
    
    def send(self):
        packet = self.create_packet()
        t = Thread(target=self.recv_packet,)
        t.start()
        self.send_time = time.time()

        try:
            self.socket.sendto(packet, (self.addr, 0))
            time.sleep(self.timeout + 1)
        except:
            pass

        self.finished = True
        self.socket.close()
        t.join()

        # 返回（是否成功收到回复，接收包的地址，请求的TTL，请求的RTT）
        self.result_list.append([self.recv_time > 0, self.recv_addr, self.ttl, ceil((self.recv_time-self.send_time) * 1000)])
        

class BatchIcmp:
    def __init__(self, addr='www.baidu.com', pack_num=4, interval=10, pack_byte=32, timeout=1000) -> None:
        self.addr = addr
        self.pack_byte = pack_byte
        self.pack_num = pack_num
        self.interval = interval / 1000
        self.timeout = timeout / 1000

        self.result_list = []
        self.req_list = [IcmpRequest(self.addr, self.pack_byte, self.timeout, self.result_list) for _ in range(pack_num)]

        self.finished = False

    def start(self):
        self.thread_list = []
        for req in self.req_list:
            self.thread_list.append(Thread(target=req.send))
        for t in self.thread_list:
            t.start()
            time.sleep(self.interval)
        for t in self.thread_list:
            t.join()
            time.sleep(0.5)
        self.finished = True


class Gui_output:
    def __init__(self) -> None:
        sg.theme('SandyBeach')     
        
        layout = [
            [sg.Text('服务端地址',size=(16,1),), sg.InputText(default_text='www.baidu.com',size=(69,12))],
            # [sg.Text('',font=('黑体',1))],
            [sg.Text('报文数量（ 个 ）', size =(16, 1)), sg.Slider(range=(1, 100), default_value=4, resolution=1, orientation='horizontal', size=(69,10))],
            [sg.Text('时间间隔（毫秒）', size =(16, 1)), sg.Slider(range=(1, 100), default_value=10, resolution=1, orientation='horizontal', size=(69,10))],
            [sg.Text('报文大小（字节）', size =(16, 1)), sg.Slider(range=(32,32*100), default_value=32, resolution=32, orientation='horizontal', size=(69,10))],
            [sg.Text('',size=(15,1))],
            [sg.Submit(button_text='开始测试'), sg.Cancel('退出测试')],
            [sg.Multiline(size=(85, 15), key='_Multiline_', auto_refresh=True)],
        ]
        
        self.window = sg.Window('网络连通测试程序', layout, font=('黑体',12), default_element_size=(50,1))
        
    def open_window(self):
        while True:
            event, values = self.window.read()
            if event == None: 
                break
            if event == '开始测试':
                batch_icmp = BatchIcmp(addr=values[0],pack_num=int(values[1]),interval=int(values[2]),pack_byte=int(values[3]))
                t = Thread(target=batch_icmp.start)
                t.start()

                while not batch_icmp.finished:
                    self.window.Element('_Multiline_').Update(self.output_trans(batch_icmp))
                t.join()
            if event == '退出测试' or event == None:
                self.window.close()
    
    def output_trans(self, batch_icmp:BatchIcmp):
        out_text = f'正在连通测试 {batch_icmp.addr}\n'
        if len(batch_icmp.result_list) > 0:
            for i,r in enumerate(batch_icmp.result_list):
                if r[0]:
                    out_text += f'{i+1} 来自 {r[1]} 的回复: 字节 = {batch_icmp.pack_byte}; 生存时间(TTL) = {r[2]}; 往返时间(RTT) = {r[3]} ms\n'
                else:
                    out_text += f'{i+1} 请求超时(超过 {batch_icmp.timeout} ms 无应答)\n'

                if i+1 == len(batch_icmp.result_list):
                    total = batch_icmp.pack_num
                    accept = sum([1 for r in batch_icmp.result_list if r[0]])
                    reject = total - accept
                    out_text += f'\n连通测试 {batch_icmp.addr} 的统计信息\n'
                    out_text += f'接收回送应答: 已发送 = {total}; 接收 = {accept}; 丢失 = {reject} (丢失率 = {reject / total * 100}%)\n'

                    rtt_list = [r[3] for r in batch_icmp.result_list]
                    out_text += f'往返行程延时: 最小 = {min(rtt_list)} ms; 最大 = {max(rtt_list)} ms; 平均 = {sum(rtt_list)/total} ms'
        return out_text


if __name__ == '__main__':
    gui = Gui_output()
    gui.open_window()
    