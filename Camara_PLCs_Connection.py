import socket
import snap7
from snap7.util import set_lreal, set_bool, get_bool, set_int
from time import sleep


# ============================================================
# CONFIGURATION
# ============================================================

COGNEX_IP = "192.168.0.90"
COGNEX_PORT = 5001

PLC1_IP = "192.168.0.1"   # PLC del Delta
PLC2_IP = "192.168.0.2"   # PLC del multivista


# ============================================================
# PLC1 ADDRESSES
# PLC1 = Delta + secuencia principal
# ============================================================

X_ADDR = 332        # ML332, LREAL
Y_ADDR = 348        # ML348, LREAL

PLC1_FLAGS_ADDR = 360  # MB360

COORD_DATA_READY_BIT = 0       # M360.0 Python → PLC1
OBJECT_VALID_BIT = 1           # M360.1 Python → PLC1
COORD_DATA_RECEIVED_BIT = 2    # M360.2 PLC1 → Python
ROBOT_BUSY_BIT = 3             # M360.3 PLC1 → Python
MULTIVISTA_READY_BIT = 4       # M360.4 PLC1 → Python

DIAGNOSTIC_READY_BIT = 5       # M360.5 Python → PLC1
DIAGNOSTIC_RECEIVED_BIT = 6    # M360.6 PLC1 → Python

DIAGNOSTIC_ADDR = 232          # MW362, INT

ROBOT_READY_TO_START = 7       #M219.7


# ============================================================
# PLC2 ADDRESSES
# PLC2 = Motores multivista + succión + gripper auxiliar
# ============================================================

PLC2_FLAGS_ADDR = 360          # MB360

FLIP_REQUEST_BIT = 0           # M360.0 Python → PLC2
FLIP_DONE_BIT = 1              # M360.1 PLC2 → Python

ROTATE_DONE_BIT = 2            # M360.2 PLC2 → Python
ROTATE_REQUEST_BIT = 3         # M360.3 Python → PLC2

MOVE_BUSY_BIT = 4              # M360.4 PLC2 → Python, opcional

ROTATE_DEGREES_ADDR = 362      # MW362, INT

INSPECTION_DONE_BIT = 5  # M360.5 Python → PLC2

DIAGNOSTIC_ADDR_2 = 28         # MW28, INT
# ============================================================
# DIAGNOSTIC CODES
# ============================================================

DIAG_OK = 1
DIAG_NOT_OK = 2
DIAG_RETRY = 3


# ============================================================
# PARAMETERS
# ============================================================

ROTATE_SMALL = 10
ROTATE_BIG = 120

FULL_ROTATION_STEPS = 36
# 36 * 10° = 360°. Solo imprime advertencia, no manda RETRY.

MAX_OCR_READ_ATTEMPTS = 5
# Si llega al OCR pero no lee YELLOW/BROWN, hace ajustes pequeños.

COLOR_THRESHOLD = 70
# Calibrar con pruebas reales.
# mean_color > 50  → YELLOW
# mean_color <= 50 → BROWN


# ============================================================
# CONNECTIONS
# ============================================================

camera = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
camera.connect((COGNEX_IP, COGNEX_PORT))
print("Cognex connected")


PLC1 = snap7.Client()
PLC1.connect(PLC1_IP, 0, 1)

if PLC1.get_connected():
    print("PLC1 connected")
else:
    print("PLC1 failed to connect")
    exit()


PLC2 = snap7.Client()
PLC2.connect(PLC2_IP, 0, 1)

if PLC2.get_connected():
    print("PLC2 connected")
else:
    print("PLC2 failed to connect")
    exit()


# ============================================================
# BASIC PLC FUNCTIONS
# ============================================================

def write_lreal(plc, start_byte, value):
    data = bytearray(8)
    set_lreal(data, 0, value)
    plc.mb_write(start_byte, 8, data)


def write_int(plc, start_byte, value):
    data = bytearray(2)
    set_int(data, 0, value)
    plc.mb_write(start_byte, 2, data)


def write_bool(plc, byte_addr, bit_addr, value):
    data = plc.mb_read(byte_addr, 1)
    set_bool(data, 0, bit_addr, value)
    plc.mb_write(byte_addr, 1, data)


def read_bool(plc, byte_addr, bit_addr):
    data = plc.mb_read(byte_addr, 1)
    return get_bool(data, 0, bit_addr)


def safe_int(value, default=0):
    try:
        value = value.strip()
        if value == "":
            return default
        return int(float(value))
    except:
        return default


def safe_float(value, default=0.0):
    try:
        value = value.strip()
        if value == "":
            return default
        return float(value)
    except:
        return default


# ============================================================
# COGNEX READING
# ============================================================

def read_cognex():
    data = camera.recv(32).decode(errors="ignore").strip()

    # if data == "":
    #     return None

    #print("Raw Cognex:", data)

    values = data.split(",")

    while len(values) < 7:
        values.append("0")

    return {
        "label": values[0].strip().upper(),
        "x": safe_float(values[1]),
        "y": safe_float(values[2]),
        "blob_status": values[3].strip().upper(),
        "logo_status": values[4].strip().upper(),
        "ocr_text": values[5].strip().upper(),
        "mean_color": safe_float(values[6]),
    }

# ============================================================
# LOGIC FUNCTIONS
# ============================================================

def detect_color(mean_color):
    if mean_color > COLOR_THRESHOLD:
        return "Y"
    else:
        return "B"

def print_full_rotation_warning(counter, target_name):
    if counter > 0 and counter % FULL_ROTATION_STEPS == 0:
        print("WARNING: completed one full rotation while searching for", target_name)
        print("Still searching because every cup should have this reference.")


def send_coordinates_to_plc1(x, y):
    write_lreal(PLC1, X_ADDR, x)
    write_lreal(PLC1, Y_ADDR, y)

    write_bool(PLC1, PLC1_FLAGS_ADDR, OBJECT_VALID_BIT, True)
    write_bool(PLC1, PLC1_FLAGS_ADDR, COORD_DATA_READY_BIT, True)

    print("Coordinates sent to PLC1")
    print("X:", x)
    print("Y:", y)


def clear_coordinate_request_to_plc1():
    write_bool(PLC1, PLC1_FLAGS_ADDR, COORD_DATA_READY_BIT, False)
    write_bool(PLC1, PLC1_FLAGS_ADDR, OBJECT_VALID_BIT, False)

    print("Coordinate request cleared")


def request_multivista_flip():
    write_bool(PLC2, PLC2_FLAGS_ADDR, FLIP_REQUEST_BIT, True)
    print("Requested multivista flip")


def clear_multivista_flip_request():
    write_bool(PLC2, PLC2_FLAGS_ADDR, FLIP_REQUEST_BIT, False)
    print("Multivista flip request cleared")


def request_multivista_rotation(degrees):
    write_int(PLC2, ROTATE_DEGREES_ADDR, degrees)
    write_bool(PLC2, PLC2_FLAGS_ADDR, ROTATE_REQUEST_BIT, True)

    print("Requested multivista rotation:", degrees, "degrees")


def clear_multivista_rotation_request():
    write_bool(PLC2, PLC2_FLAGS_ADDR, ROTATE_REQUEST_BIT, False)
    print("Multivista rotation request cleared")


def send_diagnostic_to_plc1(diagnostic_code):
    write_int(PLC1, DIAGNOSTIC_ADDR, diagnostic_code)
    write_bool(PLC1, PLC1_FLAGS_ADDR, DIAGNOSTIC_READY_BIT, True)

    if diagnostic_code == DIAG_OK:
        print("Diagnostic sent to PLC1: OK")
    elif diagnostic_code == DIAG_NOT_OK:
        print("Diagnostic sent to PLC1: NOT OK")
    elif diagnostic_code == DIAG_RETRY:
        print("Diagnostic sent to PLC1: RETRY")
    else:
        print("Diagnostic sent to PLC1: UNKNOWN")


def send_diagnostic_to_plc2(diagnostic_code):
    write_int(PLC2, DIAGNOSTIC_ADDR_2, diagnostic_code)
    write_bool(PLC2, PLC2_FLAGS_ADDR, INSPECTION_DONE_BIT, True)
    
    if diagnostic_code == DIAG_OK:
        print("Diagnostic sent to PLC2: OK")
    elif diagnostic_code == DIAG_NOT_OK:
        print("Diagnostic sent to PLC2: NOT OK")
    elif diagnostic_code == DIAG_RETRY:
        print("Diagnostic sent to PLC2: RETRY")
    else:
        print("Diagnostic sent to PLC2: UNKNOWN")

def clear_diagnostic_to_plc1():
    write_bool(PLC1, PLC1_FLAGS_ADDR, DIAGNOSTIC_READY_BIT, False)
    print("Diagnostic request cleared")
    

def clear_inspection_done_to_plc2():
    write_bool(PLC2, PLC2_FLAGS_ADDR, INSPECTION_DONE_BIT, False)
    print("InspectionDone to PLC2 cleared")
# ============================================================
# INITIAL CLEANUP
# ============================================================

write_bool(PLC1, PLC1_FLAGS_ADDR, COORD_DATA_READY_BIT, False)
write_bool(PLC1, PLC1_FLAGS_ADDR, OBJECT_VALID_BIT, False)
write_bool(PLC1, PLC1_FLAGS_ADDR, DIAGNOSTIC_READY_BIT, False)

write_bool(PLC2, PLC2_FLAGS_ADDR, FLIP_REQUEST_BIT, False)
write_bool(PLC2, PLC2_FLAGS_ADDR, ROTATE_REQUEST_BIT, False)



x = 0.0
y = 0.0

ocr_color = None
diagnostic = None

logo_search_count = 0
ocr_retry_count = 0


state = "WAIT_FOR_DELTA"
printed_not_ready = False

# ============================================================
# STATE MACHINE
# ============================================================



while True:
    
    result = read_cognex()
    
    # --------------------------------------------------------
    # 0. Esperar a que el delta este listo.
    # --------------------------------------------------------
    
    Start = read_bool(PLC1, 219, ROBOT_READY_TO_START)

    if state == "WAIT_FOR_DELTA":
        if Start:
            print("Python ready")
            printed_not_ready = False
            state = "WAIT_CUP"
        else:
            if not printed_not_ready:
                print("Delta is not ready.")
                printed_not_ready = True

        sleep(0.05)
        continue
    

    # --------------------------------------------------------
    # 1. Esperar que la cámara vea una vacuna/vasito
    # --------------------------------------------------------
    elif state == "WAIT_CUP":

        robot_busy = read_bool(PLC1, PLC1_FLAGS_ADDR, ROBOT_BUSY_BIT)
        coord_received = read_bool(
            PLC1,
            PLC1_FLAGS_ADDR,
            COORD_DATA_RECEIVED_BIT
        )

        if not robot_busy and not coord_received:
            #result = read_cognex()
            print(result)

            if result is None:
                sleep(0.05)
                continue

            if result["label"] == "1":
                x = result["x"]
                y = result["y"]

                print("Vacuna detected")
                state = "SEND_COORDS_TO_PLC1"
                

            else:
                print("NoVacuna detected. Waiting...")
                state = "WAIT_CUP"


    # --------------------------------------------------------
    # 2. Mandar coordenadas X/Y al PLC1
    # --------------------------------------------------------
    elif state == "SEND_COORDS_TO_PLC1":

        send_coordinates_to_plc1(x, y)
        state = "WAIT_PLC1_COORD_RECEIVED"


    # --------------------------------------------------------
    # 3. Esperar confirmación de PLC1
    # --------------------------------------------------------
    elif state == "WAIT_PLC1_COORD_RECEIVED":

        coord_received = read_bool(
            PLC1,
            PLC1_FLAGS_ADDR,
            COORD_DATA_RECEIVED_BIT
        )

        if coord_received:
            print("PLC1 received coordinates")
            #clear_coordinate_request_to_plc1()
            state = "WAIT_PLC1_COORD_RECEIVED_RESET"


    # --------------------------------------------------------
    # 4. Esperar que PLC1 baje CoordDataReceived
    # --------------------------------------------------------
    elif state == "WAIT_PLC1_COORD_RECEIVED_RESET":

        coord_received = read_bool(
            PLC1,
            PLC1_FLAGS_ADDR,
            COORD_DATA_RECEIVED_BIT
        )

        if coord_received:
            print("Coordinate handshake finished")
            print("Robot moving to position.")
            state = "WAIT_MULTIVISTA_READY"


    # --------------------------------------------------------
    # 5. Esperar que PLC1 diga que el vasito ya está en multivista
    # --------------------------------------------------------
    elif state == "WAIT_MULTIVISTA_READY":

        multivista_ready = read_bool(
            PLC1,
            PLC1_FLAGS_ADDR,
            MULTIVISTA_READY_BIT
        )

        if multivista_ready:
            print("Cup is in multivista position")
            clear_coordinate_request_to_plc1()

            ocr_color = None
            diagnostic = None
            logo_search_count = 0
            ocr_retry_count = 0

            state = "READ_TOP_CAMERA"


    # --------------------------------------------------------
    # 6. Leer cámara viendo la tapa
    # --------------------------------------------------------
    elif state == "READ_TOP_CAMERA":

        #result = read_cognex()
        print(result)

        if result is None:
            sleep(0.05)
            continue

        blob_status = result["blob_status"]

        print("Top inspection:")
        print("Blob status:", blob_status)

        state = "EVALUATE_TOP_BLOB"


    # --------------------------------------------------------
    # 7. Evaluar rayón en tapa
    # --------------------------------------------------------
    elif state == "EVALUATE_TOP_BLOB":

        if blob_status == "1":
            print("Scratch detected on lid")
            diagnostic = DIAG_NOT_OK
            state = "SEND_DIAGNOSTIC_TO_PLC1"

        else:
            print("No scratch detected. Requesting flip to side view.")
            request_multivista_flip()
            state = "WAIT_FLIP_DONE"


    # --------------------------------------------------------
    # 8. Esperar que PLC2 termine el flip fijo
    # --------------------------------------------------------
    elif state == "WAIT_FLIP_DONE":

        flip_done = read_bool(PLC2, PLC2_FLAGS_ADDR, FLIP_DONE_BIT)

        if flip_done:
            print("PLC2 finished flip")
            clear_multivista_flip_request()
            state = "WAIT_FLIP_DONE_RESET"


    # --------------------------------------------------------
    # 9. Esperar que PLC2 baje FlipDone
    # --------------------------------------------------------
    elif state == "WAIT_FLIP_DONE_RESET":

        flip_done = read_bool(PLC2, PLC2_FLAGS_ADDR, FLIP_DONE_BIT)

        if not flip_done:
            print("Flip handshake finished")
            sleep(3)
            state = "SEARCH_LOGO"


    # --------------------------------------------------------
    # 10. Buscar logo con pasos pequeños
    # --------------------------------------------------------
    elif state == "SEARCH_LOGO":

        #result = read_cognex()
        print(result)

        if result is None:
            sleep(0.05)
            continue

        logo_status = result["logo_status"]

        print("Searching logo...")
        print("Logo status:", logo_status)

        if logo_status == "1":
            print("Logo found. Rotating 120 degrees to OCR.")

            logo_search_count = 0
            request_multivista_rotation(ROTATE_BIG)

            state = "WAIT_ROTATE_TO_OCR_DONE"

        else:
            print("Logo not found. Rotating small step.")

            logo_search_count += 1
            print_full_rotation_warning(logo_search_count, "LOGO")

            request_multivista_rotation(ROTATE_SMALL)

            state = "WAIT_LOGO_SEARCH_STEP_DONE"


    # --------------------------------------------------------
    # 11. Esperar giro pequeño durante búsqueda de logo
    # --------------------------------------------------------
    elif state == "WAIT_LOGO_SEARCH_STEP_DONE":

        rotate_done = read_bool(PLC2, PLC2_FLAGS_ADDR, ROTATE_DONE_BIT)

        if rotate_done:
            print("PLC2 finished logo search step")
            clear_multivista_rotation_request()
            state = "WAIT_LOGO_SEARCH_STEP_RESET"


    # --------------------------------------------------------
    # 12. Esperar que PLC2 baje RotateDone del giro pequeño
    # --------------------------------------------------------
    elif state == "WAIT_LOGO_SEARCH_STEP_RESET":

        rotate_done = read_bool(PLC2, PLC2_FLAGS_ADDR, ROTATE_DONE_BIT)

        if not rotate_done:
            print("Logo search step handshake finished")
            
            sleep(4)
            state = "SEARCH_LOGO"


    # --------------------------------------------------------
    # 13. Esperar giro de 120° hacia OCR
    # --------------------------------------------------------
    elif state == "WAIT_ROTATE_TO_OCR_DONE":

        rotate_done = read_bool(PLC2, PLC2_FLAGS_ADDR, ROTATE_DONE_BIT)

        if rotate_done:
            print("PLC2 finished rotation to OCR")
            clear_multivista_rotation_request()
            state = "WAIT_ROTATE_TO_OCR_RESET"


    # --------------------------------------------------------
    # 14. Esperar reset de RotateDone después de girar a OCR
    # --------------------------------------------------------
    elif state == "WAIT_ROTATE_TO_OCR_RESET":

        rotate_done = read_bool(PLC2, PLC2_FLAGS_ADDR, ROTATE_DONE_BIT)

        if not rotate_done:
            print("Rotation to OCR handshake finished")
            sleep(4)
            state = "READ_OCR"


    # --------------------------------------------------------
    # 15. Leer OCR
    # --------------------------------------------------------
    elif state == "READ_OCR":

        #result = read_cognex()
        print(result)

        if result is None:
            sleep(0.05)
            continue

        ocr_text = result["ocr_text"]

        print("Reading OCR...")
        print("OCR text:", ocr_text)

        state = "EVALUATE_OCR"


    # --------------------------------------------------------
    # 16. Evaluar OCR
    # --------------------------------------------------------
    elif state == "EVALUATE_OCR":

        if ocr_text == "Y" or ocr_text == "B":
            ocr_color = ocr_text

            print("OCR saved color:", ocr_color)
            print("Rotating 120 degrees to color/content.")

            ocr_retry_count = 0
            request_multivista_rotation(ROTATE_BIG)

            state = "WAIT_ROTATE_TO_COLOR_DONE"

        else:
            print("OCR not readable. Rotating small correction.")

            ocr_retry_count += 1

            if ocr_retry_count >= MAX_OCR_READ_ATTEMPTS:
                print("OCR still unreadable after small corrections.")
                print("Returning to SEARCH_LOGO for relocalization.")

                ocr_retry_count = 0
                state = "SEARCH_LOGO"

            else:
                request_multivista_rotation(ROTATE_SMALL)
                state = "WAIT_OCR_CORRECTION_DONE"


    # --------------------------------------------------------
    # 17. Esperar corrección pequeña para OCR
    # --------------------------------------------------------
    elif state == "WAIT_OCR_CORRECTION_DONE":

        rotate_done = read_bool(PLC2, PLC2_FLAGS_ADDR, ROTATE_DONE_BIT)

        if rotate_done:
            print("PLC2 finished OCR correction")
            clear_multivista_rotation_request()
            state = "WAIT_OCR_CORRECTION_RESET"


    # --------------------------------------------------------
    # 18. Esperar reset de RotateDone de corrección OCR
    # --------------------------------------------------------
    elif state == "WAIT_OCR_CORRECTION_RESET":

        rotate_done = read_bool(PLC2, PLC2_FLAGS_ADDR, ROTATE_DONE_BIT)

        if not rotate_done:
            print("OCR correction handshake finished")
            sleep(4)
            state = "READ_OCR"


    # --------------------------------------------------------
    # 19. Esperar giro de 120° hacia color físico
    # --------------------------------------------------------
    elif state == "WAIT_ROTATE_TO_COLOR_DONE":

        rotate_done = read_bool(PLC2, PLC2_FLAGS_ADDR, ROTATE_DONE_BIT)

        if rotate_done:
            print("PLC2 finished rotation to color/content")
            clear_multivista_rotation_request()
            state = "WAIT_ROTATE_TO_COLOR_RESET"


    # --------------------------------------------------------
    # 20. Esperar reset de RotateDone después de girar a color
    # --------------------------------------------------------
    elif state == "WAIT_ROTATE_TO_COLOR_RESET":

        rotate_done = read_bool(PLC2, PLC2_FLAGS_ADDR, ROTATE_DONE_BIT)

        if not rotate_done:
            print("Rotation to color/content handshake finished")
            sleep(4)
            state = "READ_COLOR"


    # --------------------------------------------------------
    # 21. Leer color físico
    # --------------------------------------------------------
    elif state == "READ_COLOR":

        #result = read_cognex()
        print(result)

        if result is None:
            sleep(0.05)
            continue

        mean_color = result["mean_color"]

        print("Reading physical color...")
        print("Mean color:", mean_color)

        state = "EVALUATE_COLOR"


    # --------------------------------------------------------
    # 22. Evaluar color físico contra OCR
    # --------------------------------------------------------
    elif state == "EVALUATE_COLOR":

        physical_color = detect_color(mean_color)

        print("Physical color:", physical_color)
        print("OCR saved color:", ocr_color)

        if physical_color == ocr_color:
            print("Vaccine condition: OK")
            diagnostic = DIAG_OK
            state = "SEND_DIAGNOSTIC_TO_PLC1"

        else:
            print("Vaccine condition: RETRY")
            diagnostic = DIAG_RETRY
            state = "SEND_DIAGNOSTIC_TO_PLC1"


    # --------------------------------------------------------
    # 23. Mandar diagnóstico final a los PLCs
    # --------------------------------------------------------
    elif state == "SEND_DIAGNOSTIC_TO_PLC1":

        send_diagnostic_to_plc1(diagnostic)
        send_diagnostic_to_plc2(diagnostic)
        state = "WAIT_PLC1_DIAGNOSTIC_RECEIVED"


    # --------------------------------------------------------
    # 24. Esperar que PLC1 confirme diagnóstico
    # --------------------------------------------------------
    elif state == "WAIT_PLC1_DIAGNOSTIC_RECEIVED":

        diagnostic_received = read_bool(
            PLC1,
            PLC1_FLAGS_ADDR,
            DIAGNOSTIC_RECEIVED_BIT
        )

        if diagnostic_received:
            print("PLC1 received diagnostic")
            clear_diagnostic_to_plc1()
            state = "WAIT_PLC1_DIAGNOSTIC_RECEIVED_RESET"


    # --------------------------------------------------------
    # 25. Esperar que PLC1 baje DiagnosticReceived
    # --------------------------------------------------------
    elif state == "WAIT_PLC1_DIAGNOSTIC_RECEIVED_RESET":

        diagnostic_received = read_bool(
            PLC1,
            PLC1_FLAGS_ADDR,
            DIAGNOSTIC_RECEIVED_BIT
        )

        if not diagnostic_received:
            print("Diagnostic handshake finished")
            clear_inspection_done_to_plc2()
            state = "WAIT_CYCLE_END"


    # --------------------------------------------------------
    # 26. Esperar que el PLC1 quite MultivistaReady
    # --------------------------------------------------------
    elif state == "WAIT_CYCLE_END":

        multivista_ready = read_bool(
            PLC1,
            PLC1_FLAGS_ADDR,
            MULTIVISTA_READY_BIT
        )

        if not multivista_ready:
            print("Cycle finished. Waiting for next cup.")
            state = "WAIT_FOR_DELTA"


    else:
        print("Unknown state:", state)
        state = "WAIT_CUP"


    sleep(0.05)