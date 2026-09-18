import pyautogui
import pygetwindow
import PIL.Image
import os
import cv2
import numpy as np
import mediapipe as mp
from collections import deque
import datetime
import tkinter as tk
import threading
import subprocess
import sys

date = datetime.datetime.now()



#win= Tk()


#win.geometry("1980x1080")


# colour 
bpoints = [deque(maxlen=1024)]
gpoints = [deque(maxlen=1024)]
rpoints = [deque(maxlen=1024)]
ypoints = [deque(maxlen=1024)]


# These indexes will be used to mark the points in particular arrays of specific colour
blue_index = 0
green_index = 0
red_index = 0
yellow_index = 0


#The kernel to be used for dilation purpose 
kernel = np.ones((5,5),np.uint8)


colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 255, 255)]
colorIndex = 0


# copilot setup
paintWindow = np.zeros((471,636,3),dtype=np.uint8)
paintWindow = cv2.rectangle(paintWindow, (5,1), (80,65), (255,255,255), 2)
paintWindow = cv2.rectangle(paintWindow, (90,1), (160,65), (255,0,0), 2)
paintWindow = cv2.rectangle(paintWindow, (170,1), (255,65), (0,255,0), 2)
paintWindow = cv2.rectangle(paintWindow, (265,1), (345,65), (0,0,255), 2)
paintWindow = cv2.rectangle(paintWindow, (355,1), (435,65), (0,255,255), 2)
paintWindow = cv2.rectangle(paintWindow, (445,1), (525,65), (255,255,255), 2)
paintWindow = cv2.rectangle(paintWindow, (535,1), (620,65), (255,255,255), 2)
#text input
cv2.putText(paintWindow, "CLEAR", (17, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2, cv2.LINE_AA)
cv2.putText(paintWindow, "BLUE", (105, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2, cv2.LINE_AA)
cv2.putText(paintWindow, "GREEN", (185, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2, cv2.LINE_AA)
cv2.putText(paintWindow, "RED", (285, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2, cv2.LINE_AA)
cv2.putText(paintWindow, "YELLOW", (366, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2, cv2.LINE_AA)
cv2.putText(paintWindow, "PRINT", (465, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2, cv2.LINE_AA)
cv2.putText(paintWindow, "KEYBOARD", (540,33), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2, cv2.LINE_AA)
cv2.namedWindow('Paint', cv2.WINDOW_AUTOSIZE)


# initialize mediapipe
mpHands = mp.solutions.hands
hands = mpHands.Hands(max_num_hands=1, min_detection_confidence=0.7)
mpDraw = mp.solutions.drawing_utils


# ---------------- KEYBOARD / NOTES ----------------
notes_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes")
os.makedirs(notes_folder, exist_ok=True)

keyboard_window = None
keyboard_text = None
keyboard_note_list = None
keyboard_current_file = None
keyboard_open_lock = False
screenshot_cooldown = False

# Hand recognition starts OFF. Turn it on only when needed.
hand_recognition_enabled = False
control_window = None
hand_status_label = None


def update_hand_button():
    if control_window is None or hand_status_label is None:
        return
    if hand_recognition_enabled:
        hand_status_label.config(text="HAND RECOGNITION: ON", fg="green")
    else:
        hand_status_label.config(text="HAND RECOGNITION: OFF", fg="red")


def toggle_hand_recognition():
    global hand_recognition_enabled
    hand_recognition_enabled = not hand_recognition_enabled
    update_hand_button()
    print("Hand recognition:", "ON" if hand_recognition_enabled else "OFF")


def open_control_window():
    global control_window, hand_status_label

    control_window = tk.Tk()
    control_window.title("Co-Pilot Controls")
    control_window.geometry("320x190")
    control_window.resizable(False, False)

    tk.Label(
        control_window, text="Co-Pilot",
        font=("Arial", 18, "bold")
    ).pack(pady=(15, 5))

    hand_status_label = tk.Label(
        control_window,
        text="HAND RECOGNITION: OFF",
        font=("Arial", 11, "bold"),
        fg="red"
    )
    hand_status_label.pack(pady=5)

    tk.Button(
        control_window,
        text="TURN HAND RECOGNITION ON / OFF",
        command=toggle_hand_recognition,
        width=30,
        height=2
    ).pack(pady=8)

    tk.Label(
        control_window,
        text="Turn it on only when you want to use hand controls.",
        font=("Arial", 9)
    ).pack()

    control_window.protocol("WM_DELETE_WINDOW", control_window.withdraw)


def update_control_window():
    if control_window is not None:
        try:
            control_window.update_idletasks()
            control_window.update()
        except tk.TclError:
            pass


def refresh_notes():
    if keyboard_note_list is None:
        return
    keyboard_note_list.delete(0, tk.END)
    for filename in sorted(os.listdir(notes_folder)):
        if filename.lower().endswith(".txt"):
            keyboard_note_list.insert(tk.END, filename)

def new_note():
    global keyboard_current_file
    keyboard_current_file = None
    keyboard_text.delete("1.0", tk.END)
    keyboard_text.focus_set()

def save_note():
    global keyboard_current_file
    content = keyboard_text.get("1.0", tk.END).rstrip()

    if keyboard_current_file is None:
        existing = [
            f for f in os.listdir(notes_folder)
            if f.lower().startswith("note_") and f.lower().endswith(".txt")
        ]
        numbers = []
        for filename in existing:
            try:
                numbers.append(int(filename[5:-4]))
            except ValueError:
                pass
        next_number = max(numbers, default=0) + 1
        keyboard_current_file = os.path.join(
            notes_folder, f"note_{next_number}.txt"
        )

    with open(keyboard_current_file, "w", encoding="utf-8") as file:
        file.write(content)

    refresh_notes()

    # Close the keyboard window immediately after a successful save.
    close_keyboard()


def share_note():
    """Save a separate shareable copy of the current note to computer storage."""
    global keyboard_current_file

    try:
        content = keyboard_text.get("1.0", tk.END).rstrip()

        if keyboard_current_file is None:
            existing = [
                f for f in os.listdir(notes_folder)
                if f.lower().startswith("note_") and f.lower().endswith(".txt")
            ]
            numbers = []
            for filename in existing:
                try:
                    numbers.append(int(filename[5:-4]))
                except ValueError:
                    pass

            next_number = max(numbers, default=0) + 1
            keyboard_current_file = os.path.join(
                notes_folder, f"note_{next_number}.txt"
            )
            with open(keyboard_current_file, "w", encoding="utf-8") as file:
                file.write(content)

        share_folder = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "shared_profiles"
        )
        os.makedirs(share_folder, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(keyboard_current_file))[0]
        share_file = os.path.join(share_folder, f"{base_name}_shared.txt")

        with open(share_file, "w", encoding="utf-8") as file:
            file.write(content)

        print(f"Shareable profile saved to: {share_file}")

        try:
            if sys.platform.startswith("win"):
                os.startfile(share_folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", share_folder])
            else:
                subprocess.Popen(["xdg-open", share_folder])
        except Exception as e:
            print(f"Could not open share folder: {e}")

        close_keyboard()

    except Exception as e:
        print(f"Share error: {e}")

def open_note(event=None):
    global keyboard_current_file

    selection = keyboard_note_list.curselection()
    if not selection:
        return

    filename = keyboard_note_list.get(selection[0])
    keyboard_current_file = os.path.join(notes_folder, filename)

    with open(keyboard_current_file, "r", encoding="utf-8") as file:
        content = file.read()

    keyboard_text.delete("1.0", tk.END)
    keyboard_text.insert("1.0", content)
    keyboard_text.focus_set()

def close_keyboard():
    global keyboard_window, keyboard_text, keyboard_note_list
    global keyboard_current_file, keyboard_open_lock

    if keyboard_window is not None:
        try:
            keyboard_window.destroy()
        except tk.TclError:
            pass

    keyboard_window = None
    keyboard_text = None
    keyboard_note_list = None
    keyboard_current_file = None
    keyboard_open_lock = False

def open_keyboard():
    global keyboard_window, keyboard_text, keyboard_note_list
    global keyboard_open_lock

    if keyboard_window is not None:
        try:
            if keyboard_window.winfo_exists():
                keyboard_window.lift()
                keyboard_window.focus_force()
                keyboard_open_lock = True
                return
        except tk.TclError:
            close_keyboard()

    keyboard_window = tk.Tk()
    keyboard_window.title("Co-Pilot Keyboard")
    keyboard_window.geometry("800x500")
    keyboard_window.protocol("WM_DELETE_WINDOW", close_keyboard)

    left_frame = tk.Frame(keyboard_window)
    left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

    tk.Label(left_frame, text="Saved Notes").pack()

    keyboard_note_list = tk.Listbox(left_frame, width=25)
    keyboard_note_list.pack(fill=tk.Y, expand=True)
    keyboard_note_list.bind("<Double-Button-1>", open_note)

    tk.Button(left_frame, text="NEW NOTE", command=new_note).pack(fill=tk.X, pady=4)
    tk.Button(left_frame, text="SAVE NOTE", command=save_note).pack(fill=tk.X, pady=4)
    tk.Button(left_frame, text="OPEN NOTE", command=open_note).pack(fill=tk.X, pady=4)
    tk.Button(left_frame, text="SHARE NOTE", command=share_note).pack(fill=tk.X, pady=4)

    keyboard_text = tk.Text(keyboard_window, wrap=tk.WORD)
    keyboard_text.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

    refresh_notes()
    keyboard_text.focus_set()

# --------------------------------------------------

def take_screenshot():
    """Capture the Paint window without blocking the webcam/main application loop."""
    try:
        save_folder = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "images"
        )
        os.makedirs(save_folder, exist_ok=True)

        name = datetime.datetime.now().strftime("screenshot_%Y%m%d_%H%M%S_%f")
        file_location = os.path.join(save_folder, f"{name}.png")

        windows = pygetwindow.getWindowsWithTitle("Paint")
        if not windows:
            print("Paint window not found; screenshot skipped.")
            return

        window = windows[0]
        left, top = window.topleft
        right, bottom = window.bottomright

        # Take/crop the screenshot in a background thread so the
        # MediaPipe + OpenCV loop keeps running.
        screenshot = pyautogui.screenshot()
        im = screenshot.crop((left, top, right, bottom))
        im.save(file_location)

        print(f"Screenshot saved: {file_location}")

        # Open the image without waiting for the main application.
        try:
            if sys.platform.startswith("win"):
                os.startfile(file_location)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", file_location])
            else:
                subprocess.Popen(["xdg-open", file_location])
        except Exception as e:
            print(f"Could not open screenshot automatically: {e}")

    except Exception as e:
        print(f"Screenshot error: {e}")


def start_screenshot():
    """Start screenshot capture in a daemon thread, with a short cooldown."""
    global screenshot_cooldown
    if screenshot_cooldown:
        return

    screenshot_cooldown = True
    threading.Thread(target=take_screenshot, daemon=True).start()

    # Re-arm after 1 second so holding the finger on PRINT does not
    # create hundreds of screenshots.
    def reset_cooldown():
        global screenshot_cooldown
        screenshot_cooldown = False

    threading.Timer(1.0, reset_cooldown).start()


# --------------------------------------------------

# Open Co-Pilot Controls. Hand recognition is OFF at startup.
open_control_window()

# Initialize the webcam
cap = cv2.VideoCapture(0)
ret = True
while ret:
    # Read each frame from the webcam
    ret, frame = cap.read()


    x, y, c = frame.shape


    # Flip the frame vertically
    frame = cv2.flip(frame, 1)
    #hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    framergb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    #pain setup
    frame = cv2.rectangle(frame, (5,1), (80,65), (0,0,0), 2)
    frame = cv2.rectangle(frame, (90,1), (160,65), (255,0,0), 2)
    frame = cv2.rectangle(frame, (170,1), (255,65), (0,255,0), 2)
    frame = cv2.rectangle(frame, (265,1), (345,65), (0,0,255), 2)
    frame = cv2.rectangle(frame, (355,1), (435,65), (0,255,255), 2)
    frame = cv2.rectangle(frame, (445,1), (525,65), (0,0,0), 2)
    frame = cv2.rectangle(frame, (535,1), (620,65), (0,0,0), 2)
    #text input 
    cv2.putText(frame, "CLEAR", (17, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(frame, "BLUE", (105, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(frame, "GREEN", (185, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(frame, "RED", (285, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(frame, "YELLOW", (366, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(frame, "PRINT", (465, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(frame, "KEYBOARD", (540,33), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.line(frame,(25,25),(25,25),(0,0,0),3)
    #frame = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


    # Get hand landmark prediction only when enabled.
    result = hands.process(framergb) if hand_recognition_enabled else None
 

    # post process the result
    if hand_recognition_enabled and result is not None and result.multi_hand_landmarks:
        landmarks = []
        for handslms in result.multi_hand_landmarks:
            for lm in handslms.landmark:
                # # print(id, lm)
                # print(lm.x)
                # print(lm.y)
                lmx = int(lm.x * 640)
                lmy = int(lm.y * 480)


                landmarks.append([lmx, lmy])


            # Drawing landmarks on frames
            mpDraw.draw_landmarks(frame, handslms, mpHands.HAND_CONNECTIONS)
        fore_finger = (landmarks[8][0],landmarks[8][1])
        center = fore_finger
        thumb = (landmarks[4][0],landmarks[4][1])
        cv2.circle(frame, center, 3, (0,255,0),-1)
        if (thumb[1]-center[1]<30):
            bpoints.append(deque(maxlen=512))
            blue_index += 1
            gpoints.append(deque(maxlen=512))
            green_index += 1
            rpoints.append(deque(maxlen=512))
            red_index += 1
            ypoints.append(deque(maxlen=512))
            yellow_index += 1


        elif center[1] <= 65:
            if 5 <= center[0] <= 80: # Clear Button
                bpoints = [deque(maxlen=512)]
                gpoints = [deque(maxlen=512)]
                rpoints = [deque(maxlen=512)]
                ypoints = [deque(maxlen=512)]


                blue_index = 0
                green_index = 0
                red_index = 0
                yellow_index = 0


                paintWindow[67:,:,:] = 0      
            elif 90 <= center[0] <= 160:
                    colorIndex = 0 # Blue
            elif 170 <= center[0] <= 255:
                    colorIndex = 1 # Green
            elif 265 <= center[0] <= 345:
                    colorIndex = 2 # Red
            elif 355 <= center[0] <= 435:
                    colorIndex = 3 # Yellow
            elif 445 <= center[0] <= 525:
                    # Screenshot runs in the background.
                    # IMPORTANT: do not break the main loop here.
                    start_screenshot()

            elif 535 <= center[0] <= 620:
                if not keyboard_open_lock:
                    open_keyboard()

                
                
          


        else :
            if colorIndex == 0:
                bpoints[blue_index].appendleft(center)
            elif colorIndex == 1:
                gpoints[green_index].appendleft(center)
            elif colorIndex == 2:
                rpoints[red_index].appendleft(center)
            elif colorIndex == 3:
                ypoints[yellow_index].appendleft(center)
    # Append the next deques when nothing is detected to avois messing up
    else:
        bpoints.append(deque(maxlen=512))
        blue_index += 1
        gpoints.append(deque(maxlen=512))
        green_index += 1
        rpoints.append(deque(maxlen=512))
        red_index += 1
        ypoints.append(deque(maxlen=512))
        yellow_index += 1


    # Draw lines of all the colors on the canvas and frame
    points = [bpoints, gpoints, rpoints, ypoints]
    # for j in range(len(points[0])):
    #         for k in range(1, len(points[0][j])):
    #             if points[0][j][k - 1] is None or points[0][j][k] is None:
    #                 continue
    #             cv2.line(paintWindow, points[0][j][k - 1], points[0][j][k], colors[0], 2)
    for i in range(len(points)):
        for j in range(len(points[i])):
            for k in range(1, len(points[i][j])):
                if points[i][j][k - 1] is None or points[i][j][k] is None:
                    continue
                cv2.line(frame, points[i][j][k - 1], points[i][j][k], colors[i], 2)
                cv2.line(paintWindow, points[i][j][k - 1], points[i][j][k], colors[i], 2)


    cv2.imshow("Co-Pilot", frame) 
    cv2.imshow("Paint", paintWindow)

    if keyboard_window is not None:
        try:
            keyboard_window.update()
        except tk.TclError:
            close_keyboard()


    update_control_window()

    if cv2.waitKey(1) == ord('q'):
        break


# reset all windows
cap.release()
try:
    hands.close()
except Exception:
    pass
try:
    if keyboard_window is not None:
        close_keyboard()
    if control_window is not None:
        control_window.destroy()
except Exception:
    pass
cv2.destroyAllWindows()


