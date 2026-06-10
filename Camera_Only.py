
import socket
import snap7
from snap7.util import set_lreal, set_bool, get_bool, set_int
from time import sleep


# ============================================================
# CONFIGURATION
# ============================================================

COGNEX_IP = "192.168.0.90"
COGNEX_PORT = 5001

camera = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
camera.connect((COGNEX_IP, COGNEX_PORT))
print("Cognex connected")



def safe_float(value, default=0.0):
    try:
        value = value.strip()
        if value == "":
            return default
        return float(value)
    except:
        return default

    
def read_cognex():
    data = ""

    while True:
        c = camera.recv(1).decode(errors="ignore")
        if c == "<":
            break

    while True:
        c = camera.recv(1).decode(errors="ignore")
        if c == ">":
            break
        data += c

    print("RAW:", repr(data))

    values = data.split("|")

    if len(values) != 7:
        return None

    return {
        "label": values[0].strip(),
        "x": safe_float(values[1]),
        "y": safe_float(values[2]),
        "blob_status": values[3].strip(),
        "logo_status": values[4].strip(),
        "ocr_text": values[5].strip(),
        "mean_color": safe_float(values[6]),
    }

while True:
    
    # data = camera.recv(128).decode(errors="ignore").strip()
    
  
    # values = data.split(",")
    
    # while len(values) < 7:
    #     values.append("0")
        
    # result = {
    #             "label": values[0].strip().upper(),
    #             "x": float(values[1]),
    #             "y": float(values[2]),
    #             "blob_status": values[3].strip().upper(),
    #             "logo_status": values[4].strip().upper(),
    #             "ocr_text": values[5].strip().upper(),
    #             "mean_color": float(values[6]),
    #         }
    
    # print(data)
    
    results = read_cognex()
    
    
    
    sleep(0.05)