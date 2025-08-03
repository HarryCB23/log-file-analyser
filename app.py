import streamlit as st
import pandas as pd
import re
from datetime import datetime
from user_agents import parse # pip install user-agents
import matplotlib.pyplot as plt
import matplotlib.cm as cm # For color maps

# --- Configuration ---
LOG_PATTERN = re.compile(
    r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) - - '
    r'\[(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2} \+\d{4})\] '
    r'"(GET|POST|PUT|DELETE|HEAD)\s(.+?)\sHTTP/\d\.\d" '
    r'(\d{3}) '
    r'(\d+|-) '
    r'"(.*?)" '
    r'"(.*?)"'
)

DATE_FORMAT = "%d/%b/%Y:%H:%M:%S %z"

@st.cache_data
def parse_log_file(uploaded_file):
    data = []
    lines = uploaded_file.readlines()

    progress_bar = st.progress(0, text="Parsing log file...")
    total_lines = len(lines)

    for i, line in enumerate(lines):
        try:
            line = line.decode('utf-8').strip()
            match = LOG_PATTERN.match(line)
            if match:
                ip_address, timestamp_str, method, path, status_code, bytes_str, referrer, user_agent_str = match.groups()
                timestamp = datetime.strptime(timestamp_str, DATE_FORMAT)
                status_code = int(status_code)
                bytes_sent = int(bytes_str) if bytes_str != '-' else 0
                ua = parse(user_agent_str)
                is_bot = ua.is_bot
                bot_name = ua.browser.family if is_bot else "Human"
                data.append({
                    'timestamp': timestamp,
                    'ip_address': ip_address,
                    'method': method,
                    'path': path,
                    'status_code': status_code,
                    'bytes_sent': bytes_sent,
                    'referrer': referrer,
                    'user_agent': user_agent_str,
                    'is_bot': is_bot,
                    'bot_name': bot_name
                })
        except Exception as e:
            pass

        progress_bar.progress((i + 1) / total_lines, text=f"Parsing log file... {i+1}/{total_lines} lines processed.")
    
    progress_bar.empty()

    if not data:
        st.error("No valid log entries found. Please ensure the log file is in a combined log format.")
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour
    return df

def main():
    st.set_page_config(layout="wide", page_title="SEO Log Analyser")

    st.title("SEO Log Analyser")

    st.markdown("""
        Upload your web server access logs (Apache/Nginx combined log format) to get insights into how search engine bots and users interact with your website.
        **Expected Log Format (example):**
        `123.45.67.89 - - [01/Aug/2025:10:00:01 +0000] "GET /index.html HTTP/1.1" 200 1024 "http://www.example.com/previous-page" "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"`
    """)

    uploaded_file = st.file_uploader("Choose a log file (.log, .txt, .gz)", type=["log", "txt", "gz"])

    df = pd.DataFrame()

    if uploaded_file is not None:
        if uploaded_file.name.endswith('.gz'):
            import gzip
            with gzip.open(uploaded_file, 'rb') as f:
                decompressed_file = uploaded_file
                df = parse_log_file(decompressed_file)
        else:
            df = parse_log_file(uploaded_file)

        if not df.empty:
            st.success(f"Successfully loaded {len(df)} log entries.")

            # --- Sidebar Filters ---
            st.sidebar.header("Filters")
            min_date = df['date'].min()
            max_date = df['date'].max()
            selected_start_date = st.sidebar.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date)
            selected_end_date = st.sidebar.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)
            bot_options = ["All Traffic"] + sorted(df['bot_name'].unique().tolist())
            selected_bot_filter = st.sidebar.selectbox("Bot Filter", bot_options)
            status_code_options = ["All Status Codes"] + sorted(df['status_code'].unique().tolist())
            selected_status_code = st.sidebar.selectbox("Status Code", status_code_options)
            apply_filters = st.sidebar.button("Apply Filters")

            filtered_df = df.copy()
            if apply_filters:
                filtered_df = filtered_df[(filtered_df['date'] >= selected_start_date) & (filtered_df['date'] <= selected_end_date)]
                if selected_bot_filter != "All Traffic":
                    filtered_df = filtered_df[filtered_df['bot_name'] == selected_bot_filter]
                if selected_status_code != "All Status Codes":
                    filtered_df = filtered_df[filtered_df['status_code'] == selected_status_code]

            if not filtered_df.empty:
                tabs = st.tabs([
                    "Overall Statistics", 
                    "Status Code Distribution", 
                    "Most Requested Paths", 
                    "Traffic Over Time"
                ])

                # --- Tab 1: Overall Statistics ---
                with tabs[0]:
                    st.header("Overall Statistics")
                    col1, col2, col3, col4 = st.columns(4)
                    total_requests = len(filtered_df)
                    bot_requests = filtered_df[filtered_df['is_bot']].shape[0]
                    unique_ips = filtered_df['ip_address'].nunique()
                    avg_response_time = "N/A (Not in CLF)" 

                    with col1:
                        st.metric("TOTAL REQUESTS", total_requests)
                    with col2:
                        st.metric("BOT REQUESTS", bot_requests)
                    with col3:
                        st.metric("UNIQUE IPS", unique_ips)
                    with col4:
                        st.metric("AVG RESPONSE TIME", avg_response_time)

                    st.markdown("---")

                    st.subheader("Bot Distribution")
                    bot_distribution = filtered_df['bot_name'].value_counts()
                    fig1, ax1 = plt.subplots(figsize=(8, 8))
                    colors = cm.get_cmap('tab20c', len(bot_distribution))
                    ax1.pie(bot_distribution, labels=bot_distribution.index, autopct='%1.1f%%', startangle=90, colors=colors.colors)
                    ax1.axis('equal')
                    st.pyplot(fig1)

                    st.markdown("---")
                    st.subheader("Export Data")
                    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
                    json_data = filtered_df.to_json(orient='records').encode('utf-8')
                    col_exp1, col_exp2 = st.columns(2)
                    with col_exp1:
                        st.download_button(
                            label="Export CSV",
                            data=csv_data,
                            file_name="seo_log_analysis.csv",
                            mime="text/csv",
                        )
                    with col_exp2:
                        st.download_button(
                            label="Export JSON",
                            data=json_data,
                            file_name="seo_log_analysis.json",
                            mime="application/json",
                        )

                # --- Tab 2: Status Code Distribution ---
                with tabs[1]:
                    st.header("Status Code Distribution")
                    status_code_distribution = filtered_df['status_code'].value_counts().sort_index()
                    fig2, ax2 = plt.subplots(figsize=(10, 6))
                    ax2.bar(status_code_distribution.index.astype(str), status_code_distribution.values, color='skyblue')
                    ax2.set_xlabel("Status Code")
                    ax2.set_ylabel("Number of Requests")
                    ax2.set_title("Status Code Distribution")
                    st.pyplot(fig2)

                # --- Tab 3: Most Requested Paths ---
                with tabs[2]:
                    st.header("Most Requested Paths")
                    top_paths = filtered_df['path'].value_counts().head(10)
                    fig3, ax3 = plt.subplots(figsize=(10, 6))
                    ax3.barh(top_paths.index, top_paths.values, color='lightgreen')
                    ax3.set_xlabel("Number of Requests")
                    ax3.set_ylabel("Path")
                    ax3.set_title("Top 10 Most Requested Paths")
                    ax3.invert_yaxis()
                    st.pyplot(fig3)

                # --- Tab 4: Traffic Over Time ---
                with tabs[3]:
                    st.header("Traffic Over Time")
                    traffic_over_time = filtered_df.groupby(filtered_df['timestamp'].dt.to_period('D')).size().sort_index()
                    traffic_over_time.index = traffic_over_time.index.astype(str)
                    fig4, ax4 = plt.subplots(figsize=(12, 6))
                    ax4.plot(traffic_over_time.index, traffic_over_time.values, marker='o', linestyle='-', color='purple')
                    ax4.set_xlabel("Date")
                    ax4.set_ylabel("Number of Requests")
                    ax4.set_title("Traffic Over Time (Daily)")
                    ax4.tick_params(axis='x', rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig4)

            else:
                st.warning("No data matches the selected filters.")

        else:
            st.info("Upload a log file to get started!")

if __name__ == "__main__":
    main()
