
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



    
        
print(len("1,0.1038,-0.0220,0,0,N,53.2007"))

while True:
    
    data = camera.recv(32).decode(errors="ignore").strip()
    
  
    values = data.split(",")
    
    while len(values) < 7:
        values.append("0")
        
    result = {
                "label": values[0].strip().upper(),
                "x": float(values[1]),
                "y": float(values[2]),
                "blob_status": values[3].strip().upper(),
                "logo_status": values[4].strip().upper(),
                "ocr_text": values[5].strip().upper(),
                "mean_color": float(values[6]),
            }
    
    print(result)
    
    
    sleep(0.05)