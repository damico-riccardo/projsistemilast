#import serial

#ser = serial.Serial('COM8', 9600, timeout=1)  # cambia COM3 se serve

print("Lettura seriale avviata...")

while True:
    line = ser.readline().decode(errors='ignore').strip()
    if line:
        print(line)
