# Co-Pilot

Co-Pilot is a computer-vision-based virtual drawing and productivity assistant that lets users interact with a computer using hand gestures.

## Features
- Real-time hand gesture recognition
- Gesture-controlled digital drawing
- Multiple drawing colors
- Gesture-based canvas clearing
- Screenshot capture
- Built-in keyboard and notes system
- Save, open, and share notes
- Windows executable version
- Hand recognition can be enabled or disabled when needed

## Technologies
- Python
- OpenCV
- MediaPipe
- Tkinter
- NumPy
- PyAutoGUI
- PyGetWindow
- Pillow

## Fleet Tracker

A separate live fleet-tracking application is included under `fleet_tracker/`.

It provides Developer, Driver, and Student interfaces, SQLite local logging, Supabase remote driver locations, TkinterMapView maps, and Windows/IP geolocation support.

See `fleet_tracker/README.md` for setup and configuration details.

## Project

The main Co-Pilot application is in `CO_PILOT.py`. The fleet tracker is intentionally kept in its own `fleet_tracker/` directory.

## Run Co-Pilot

Install the required Python packages and run:

```bash
python CO_PILOT.py
```
