import socket
import snap7
from snap7.util import set_lreal, set_bool, get_bool, set_int
from time import sleep

COGNEX_IP = "192.168.0.90"
COGNEX_PORT = 5001
PLC1_IP = "192.168.0.1"

X_ADDR = 332
Y_ADDR = 348

PLC1_FLAGS_ADDR = 360

COORD_DATA_READY_BIT = 0
OBJECT_VALID_BIT = 1
COORD_DATA_RECEIVED_BIT = 2
ROBOT_BUSY_BIT = 3
MULTIVISTA_READY_BIT = 4
DIAGNOSTIC_READY_BIT = 5
DIAGNOSTIC_RECEIVED_BIT = 6

DIAGNOSTIC_ADDR = 232
ROBOT_READY_TO_START = 7

# Multivista ahora dentro de PLC1
MULTI_FLAGS_ADDR = 370

FLIP_REQUEST_BIT = 5
FLIP_DONE_BIT = 1
ROTATE_DONE_BIT = 2
ROTATE_REQUEST_BIT = 6
MOVE_BUSY_BIT = 4
INSPECTION_DONE_BIT = 5

ROTATE_DEGREES_ADDR = 372



FLIP_CMD_ADDR = 450
ROTATE_CMD_ADDR = 470
MISSING_CMD_ADDR = 600



DIAG_OK = 1
DIAG_NOT_OK = 2
DIAG_RETRY = 3

ROTATE_SMALL = 10
ROTATE_BIG = 120
FULL_ROTATION_STEPS = 36
MAX_OCR_READ_ATTEMPTS = 10

COLOR_THRESHOLD = 80
COINTANER_THRESHOLD = 20



#--------Reset if Missing-----------
DIAG_MISSING = 4

MISSING_RESET_BIT = 6      # Python -> PLC1
MISSING_RESET_DONE_BIT = 7 # PLC1 -> Python

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


def safe_float(value, default=0.0):
    try:
        value = value.strip()
        if value == "":
            return default
        return float(value)
    except:
        return default

#-------------------------ESTA SI JALA----------------------
# def read_cognex():
#     data = camera.recv(128).decode(errors="ignore").strip()
#     values = data.split(",")

#     while len(values) < 7:
#         values.append("0")

#     return {
#         "label": values[0].strip().upper(),
#         "x": safe_float(values[1]),
#         "y": safe_float(values[2]),
#         "blob_status": values[3].strip().upper(),
#         "logo_status": values[4].strip().upper(),
#         "ocr_text": values[5].strip().upper(),
#         "mean_color": safe_float(values[6]),
#     }


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

    if len(values) != 8:
        return None

    return {
        "label": values[0].strip(),
        "x": safe_float(values[1]),
        "y": safe_float(values[2]),
        "blob_status": values[3].strip(),
        "logo_status": values[4].strip(),
        "ocr_text": values[5].strip(),
        "mean_color": safe_float(values[6]),
        "missing": values[7].strip(),
    }





def detect_color(mean_color):
    if mean_color > COLOR_THRESHOLD:
        return "Y"
    elif mean_color < COINTANER_THRESHOLD:
        return "N"
    else:
        return "B"


def print_full_rotation_warning(counter, target_name):
    if counter > 0 and counter % FULL_ROTATION_STEPS == 0:
        print("WARNING: completed one full rotation while searching for", target_name)


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
    write_bool(PLC1, FLIP_CMD_ADDR, FLIP_REQUEST_BIT, True)
    print("Requested multivista flip")


def clear_multivista_flip_request():
    write_bool(PLC1, FLIP_CMD_ADDR, FLIP_REQUEST_BIT, False)
    print("Multivista flip request cleared")


def request_multivista_rotation(degrees):
    write_int(PLC1, 800, degrees)
    write_bool(PLC1, ROTATE_CMD_ADDR, ROTATE_REQUEST_BIT, True)
    print("Requested multivista rotation:", degrees, "degrees")


def clear_multivista_rotation_request():
    write_bool(PLC1, ROTATE_CMD_ADDR, ROTATE_REQUEST_BIT, False)
    print("Multivista rotation request cleared")


def send_diagnostic_to_plc1(diagnostic_code):
    write_int(PLC1, DIAGNOSTIC_ADDR, diagnostic_code)
    write_bool(PLC1, PLC1_FLAGS_ADDR, DIAGNOSTIC_READY_BIT, True)
    print("Diagnostic sent to PLC1:", diagnostic_code)


def clear_diagnostic_to_plc1():
    write_bool(PLC1, PLC1_FLAGS_ADDR, DIAGNOSTIC_READY_BIT, False)
    print("Diagnostic request cleared")


def clear_inspection_done():
    write_bool(PLC1, MULTI_FLAGS_ADDR, INSPECTION_DONE_BIT, False)
    print("InspectionDone cleared")


def is_missing(result):
    return result is not None and result["missing"] == "1"


def request_missing_reset():
    write_bool(PLC1, MISSING_CMD_ADDR, MISSING_RESET_BIT, True)
    print("Missing reset requested")


def clear_missing_reset():
    write_bool(PLC1, MISSING_CMD_ADDR, MISSING_RESET_BIT, False)
    print("Missing reset cleared")

def handle_missing(result):
    global diagnostic, counter_degrees, state

    if is_missing(result):
        diagnostic = DIAG_MISSING

        if counter_degrees != 0:
            request_multivista_rotation(-counter_degrees)
            state = "WAIT_MISSING_RETURN_ROTATION_DONE"
        else:
            request_missing_reset()
            state = "WAIT_MISSING_RESET_DONE"

        return True

    return False


# Cleanup inicial
write_bool(PLC1, PLC1_FLAGS_ADDR, COORD_DATA_READY_BIT, False)
write_bool(PLC1, PLC1_FLAGS_ADDR, OBJECT_VALID_BIT, False)
write_bool(PLC1, PLC1_FLAGS_ADDR, DIAGNOSTIC_READY_BIT, False)

write_bool(PLC1, MULTI_FLAGS_ADDR, FLIP_REQUEST_BIT, False)
write_bool(PLC1, MULTI_FLAGS_ADDR, ROTATE_REQUEST_BIT, False)
write_bool(PLC1, MULTI_FLAGS_ADDR, INSPECTION_DONE_BIT, False)
write_bool(PLC1, MISSING_CMD_ADDR, MISSING_RESET_BIT, False)

x = 0.0
y = 0.0
ocr_color = None
diagnostic = None
logo_search_count = 0
ocr_retry_count = 0
counter_degrees = 0

state = "WAIT_FOR_DELTA"
printed_not_ready = False


while True:
    result = read_cognex()
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

    elif state == "WAIT_CUP":

        robot_busy = read_bool(PLC1, PLC1_FLAGS_ADDR, ROBOT_BUSY_BIT)
        coord_received = read_bool(PLC1, PLC1_FLAGS_ADDR, COORD_DATA_RECEIVED_BIT)

        if not robot_busy and not coord_received:
            sleep(0.5)
            result = read_cognex()
            print(result)

            # if result is None:
            #     sleep(0.05)
            #     continue

            if result["label"] == "1":
                print("Vacuna detected")
                x = result["x"]
                y = result["y"]
                #print("Vacuna detected")
                state = "SEND_COORDS_TO_PLC1"
            else:
                x = 0.0
                y = 0.0
                print("NoVacuna detected. Waiting...")

    elif state == "SEND_COORDS_TO_PLC1":
        send_coordinates_to_plc1(x, y)
        state = "WAIT_PLC1_COORD_RECEIVED"

    elif state == "WAIT_PLC1_COORD_RECEIVED":

        coord_received = read_bool(PLC1, PLC1_FLAGS_ADDR, COORD_DATA_RECEIVED_BIT)

        if coord_received:
            print("PLC1 received coordinates")
            state = "WAIT_PLC1_COORD_RECEIVED_RESET"

    elif state == "WAIT_PLC1_COORD_RECEIVED_RESET":

        coord_received = read_bool(PLC1, PLC1_FLAGS_ADDR, COORD_DATA_RECEIVED_BIT)

        if coord_received:
            print("Coordinate handshake finished")
            print("Robot moving to position.")
            state = "WAIT_MULTIVISTA_READY"

    elif state == "WAIT_MULTIVISTA_READY":

        multivista_ready = read_bool(PLC1, PLC1_FLAGS_ADDR, MULTIVISTA_READY_BIT)

        if multivista_ready:
            print("Cup is in multivista position")
            clear_coordinate_request_to_plc1()

            ocr_color = None
            diagnostic = None
            logo_search_count = 0
            ocr_retry_count = 0
            counter_degrees = 0

            state = "READ_TOP_CAMERA"

    elif state == "READ_TOP_CAMERA":

        result = read_cognex()
        print(result)
        
        if handle_missing(result):
            continue

        # if result is None:
        #     sleep(0.05)
        #     continue

        blob_status = result["blob_status"]

        print("Top inspection:")
        print("Blob status:", blob_status)

        state = "EVALUATE_TOP_BLOB"

    elif state == "EVALUATE_TOP_BLOB":

        if blob_status == "1":
            print("Scratch detected on lid")
            diagnostic = DIAG_NOT_OK
            state = "SEND_DIAGNOSTIC_TO_PLC1"
        else:
            print("No scratch detected. Requesting flip.")
            request_multivista_flip()
            state = "WAIT_FLIP_DONE"

    elif state == "WAIT_FLIP_DONE":

        flip_done = read_bool(PLC1, MULTI_FLAGS_ADDR, FLIP_DONE_BIT)

        if flip_done:
            print("Multivista finished flip")
            clear_multivista_flip_request()
            state = "WAIT_FLIP_DONE_RESET"

    elif state == "WAIT_FLIP_DONE_RESET":

        flip_done = read_bool(PLC1, MULTI_FLAGS_ADDR, FLIP_DONE_BIT)

        if not flip_done:
            print("Flip handshake finished")
            sleep(2)
            
            result = read_cognex()
            print(result)
            
            if handle_missing(result):
                continue
            
            
            state = "SEARCH_LOGO"

    elif state == "SEARCH_LOGO":

        result = read_cognex()
        print(result)
        
        if handle_missing(result):
            continue

        # if result is None:
        #     sleep(0.05)
        #     continue

        logo_status = result["logo_status"]

        print("Searching logo...")
        print("Logo status:", logo_status)

        if logo_status == "1":
            print("Logo found. Rotating 120 degrees to OCR.")
            logo_search_count = 0
            request_multivista_rotation(ROTATE_BIG)
            counter_degrees += ROTATE_BIG
            state = "WAIT_ROTATE_TO_OCR_DONE"
        else:
            print("Logo not found. Rotating small step.")
            logo_search_count += 1
            print_full_rotation_warning(logo_search_count, "LOGO")
            request_multivista_rotation(ROTATE_SMALL)
            counter_degrees += ROTATE_SMALL
            state = "WAIT_LOGO_SEARCH_STEP_DONE"

    elif state == "WAIT_LOGO_SEARCH_STEP_DONE":

        rotate_done = read_bool(PLC1, MULTI_FLAGS_ADDR, ROTATE_DONE_BIT)

        if rotate_done:
            print("Finished logo search step")
            clear_multivista_rotation_request()
            state = "WAIT_LOGO_SEARCH_STEP_RESET"

    elif state == "WAIT_LOGO_SEARCH_STEP_RESET":

        rotate_done = read_bool(PLC1, MULTI_FLAGS_ADDR, ROTATE_DONE_BIT)

        if not rotate_done:
            print("Logo search step handshake finished")
            sleep(2)
            
            result = read_cognex()
            print(result)
        
            if handle_missing(result):
                continue
            
            
            state = "SEARCH_LOGO"

    elif state == "WAIT_ROTATE_TO_OCR_DONE":

        rotate_done = read_bool(PLC1, MULTI_FLAGS_ADDR, ROTATE_DONE_BIT)

        if rotate_done:
            print("Finished rotation to OCR")
            clear_multivista_rotation_request()
            state = "WAIT_ROTATE_TO_OCR_RESET"

    elif state == "WAIT_ROTATE_TO_OCR_RESET":

        rotate_done = read_bool(PLC1, MULTI_FLAGS_ADDR, ROTATE_DONE_BIT)

        if not rotate_done:
            print("Rotation to OCR handshake finished")
            sleep(2)
            
            
            result = read_cognex()
            print(result)
        
            if handle_missing(result):
                continue
            
            
            state = "READ_OCR"

    elif state == "READ_OCR":

        result = read_cognex()
        print(result)
        
        if handle_missing(result):
            continue

        # if result is None:
        #     sleep(0.05)
        #     continue

        ocr_text = result["ocr_text"]

        print("Reading OCR...")
        print("OCR text:", ocr_text)

        state = "EVALUATE_OCR"

    elif state == "EVALUATE_OCR":

        if ocr_text == "Y" or ocr_text == "B":
            ocr_color = ocr_text
            print("OCR saved color:", ocr_color)
            request_multivista_rotation(ROTATE_BIG)
            counter_degrees += ROTATE_BIG
            ocr_retry_count = 0
            state = "WAIT_ROTATE_TO_COLOR_DONE"
        else:
            print("OCR not readable. Rotating small correction.")
            ocr_retry_count += 1

            if ocr_retry_count >= MAX_OCR_READ_ATTEMPTS:
                print("OCR still unreadable. Returning to SEARCH_LOGO.")
                ocr_retry_count = 0
                state = "SEARCH_LOGO"
            else:
                request_multivista_rotation(ROTATE_SMALL)
                counter_degrees += ROTATE_SMALL
                state = "WAIT_OCR_CORRECTION_DONE"

    elif state == "WAIT_OCR_CORRECTION_DONE":

        rotate_done = read_bool(PLC1, MULTI_FLAGS_ADDR, ROTATE_DONE_BIT)

        if rotate_done:
            print("Finished OCR correction")
            clear_multivista_rotation_request()
            state = "WAIT_OCR_CORRECTION_RESET"

    elif state == "WAIT_OCR_CORRECTION_RESET":

        rotate_done = read_bool(PLC1, MULTI_FLAGS_ADDR, ROTATE_DONE_BIT)

        if not rotate_done:
            print("OCR correction handshake finished")
            sleep(2)
            state = "READ_OCR"

    elif state == "WAIT_ROTATE_TO_COLOR_DONE":

        rotate_done = read_bool(PLC1, MULTI_FLAGS_ADDR, ROTATE_DONE_BIT)

        if rotate_done:
            print("Finished rotation to color")
            clear_multivista_rotation_request()
            state = "WAIT_ROTATE_TO_COLOR_RESET"

    elif state == "WAIT_ROTATE_TO_COLOR_RESET":

        rotate_done = read_bool(PLC1, MULTI_FLAGS_ADDR, ROTATE_DONE_BIT)

        if not rotate_done:
            print("Rotation to color handshake finished")
            sleep(2)
            state = "READ_COLOR"

    elif state == "READ_COLOR":

        result = read_cognex()
        print(result)
        
        if handle_missing(result):
            continue

        # if result is None:
        #     sleep(0.05)
        #     continue

        mean_color = result["mean_color"]

        print("Reading physical color...")
        print("Mean color:", mean_color)

        state = "EVALUATE_COLOR"

    elif state == "EVALUATE_COLOR":

        physical_color = detect_color(mean_color)

        print("Physical color:", physical_color)
        print("OCR saved color:", ocr_color)

        if physical_color == ocr_color:
            print("Vaccine condition: OK")
            diagnostic = DIAG_OK
        else:
            print("Vaccine condition: RETRY")
            diagnostic = DIAG_RETRY

        if counter_degrees != 0:
            request_multivista_rotation(-counter_degrees)
            state = "WAIT_RETURN_ROTATION_DONE"
        else:
            state = "SEND_DIAGNOSTIC_TO_PLC1"

    elif state == "WAIT_RETURN_ROTATION_DONE":

        rotate_done = read_bool(PLC1, MULTI_FLAGS_ADDR, ROTATE_DONE_BIT)

        if rotate_done:
            clear_multivista_rotation_request()
            state = "WAIT_RETURN_ROTATION_RESET"

    elif state == "WAIT_RETURN_ROTATION_RESET":

        rotate_done = read_bool(PLC1, MULTI_FLAGS_ADDR, ROTATE_DONE_BIT)

        if not rotate_done:
            print("Returned multivista to start angle")
            counter_degrees = 0
            state = "SEND_DIAGNOSTIC_TO_PLC1"

    elif state == "SEND_DIAGNOSTIC_TO_PLC1":

        send_diagnostic_to_plc1(diagnostic)
        state = "WAIT_PLC1_DIAGNOSTIC_RECEIVED"

    elif state == "WAIT_PLC1_DIAGNOSTIC_RECEIVED":

        diagnostic_received = read_bool(PLC1, PLC1_FLAGS_ADDR, DIAGNOSTIC_RECEIVED_BIT)

        if diagnostic_received:
            print("PLC1 received diagnostic")
            clear_diagnostic_to_plc1()
            state = "WAIT_PLC1_DIAGNOSTIC_RECEIVED_RESET"

    elif state == "WAIT_PLC1_DIAGNOSTIC_RECEIVED_RESET":

        diagnostic_received = read_bool(PLC1, PLC1_FLAGS_ADDR, DIAGNOSTIC_RECEIVED_BIT)

        if not diagnostic_received:
            print("Diagnostic handshake finished")
            clear_inspection_done()
            state = "WAIT_CYCLE_END"
    
    elif state == "WAIT_MISSING_RETURN_ROTATION_DONE":

        rotate_done = read_bool(PLC1, MULTI_FLAGS_ADDR, ROTATE_DONE_BIT)

        if rotate_done:
            clear_multivista_rotation_request()
            state = "WAIT_MISSING_RETURN_ROTATION_RESET"


    elif state == "WAIT_MISSING_RETURN_ROTATION_RESET":

        rotate_done = read_bool(PLC1, MULTI_FLAGS_ADDR, ROTATE_DONE_BIT)

        if not rotate_done:
            counter_degrees = 0
            request_missing_reset()
            state = "WAIT_MISSING_RESET_DONE"


    elif state == "WAIT_MISSING_RESET_DONE":

        reset_done = read_bool(PLC1, MISSING_CMD_ADDR, MISSING_RESET_DONE_BIT)

        if reset_done:
            clear_missing_reset()
            state = "WAIT_MISSING_RESET_CLEAR"


    elif state == "WAIT_MISSING_RESET_CLEAR":

        reset_done = read_bool(PLC1, MISSING_CMD_ADDR, MISSING_RESET_DONE_BIT)

        if not reset_done:
            print("Missing reset finished")
            state = "WAIT_CYCLE_END"
    
    
    
    

    elif state == "WAIT_CYCLE_END":

        multivista_ready = read_bool(PLC1, PLC1_FLAGS_ADDR, MULTIVISTA_READY_BIT)

        if not multivista_ready:
            counter_degrees = 0
            print("Cycle finished. Waiting for next cup.")
            state = "WAIT_FOR_DELTA"

    else:
        print("Unknown state:", state)
        state = "WAIT_CUP"

    sleep(0.05)