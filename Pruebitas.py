import socket
import snap7
from snap7.util import set_lreal, set_bool, get_bool, set_int
from time import sleep

COGNEX_IP = "192.168.0.90"
COGNEX_PORT = 5001
PLC1_IP = "192.168.0.1"

PLC1 = snap7.Client()
PLC1.connect(PLC1_IP, 0, 1)



def write_bool(plc, byte_addr, bit_addr, value):
    data = plc.mb_read(byte_addr, 1)
    set_bool(data, 0, bit_addr, value)
    plc.mb_write(byte_addr, 1, data)
    
 
 
def write_int(plc, start_byte, value):
    data = bytearray(2)
    set_int(data, 0, value)
    plc.mb_write(start_byte, 2, data)

if PLC1.get_connected():
    print("PLC1 connected")
else:
    print("PLC1 failed to connect")
    exit()


while True:
    write_bool(PLC1, 450,5, True)
    write_bool(PLC1, 470,6, True)
    write_int(PLC1, 800, 500)