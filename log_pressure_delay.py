# log_pressure_clean_prestart.py
import serial
import csv
import time

PORT = "COM3"
BAUD = 115200
OUTFILE = "finaltest_12floors_new.csv"

START_DELAY_SEC = 0      # how long to log before sending 's'

with serial.Serial(PORT, BAUD, timeout=1) as ser, open(OUTFILE, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp_ms", "pressure_kPa"])

    print(f"Opened {PORT} at {BAUD} baud")

    # — Wait for Arduino reboot —
    time.sleep(2.0)
    ser.reset_input_buffer()

    print("Logging started BEFORE starting test...")

    start_ms = int(time.time() * 1000)
    start_command_sent = False
    start_send_time = start_ms + int(START_DELAY_SEC * 1000)

    try:
        while True:
            now_ms = int(time.time() * 1000)

            # ---- Send start command after delay ----
            if not start_command_sent and now_ms >= start_send_time:
                ser.write(b's\n')
                ser.flush()
                start_command_sent = True
                print(">>> Sent START command to Arduino")

            # ---- Read Arduino ----
            raw = ser.readline().decode(errors="replace").strip()
            if not raw:
                continue

            # Try to extract pressure field P=<value>
            fields = raw.split(',')
            p_val = None

            for field in fields:
                field = field.strip()
                if field.startswith("P="):
                    try:
                        p_val = float(field[2:])
                    except ValueError:
                        p_val = None
                    break

            if p_val is None:
                # Other info lines (like welcome message, stage info)
                print("INFO:", raw)
                continue

            # ---- Log pressure ----
            t_ms = now_ms - start_ms
            writer.writerow([t_ms, p_val])
            f.flush()
            print(t_ms, p_val)

    except KeyboardInterrupt:
        print("\nStopping...")

        # Stop Arduino test
        try:
            ser.write(b'x\n')
            ser.flush()
            print(">>> Sent STOP command to Arduino")
            time.sleep(0.2)
        except Exception as e:
            print("Error while sending stop:", e)

print("Done.")
