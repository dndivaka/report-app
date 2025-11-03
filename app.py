import streamlit as st
import pandas as pd
import json
import io

def process_json_data(uploaded_file):
    """
    Reads the specific JSON file structure from an uploaded file,
    processes it, and returns the final DataFrame.
    """
    try:
        # Load and parse the JSON data from the uploaded file
        data = json.load(uploaded_file)

        # === 1. Extract Teacher List ===
        teachers_data = data.get('metadata', {}).get('teachers', [])
        if not teachers_data:
            st.error("Error: No 'metadata.teachers' list found in the file.")
            return None

        df_teachers = pd.DataFrame(teachers_data)
        
        # Clean up subjects: handle 'None' or lists
        def format_subjects(subjects):
            if subjects is None:
                return ""
            if isinstance(subjects, list):
                return ", ".join(subjects)
            return str(subjects)

        if 'subjects' in df_teachers.columns:
            df_teachers['subjects'] = df_teachers['subjects'].apply(format_subjects)
        else:
            df_teachers['subjects'] = "" # Add empty column if 'subjects' is missing
            
        df_teachers = df_teachers[['id', 'name', 'subjects']]
        df_teachers.rename(columns={'name': 'Teacher name', 'subjects': 'subject'}, inplace=True)

        # === 2. Extract and Aggregate Usage Data ===
        usage_data = data.get('usage', [])
        total_days = len(usage_data) # Count total days in the report
        
        all_teacher_usage = []
        for day_data in usage_data:
            daily_teachers = day_data.get('data', {}).get('teachers', [])
            for teacher_usage in daily_teachers:
                all_teacher_usage.append(teacher_usage)
        
        if not all_teacher_usage:
            st.warning("Warning: 'usage' section is empty. All usage stats will be 0.")
            df_usage_agg = pd.DataFrame(columns=[
                'id', 'Total number of logins', 'Total usage in minutes', 'Number of days used in a month'
            ])
        else:
            df_usage_flat = pd.DataFrame(all_teacher_usage)
            df_usage_flat['day_used'] = (df_usage_flat['usageMins'] > 0).astype(int)
            df_usage_agg = df_usage_flat.groupby('id').agg(
                total_logins=pd.NamedAgg(column='noOfLogins', aggfunc='sum'),
                total_usage_mins=pd.NamedAgg(column='usageMins', aggfunc='sum'),
                days_used=pd.NamedAgg(column='day_used', aggfunc='sum')
            ).reset_index()
            df_usage_agg.rename(columns={
                'total_logins': 'Total number of logins',
                'total_usage_mins': 'Total usage in minutes',
                'days_used': 'Number of days used in a month'
            }, inplace=True)

        # === 3. Merge Teacher List and Usage Data ===
        df_final = pd.merge(df_teachers, df_usage_agg, on='id', how='left')

        # === 4. Final Cleanup and Formatting ===
        usage_columns = ['Total number of logins', 'Total usage in minutes', 'Number of days used in a month']
        df_final[usage_columns] = df_final[usage_columns].fillna(0)
        df_final['Total number of days in the month'] = total_days
        df_final['Total number of logins'] = df_final['Total number of logins'].astype(int)
        df_final['Number of days used in a month'] = df_final['Number of days used in a month'].astype(int)
        df_final['Total usage in minutes'] = df_final['Total usage in minutes'].round(2)

        final_columns = [
            'Teacher name', 'subject', 'Number of days used in a month',
            'Total number of days in the month', 'Total number of logins', 'Total usage in minutes'
        ]
        df_final = df_final[final_columns]
        
        return df_final

    except json.JSONDecodeError:
        st.error("Error: Could not decode JSON. The file might be corrupted or in the wrong format.")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None

# --- This is the main part of the web app ---

st.set_page_config(page_title="Teacher Usage Report", layout="centered")
st.title("Teacher Usage Report Generator")
st.write("Upload your `Global.json.txt` file to generate the downloadable CSV summary.")

uploaded_file = st.file_uploader("Choose your JSON file", type=["json", "txt"])

if uploaded_file is not None:
    st.write("File uploaded. Processing...")
    
    # Process the file
    df_report = process_json_data(uploaded_file)
    
    if df_report is not None:
        st.success("Report generated successfully!")
        
        # Convert DataFrame to CSV in memory
        @st.cache_data
        def convert_df_to_csv(df):
            return df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8')

        csv_data = convert_df_to_csv(df_report)
        
        # Show the download button
        st.download_button(
            label="Download teacher usage summary.csv",
            data=csv_data,
            file_name="teacher usage summary.csv",
            mime="text/csv",
        )