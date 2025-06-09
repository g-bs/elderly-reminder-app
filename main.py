import streamlit as st
import os
import json
from datetime import datetime
import calendar


DATA_FILE = "med_schedule.json"
def normalize_name(name):
    """Normalize names by stripping whitespace and converting to lowercase"""
    return name.strip().lower()

def normalize_medicine_name(med_name):
    """Normalize medicine names by stripping whitespace and converting to lowercase"""
    return med_name.strip().lower()

def remove_empty_patients(schedule_data):
    if "patients" in schedule_data:
        empty_patients = [p for p, data in schedule_data["patients"].items() if not data.get("medications")]
        for p in empty_patients:
            del schedule_data["patients"][p]

def validate_phone_number(phone_number):
    """Validate phone number format"""
    if not phone_number:
        return False, "Phone number is required for new patients!"
    
    # Normalize input: add '+' if missing but starts with 91
    if phone_number.startswith("91") and not phone_number.startswith("+91"):
        phone_number = "+" + phone_number
    
    if not phone_number.startswith("+91"):
        return False, "Phone number must start with +91!"
    
    # Remove +91
    remaining_digits = phone_number[3:]
    # Remove spaces and dashes
    remaining_digits = remaining_digits.replace(" ", "").replace("-", "")
    
    if not remaining_digits.isdigit():
        return False, "Phone number must contain only digits after +91!"
    
    if len(remaining_digits) != 10:
        return False, "Phone number must be 10 digits after +91!"
    
    return True, ""

# Load existing data or initialize
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        schedule_data = json.load(f)
        
    # Convert old data structure to new structure if needed
    if "patients" in schedule_data:
        normalized_patients = {}
        for patient_name, patient_data in schedule_data["patients"].items():
            normalized_key = normalize_name(patient_name)

            # If old structure (list), convert to dict
            if isinstance(patient_data, list):
                normalized_patients[normalized_key] = {
                    "phone": "",
                    "display_name": patient_name,
                    "medications": []
                }
                for med in patient_data:
                    med["normalized_name"] = normalize_medicine_name(med["name"])
                    normalized_patients[normalized_key]["medications"].append(med)
            else:
                # Ensure display_name is stored
                if "display_name" not in patient_data:
                    patient_data["display_name"] = patient_name

                # *** THIS PART TO NORMALIZE OLD MEDICINES ***
                for med in patient_data.get("medications", []):
                    if "normalized_name" not in med:
                        med["normalized_name"] = normalize_medicine_name(med["name"])

                normalized_patients[normalized_key] = patient_data

        # Replace with normalized keys
        schedule_data["patients"] = normalized_patients

    else:
        schedule_data = {"patients": {}}
else:
    schedule_data = {"patients": {}}

    

st.set_page_config(page_title="EasyMed", page_icon="💊", layout="centered")
st.title("🩺 EasyMed: Elderly Medicine Reminder")
st.markdown("Enter the medicine prescription to get reminders on time!")


def check_medicine_exists(patient_medications, med_name, frequency, times=None, day=None, datetime_str=None):
    """Check if a medicine with same name and schedule already exists for a patient"""
    normalized_med_name = normalize_medicine_name(med_name)
    
    for med in patient_medications:
        if med.get("normalized_name") == normalized_med_name:
            # Check if it's the same frequency
            if med["frequency"] == frequency:
                # For Daily/Weekly, check times
                if frequency in ["Daily", "Weekly"]:
                    if med.get("times") == times:
                        # For Weekly, also check day
                        if frequency == "Weekly":
                            if med.get("day") == day:
                                return True
                        else:
                            return True
                # For Once, check datetime
                elif frequency == "Once":
                    if med.get("datetime") == datetime_str:
                        return True
    return False

if "num_doses" not in st.session_state:
    st.session_state.num_doses = 1

if "selected_frequency" not in st.session_state:
    st.session_state.selected_frequency = "Daily"
    
st.selectbox(
    "Frequency",
    ["Daily", "Once", "Weekly"],
    index=["Daily", "Once", "Weekly"].index(st.session_state.selected_frequency),
    key="selected_frequency"
)

# Interactive frequency selectbox
if st.session_state.selected_frequency in ["Daily", "Weekly"]:
    st.session_state.num_doses = st.number_input("Number of doses per day", min_value=1, max_value=5, value=st.session_state.num_doses, key="dose_input")

# --- Input Form ---
with st.form("medForm"):
    patient_name = st.text_input("Patient Name")
    med_name = st.text_input("Medicine Name")

    phone_number = st.text_input("Phone Number (with country code, e.g. +91xxxxxxxxxx)", key="phone_number_input")

    # Use frequency from session state
    frequency = st.session_state.selected_frequency

    day = None
    once_date = None
    once_time = None

    if frequency in ["Daily", "Weekly"]:
        times = []
        for i in range(st.session_state.num_doses):
            t = st.time_input(f"Time for dose {i+1}", key=f"time_input_{i}")
            times.append(t.strftime("%H:%M"))
    else:
        times = []

    if frequency == "Weekly":
        day = st.selectbox("Select day of week", list(calendar.day_name), key="main_day")

    if frequency == "Once":
        once_date = st.date_input("Select date", key="main_once_date")
        once_time = st.time_input("Select time", key="main_once_time")

    submit = st.form_submit_button("Add Reminder🔔")

if submit and med_name and patient_name:
    normalized_patient_name = normalize_name(patient_name)

    if "patients" not in schedule_data:
        schedule_data["patients"] = {}

    # Check if this is a new patient
    is_new_patient = normalized_patient_name not in schedule_data["patients"]
    
    # Validate phone number
    phone_valid = True
    error_message = ""
    
    if is_new_patient:
        # For new patients, phone number is mandatory
        phone_valid, error_message = validate_phone_number(phone_number)
    else:
        # For existing patients, validate only if phone number is provided
        if phone_number:
            phone_valid, error_message = validate_phone_number(phone_number)

    if not phone_valid:
        st.error(f"❌ {error_message}")
    else:
        # Create new patient if needed
        if is_new_patient:
            schedule_data["patients"][normalized_patient_name] = {
                "display_name": patient_name,
                "phone": phone_number,
                "medications": []
            }
        else:
            # Update phone number for existing patient if provided
            if phone_number:
                schedule_data["patients"][normalized_patient_name]["phone"] = phone_number

        # Prepare datetime string for Once frequency
        datetime_str = None
        if frequency == "Once":
            datetime_str = f"{once_date.strftime('%Y-%m-%d')} {once_time.strftime('%H:%M')}"

        # Check for duplication using normalized names
        if check_medicine_exists(schedule_data["patients"][normalized_patient_name]["medications"],
                                 med_name, frequency, times, day, datetime_str):
            st.warning("⚠️ This medicine schedule already exists for this patient.")
        else:
            # Add the medicine
            new_entry = {
                "name": med_name,
                "normalized_name": normalize_medicine_name(med_name),
                "frequency": frequency,
            }

            if frequency == "Daily":
                new_entry["times"] = times
            elif frequency == "Weekly":
                new_entry["times"] = times
                new_entry["day"] = day
            elif frequency == "Once":
                new_entry["datetime"] = datetime_str

            schedule_data["patients"][normalized_patient_name]["medications"].append(new_entry)
            remove_empty_patients(schedule_data)
            with open(DATA_FILE, "w") as f:
                json.dump(schedule_data, f, indent=4)

            # Success message
            if frequency == "Weekly":
                st.success(f"✅ Scheduled {med_name} for {patient_name} at {', '.join(times)} every {day}")
            elif frequency == "Once":
                st.success(f"✅ Scheduled {med_name} for {patient_name} on {once_date} at {once_time}")
            else:
                st.success(f"✅ Scheduled {med_name} for {patient_name} at {', '.join(times)} ({frequency})")

# --- Manage Medication Schedules ---
st.subheader("📋 Manage Medication Schedules")
if "patients" in schedule_data and schedule_data["patients"]:
    # Create display names for dropdown (use display_name if available, otherwise use key)
    patient_display_names = []
    patient_key_mapping = {}
    
    for key, patient_data in schedule_data["patients"].items():
        display_name = f"{patient_data.get('display_name', key.title())} ({key})"  # Add normalized key to guarantee uniqueness
        patient_display_names.append(display_name)
        patient_key_mapping[display_name] = key
    
    selected_display_name = st.selectbox("Select Patient", patient_display_names)
    selected_patient = patient_key_mapping[selected_display_name]


    if selected_patient:
        patient_data = schedule_data["patients"][selected_patient]
        meds = patient_data["medications"]
        
        # Display patient info
        st.info(f"📱 Phone: {patient_data.get('phone', 'Not provided')}")
        
        if meds:
            for i, med in enumerate(meds):
                col1, col2 = st.columns([4, 1])
                with col1:
                    if med["frequency"] == "Weekly":
                        st.write(f"{i+1}. **{med['name']}** at {', '.join(med['times'])} every {med.get('day', 'N/A')}")
                    elif med["frequency"] == "Once":
                        st.write(f"{i+1}. **{med['name']}** at {med.get('datetime', 'N/A')}")
                    else:
                        st.write(f"{i+1}. **{med['name']}** at {', '.join(med['times'])}")

                # Create a second row of columns for buttons (Edit + Delete side by side)
                btn_col1, btn_col2 = st.columns([1, 1])
                with btn_col1:
                    if st.button("✏️ Edit", key=f"edit_{selected_patient}_{i}"):
                        st.session_state.edit_index = i
                        st.session_state.edit_patient = selected_patient

                with btn_col2:
                    if st.button("❌ Delete", key=f"del_{selected_patient}_{i}"):
                        schedule_data["patients"][selected_patient]["medications"].pop(i)
                        # Remove patient if no medications left
                        if not schedule_data["patients"][selected_patient]["medications"]:
                            del schedule_data["patients"][selected_patient]
                        remove_empty_patients(schedule_data)
                        with open(DATA_FILE, "w") as f:
                            json.dump(schedule_data, f, indent=4)
                        st.success(f"Deleted {med['name']} for {selected_display_name}")
                        st.rerun()
            
            # "➕ Add Medicine" Button & Form per Patient
            if st.button(f"➕ Add Medicine for {selected_display_name}", key=f"add_{selected_patient}"):
                st.session_state.add_patient = selected_patient

            # If adding a medicine for this patient
            if st.session_state.get("add_patient") == selected_patient:
                # --- Dynamic dose logic ---
                add_dose_key = f"add_doses_{selected_patient}"
                temp_dose_key = f"add_doses_temp_{selected_patient}"
                
                def update_add_doses():
                    st.session_state[add_dose_key] = st.session_state[temp_dose_key]

                if add_dose_key not in st.session_state:
                    st.session_state[add_dose_key] = 1
                if temp_dose_key not in st.session_state:
                    st.session_state[temp_dose_key] = st.session_state[add_dose_key]

                # Input for number of doses (reactive)
                freq_key = f"new_freq_{selected_patient}"
                freq_value = st.session_state.setdefault(freq_key, "Daily")

                if freq_value in ["Daily", "Weekly"]:
                    st.number_input(
                        "Number of doses",
                        min_value=1,
                        max_value=5,
                        value=st.session_state[add_dose_key],
                        key=temp_dose_key,
                        on_change=update_add_doses
                    )   

                st.selectbox(
                    "Frequency",
                    ["Daily", "Once", "Weekly"],
                    index=["Daily", "Once", "Weekly"].index(st.session_state[freq_key]),
                    key=freq_key
                )
                
                with st.form(f"add_med_form_{selected_patient}"):
                    new_med_name = st.text_input("Medicine Name", key=f"new_med_name_{selected_patient}")

                    # Use frequency from session state:
                    new_freq = st.session_state[freq_key]

                    # Now you can do:
                    if new_freq in ["Daily", "Weekly"]:
                        new_times = []
                        for d in range(st.session_state[add_dose_key]):
                            t = st.time_input(f"Time for dose {d+1}", key=f"new_time_{selected_patient}_{d}")
                            new_times.append(t.strftime("%H:%M"))
                    else:
                        new_times = []

                    # Day selection for Weekly:
                    new_day = None
                    if new_freq == "Weekly":
                        new_day = st.selectbox("Select day of week", list(calendar.day_name), key=f"day_select_{selected_patient}")

                    # Once fields:
                    once_date = None
                    once_time = None
                    if new_freq == "Once":
                        once_date = st.date_input("Select date", key=f"once_date_{selected_patient}")
                        once_time = st.time_input("Select time", key=f"once_time_{selected_patient}")

                    # Submit / Cancel buttons:
                    col1, col2 = st.columns(2)
                    with col1:
                        add_submit = st.form_submit_button("➕ Add")
                    with col2:
                        cancel_add = st.form_submit_button("❌ Cancel")

                if add_submit and new_med_name:
                    # Prepare datetime string for Once frequency
                    datetime_str = None
                    if new_freq == "Once":
                        datetime_str = f"{once_date.strftime('%Y-%m-%d')} {once_time.strftime('%H:%M')}"

                    # Check for duplication using normalized names
                    if check_medicine_exists(schedule_data["patients"][selected_patient]["medications"], 
                                           new_med_name, new_freq, new_times, new_day, datetime_str):
                        st.warning("⚠️ This medicine schedule already exists for this patient.")
                    else:
                        new_entry = {
                            "name": new_med_name,
                            "normalized_name": normalize_medicine_name(new_med_name),# Keep original case for display
                            "frequency": new_freq
                        }

                        if new_freq == "Daily":
                            new_entry["times"] = new_times
                        elif new_freq == "Weekly":
                            new_entry["times"] = new_times
                            new_entry["day"] = new_day
                        elif new_freq == "Once":
                            new_entry["datetime"] = datetime_str
                                
                        schedule_data["patients"][selected_patient]["medications"].append(new_entry)
                        with open(DATA_FILE, "w") as f:
                            json.dump(schedule_data, f, indent=4)
                        
                        if new_freq == "Weekly":
                            st.success(f"✅ Added {new_med_name} for {selected_display_name} at {', '.join(new_times)} every {new_day}")
                        elif new_freq == "Once":
                            st.success(f"✅ Added {new_med_name} for {selected_display_name} on {once_date} at {once_time}")
                        else:
                            st.success(f"✅ Added {new_med_name} for {selected_display_name}")
                        
                    del st.session_state.add_patient
                    st.session_state.pop(add_dose_key, None)
                    st.session_state.pop(temp_dose_key, None)
                    st.rerun()

                elif cancel_add:
                    del st.session_state.add_patient
                    st.session_state.pop(add_dose_key, None)
                    st.session_state.pop(temp_dose_key, None)
                    st.info("✖️ Addition canceled.")
                    st.rerun()

            # --- Editing Form ---
            if "edit_index" in st.session_state and "edit_patient" in st.session_state:
                edit_index = st.session_state.edit_index
                edit_patient = st.session_state.edit_patient
                med_to_edit = schedule_data["patients"][edit_patient]["medications"][edit_index]

                st.subheader("✏️ Edit Medication")
                edit_freq_key = f"edit_freq_{edit_patient}"
                if edit_freq_key not in st.session_state:
                        st.session_state[edit_freq_key] = med_to_edit["frequency"]
                # Number of doses input OUTSIDE the form
                if "edit_num_doses" not in st.session_state:
                    st.session_state.edit_num_doses = len(med_to_edit.get("times", [1]))
                    
                st.selectbox(
                        "Edit Frequency",
                        ["Daily", "Once", "Weekly"],
                        index=["Daily", "Once", "Weekly"].index(st.session_state[edit_freq_key]),
                        key=edit_freq_key
                    )
                if st.session_state[edit_freq_key] in ["Daily", "Weekly"]:
                    new_num_doses = st.number_input(
                            "Edit Number of Doses",
                            min_value=1,
                            max_value=5,
                            value=st.session_state.edit_num_doses,
                            key="edit_num_doses_input"
                    )

                    # Update session state when number changes
                    if new_num_doses != st.session_state.edit_num_doses:
                        st.session_state.edit_num_doses = new_num_doses

                with st.form("edit_form"):
                    new_name = st.text_input("Edit Medicine Name", med_to_edit["name"])
                    new_freq = st.session_state[edit_freq_key]
                    if new_freq in ["Daily", "Weekly"]:
                        new_times = []
                        
                        for j in range(st.session_state.edit_num_doses):
                            if j < len(med_to_edit.get("times", [])):
                                default_time = datetime.strptime(med_to_edit["times"][j], "%H:%M").time()
                            else:
                                default_time = datetime.now().time()
                            new_time = st.time_input(f"Edit Time {j+1}", default_time, key=f"edit_time_{j}")
                            new_times.append(new_time.strftime("%H:%M"))

                    # Day selection for Weekly frequency
                    new_day = None
                    if new_freq == "Weekly":
                        default_day_index = 0
                        if "day" in med_to_edit and med_to_edit["day"] in calendar.day_name:
                            default_day_index = list(calendar.day_name).index(med_to_edit["day"])
                        new_day = st.selectbox("Edit Day of Week", list(calendar.day_name), index=default_day_index)
                    
                    # Date/time selection for Once frequency
                    once_date = None
                    once_time = None
                    if new_freq == "Once":
                        default_datetime = datetime.strptime(med_to_edit.get("datetime", "2025-01-01 12:00"), "%Y-%m-%d %H:%M")
                        once_date = st.date_input("Edit Date", default_datetime.date())
                        once_time = st.time_input("Edit Time", default_datetime.time())

                    col1, col2 = st.columns(2)
                    with col1:
                        update = st.form_submit_button("💾 Update")
                    with col2:
                        cancel = st.form_submit_button("❌ Cancel Edit")

                # Handle form submit outside the form context
                if update:
                    # Prepare datetime string for Once frequency
                    datetime_str = None
                    if new_freq == "Once":
                        datetime_str = f"{once_date.strftime('%Y-%m-%d')} {once_time.strftime('%H:%M')}"

                    # Check for duplication (excluding current medicine being edited)
                    temp_medications = schedule_data["patients"][edit_patient]["medications"].copy()
                    temp_medications.pop(edit_index)  # Remove current medicine for duplication check
                    # Prepare datetime string for Once frequency
                    datetime_str = None
                    if new_freq == "Once":
                        datetime_str = f"{once_date.strftime('%Y-%m-%d')} {once_time.strftime('%H:%M')}"
                        new_times = []  # <- ADD THIS LINE to avoid NameError

                    if check_medicine_exists(temp_medications, new_name, new_freq, new_times, new_day, datetime_str):
                        st.warning("⚠️ This medicine schedule already exists for this patient.")
                    else:
                        if new_freq == "Daily":
                            updated_med = {
                                "name": new_name,
                                "normalized_name": normalize_medicine_name(new_name),
                                "frequency": new_freq,
                                "times": new_times
                            }
                        elif new_freq == "Weekly":
                            updated_med = {
                                "name": new_name,
                                "normalized_name": normalize_medicine_name(new_name),
                                "frequency": new_freq,
                                "times": new_times,
                                "day": new_day
                            }
                        elif new_freq == "Once":
                            updated_med = {
                                "name": new_name,
                                "normalized_name": normalize_medicine_name(new_name),
                                "frequency": new_freq,
                                "datetime": datetime_str
                            }

                        schedule_data["patients"][edit_patient]["medications"][edit_index] = updated_med

                        with open(DATA_FILE, "w") as f:
                            json.dump(schedule_data, f, indent=4)
                        
                        display_name = schedule_data["patients"][edit_patient].get("display_name", edit_patient.title())
                        if new_freq == "Weekly":
                            st.success(f"✅ Updated {new_name} for {display_name} - every {new_day} at {', '.join(new_times)}")
                        elif new_freq == "Once":
                            st.success(f"✅ Updated {new_name} for {display_name} - on {once_date} at {once_time}")
                        else:
                            st.success(f"✅ Updated {new_name} for {display_name}")
                        
                        # Clean up session state
                        del st.session_state.edit_index
                        del st.session_state.edit_patient
                        if "edit_num_doses" in st.session_state:
                            del st.session_state.edit_num_doses
                        st.rerun()

                elif cancel:
                    # Clean up session state
                    del st.session_state.edit_index
                    del st.session_state.edit_patient
                    if "edit_num_doses" in st.session_state:
                        del st.session_state.edit_num_doses
                    st.info("✖️ Edit canceled.")
                    st.rerun()
        else:
            st.info(f"No medications found for {selected_display_name}.")
else:
    st.info("No patients or medications scheduled yet.")

# --- Display All Scheduled Medications ---
st.subheader("📋 All Medication Schedules")
if "patients" in schedule_data and schedule_data["patients"]:
    for patient_key, patient_data in schedule_data["patients"].items():
        display_name = patient_data.get("display_name", patient_key.title())
        st.markdown(f"### 👤 {display_name}")
        st.caption(f"📱 {patient_data.get('phone', 'No phone number')}")
        
        medications = patient_data["medications"]
        if medications:
            for i, med in enumerate(medications):
                if med["frequency"] == "Weekly":
                    st.write(f"{i+1}. **{med['name']}** at {', '.join(med['times'])} every {med.get('day', 'N/A')}")
                elif med["frequency"] == "Once":
                    st.write(f"{i+1}. **{med['name']}** at {med.get('datetime', 'N/A')}")
                else:
                    st.write(f"{i+1}. **{med['name']}** at {', '.join(med['times'])}")
        else:
            st.info(f"No medications for {display_name}.")
else:
    st.info("No medications scheduled yet.")