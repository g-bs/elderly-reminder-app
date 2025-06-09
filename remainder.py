import time
from twilio.rest import Client
from datetime import datetime
import json
import os
from dotenv import load_dotenv
from collections import defaultdict

# Load credentials from .env file
load_dotenv()
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
from_number = os.getenv("TWILIO_FROM_NUMBER")

client = Client(account_sid, auth_token)

# ✅ Set to True to prevent real calls during development
TEST_MODE = True

def format_phone_number(raw_number):
    """Ensure phone number is in E.164 format for Twilio (+ followed by digits)"""
    number = raw_number.strip().replace(" ", "").replace("-", "")
    if not number.startswith("+"):
        number = "+" + number
    if not number[1:].isdigit():
        print(f"⚠️ Invalid phone number format: {number}")
        return None
    return number

def send_voice_reminder(to_number, patient_name, medicine_names, time_str, frequency):
    formatted_number = format_phone_number(to_number)
    if not formatted_number:
        print(f"❌ Skipping call: invalid number for {patient_name}")
        return

    if len(medicine_names) == 1:
        meds_text = medicine_names[0]
    else:
        meds_text = ", ".join(medicine_names)

    if TEST_MODE:
        print(f"[TEST MODE] Would send reminder to {formatted_number} for {patient_name}: "
              f"Take {meds_text} at {time_str} | Frequency: {frequency}")
    else:
        try:
            call = client.calls.create(
                twiml=f'<Response><Say voice="alice">Hello {patient_name}, this is a reminder to take your medicines '
                      f'{meds_text} at {time_str}. Frequency: {frequency}.</Say></Response>',
                to=formatted_number,
                from_=from_number
            )
            print(f"✅ Sent call SID: {call.sid} to {formatted_number}")
        except Exception as e:
            print(f"❌ Failed to send call to {formatted_number}: {e}")

def check_and_send_reminders():
    try:
        with open("med_schedule.json", "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"⚠️ Error reading med_schedule.json: {e}")
        return

    now = datetime.now()
    current_time_str = now.strftime("%H:%M")
    current_date_str = now.strftime("%Y-%m-%d")
    current_weekday = now.strftime("%A").lower()

    print(f"[INFO] Checking reminders for {current_time_str} on {current_weekday}, {current_date_str}")

    # --- Collect reminders ---
    reminders_to_send = defaultdict(lambda: defaultdict(list))
    # structure: reminders_to_send[(patient_name, phone)][time_str] → list of medicine names

    # Track ONCE medications to remove:
    once_alarms_to_remove = defaultdict(list)  # patient_name → list of med indices to remove

    for patient_name, info in data.get("patients", {}).items():
        phone = info.get("phone")
        if not phone:
            print(f"⚠️ Skipping patient {patient_name} — no phone number.")
            continue

        for i, med in enumerate(info.get("medications", [])):
            med_name = med.get("name", "Unnamed")
            times = med.get("times", [])
            frequency = med.get("frequency", "daily").lower()

            if frequency == "once":
                datetime_str = med.get("datetime")
                if datetime_str:
                    try:
                        scheduled_dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
                        if now.strftime("%Y-%m-%d") == scheduled_dt.strftime("%Y-%m-%d") and \
                                current_time_str == scheduled_dt.strftime("%H:%M"):
                            print(f"[MATCH] ONCE for {patient_name}: {med_name} at {scheduled_dt.strftime('%H:%M')}")
                            reminders_to_send[(patient_name, phone)][scheduled_dt.strftime("%H:%M")].append(med_name)

                            # MARK THIS ONCE alarm for removal:
                            once_alarms_to_remove[patient_name].append(i)

                        else:
                            print(f"[SKIP] ONCE for {patient_name}: {med_name} — Not time yet.")
                    except Exception as e:
                        print(f"⚠️ Error parsing 'once' datetime for {patient_name}: {e}")

            elif frequency == "daily":
                if current_time_str in times:
                    print(f"[MATCH] DAILY for {patient_name}: {med_name} at {current_time_str}")
                    reminders_to_send[(patient_name, phone)][current_time_str].append(med_name)
                else:
                    print(f"[SKIP] DAILY for {patient_name}: {med_name} — Not time yet.")

            elif frequency == "weekly":
                scheduled_day = med.get("day", "").lower()
                if scheduled_day == current_weekday:
                    if current_time_str in times:
                        print(f"[MATCH] WEEKLY for {patient_name}: {med_name} at {current_time_str} on {current_weekday}")
                        reminders_to_send[(patient_name, phone)][current_time_str].append(med_name)
                    else:
                        print(f"[SKIP] WEEKLY for {patient_name}: {med_name} — Not time yet.")
                else:
                    print(f"[SKIP] WEEKLY for {patient_name}: {med_name} — Today is {current_weekday}, not {scheduled_day}.")

            else:
                print(f"[WARN] Unknown frequency '{frequency}' for {patient_name}: {med_name}")

    # --- Send grouped reminders ---
    for (patient_name, phone), times_dict in reminders_to_send.items():
        for time_str, medicine_names in times_dict.items():
            send_voice_reminder(phone, patient_name, medicine_names, time_str, "grouped")

    # --- Remove ONCE alarms if triggered ---
    for patient_name, indices in once_alarms_to_remove.items():
        if not indices:
            continue
        print(f"[INFO] Removing triggered ONCE alarms for {patient_name}...")

        meds = data["patients"][patient_name]["medications"]
        # Remove in reverse order to avoid index shift
        for i in sorted(indices, reverse=True):
            removed_med = meds.pop(i)
            print(f"✅ Removed ONCE alarm for {removed_med['name']} from {patient_name}")

    # Save updated file if any ONCE removed
    if once_alarms_to_remove:
        try:
            with open("med_schedule.json", "w") as f:
                json.dump(data, f, indent=4)
            print("[INFO] Saved updated med_schedule.json after ONCE alarm cleanup.")
        except Exception as e:
            print(f"⚠️ Error saving med_schedule.json: {e}")

if __name__ == "__main__":
    print("[INFO] Reminder system started...")
    while True:
        check_and_send_reminders()
        time.sleep(60)  # Check every minute
