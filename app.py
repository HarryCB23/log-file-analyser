import streamlit as st
import pandas as pd
import re
from datetime import datetime
from user_agents import parse
import plotly.express as px
import plotly.graph_objects as go
import gzip # Import gzip for handling .gz files
import io   # <-- ADDED: Fixes NameError for io.BytesIO

# --- Configuration and Styling ---
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

# Define a modern, consistent color palette
COLOR_PALETTE = [
    '#4CAF50',  # Green (for Google/primary success)
    '#2196F3',  # Blue (for Apple/Bing)
    '#FFC107',  # Amber (for Yandex)
    '#9C27B0',  # Purple (for OpenSEO)
    '#FF5722',  # Deep Orange (for DuckDuckGo)
    '#00BCD4',  # Cyan (for SEMRush)
    '#795548',  # Brown (other bots)
    '#9E9E9E',  # Grey (Human)
    '#607D8B',  # Blue Grey
    '#CDDC39',  # Lime
    '#F44336',  # Red (for errors)
    '#E91E63',  # Pink (for redirects)
    '#3F51B5',  # Indigo
]

# --- Inject Custom CSS for modern look ---
st.markdown(
    """
    <style>
    /* Main container background */
    .stApp {
        background-color: #f0f2f6; /* Light grey background */
    }

    /* Header styling */
    h1 {
        color: #333333;
        font-family: 'Segoe UI', sans-serif;
        font-weight: 600;
        margin-bottom: 20px;
    }
    h2, h3, h4 {
        color: #444444;
        font-family: 'Segoe UI', sans-serif;
        font-weight: 500;
    }

    /* Metric cards styling */
    [data-testid="stMetric"] {
        background-color: #ffffff; /* White background for cards */
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); /* Subtle shadow */
        text-align: center;
        margin-bottom: 20px;
    }
    [data-testid="stMetricLabel"] {
        color: #666666;
        font-size: 0.9em;
        font-weight: 500;
    }
    [data-testid="stMetricValue"] {
        color: #333333;
        font-size: 1.8em;
        font-weight: 600;
    }

    /* Custom file uploader button styling to match screenshot */
    .stFileUploader > div > div > button {
        background-color: #4CAF50 !important; /* Green button */
        color: white !important;
        border-radius: 5px !important;
        border: none !important;
        padding: 10px 20px !important;
        font-weight: bold !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    }
    .stFileUploader > div > div > button:hover {
        background-color: #43A047 !important; /* Darker green on hover */
    }
    /* Text below uploader */
    .stFileUploader > div > label + div { /* Selects the div containing the drag & drop text */
        text-align: center;
        margin-top: 10px;
        color: #777777;
        font-style: italic;
    }

    /* Export buttons styling */
    .stDownloadButton > button {
        background-color: #4CAF50 !important; /* Green button */
        color: white !important;
        border-radius: 5px !important;
        border: none !important;
        padding: 8px 15px !important;
        font-weight: bold !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    }
    .stDownloadButton > button:hover {
        background-color: #43A047 !important;
    }

    /* Apply Filters button styling */
    button[data-testid="baseButton-secondary"] { /* Targets secondary buttons by default */
        background-color: #4CAF50 !important;
        color: white !important;
        border-radius: 5px !important;
        border: none !important;
        padding: 8px 15px !important;
        font-weight: bold !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    }
    button[data-testid="baseButton-secondary"]:hover {
        background-color: #43A047 !important;
    }

    /* Overall container for charts and content */
    .stTabs [data-testid="stVerticalBlock"] {
        background-color: #ffffff; /* White background for the main content area */
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        margin-top: 20px;
    }

    /* Adjust padding for columns within the main area to prevent squishing */
    .stColumn {
        padding: 10px !important;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #e0e0e0; /* Slightly darker grey for sidebar */
    }

    </style>
    """,
    unsafe_allow_html=True
)


# --- Parsing Function ---
@st.cache_data
def parse_log_file(uploaded_file):
    """
    Parses a web server log file (combined log format) into a pandas DataFrame.
    Handles gzipped files automatically.
    """
    data = []
    
    # Read file content based on type
    if isinstance(uploaded_file, io.BytesIO): # For direct BytesIO from .gz after decompression
        lines = uploaded_file.getvalue().decode('utf-8').splitlines()
    elif uploaded_file.name.endswith('.gz'):
        with gzip.open(uploaded_file, 'rt', encoding='utf-8') as f:
            lines = f.readlines()
    else: # Regular text file
        lines = uploaded_file.readlines()
        lines = [line.decode('utf-8').strip() for line in lines] # Decode lines for non-gzipped too

    progress_bar = st.progress(0, text="Parsing log file...")
    total_lines = len(lines)

    for i, line in enumerate(lines):
        try:
            match = LOG_PATTERN.match(line.strip())
            if match:
                ip_address, timestamp_str, method, path, status_code, bytes_str, referrer, user_agent_str = match.groups()

                timestamp = datetime.strptime(timestamp_str, DATE_FORMAT)
                status_code = int(status_code)
                bytes_sent = int(bytes_str) if bytes_str != '-' else 0
                
                ua = parse(user_agent_str)
                is_bot = ua.is_bot
                
                # Refine bot_name to be more like the screenshot's legend
                if "Googlebot" in user_agent_str:
                    bot_name = "Google"
                elif "Bingbot" in user_agent_str:
                    bot_name = "Bing"
                elif "Applebot" in user_agent_str:
                    bot_name = "Apple"
                elif "YandexBot" in user_agent_str or "YandexMobileBot" in user_agent_str:
                    bot_name = "Yandex"
                elif "DuckDuckBot" in user_agent_str:
                    bot_name = "DuckDuckGo"
                elif "SEMrushBot" in user_agent_str:
                    bot_name = "SEMRush"
                elif "OpenLinkProfiler" in user_agent_str or "SiteExplorer" in user_agent_str:
                    bot_name = "OpenSEO" # Assuming OpenSEO refers to AhrefsBot/Majestic/similar
                elif is_bot:
                    bot_name = ua.browser.family # Default for other identified bots
                else:
                    bot_name = "Human"


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
            # st.warning(f"Skipping malformed line: {line[:100]}... Error: {e}")
            pass # Silently skip malformed lines for robustness

        progress_bar.progress((i + 1) / total_lines, text=f"Parsing log file... {i+1}/{total_lines} lines processed.")
    
    progress_bar.empty()

    if not data:
        st.error("No valid log entries found. Please ensure the log file is in a combined log format.")
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour
    return df

# --- Streamlit App Layout ---
def main():
    st.set_page_config(layout="wide", page_title="SEO Log Analyser", initial_sidebar_state="expanded") # Expanded sidebar

    # Top row for Title and Export Buttons
    col_title, col_export_csv, col_export_json = st.columns([0.8, 0.1, 0.1])

    with col_title:
        st.title("SEO Log Analyser")

    # Initializing filtered_df for export buttons if no file is loaded yet
    filtered_df_for_export = pd.DataFrame() 

    # Placeholder for export buttons, they will be updated after file upload and filtering
    with col_export_csv:
        csv_placeholder = st.empty()
    with col_export_json:
        json_placeholder = st.empty()


    # File Uploader Section
    st.markdown(
        """
        <div style='background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); margin-bottom: 20px;'>
            <p style='text-align: center; font-weight: bold; color: #555;'>Choose Log Files</p>
            <p style='text-align: center; font-size: 0.9em; color: #777;'>Drag and drop log files here or click to select (.log or .gz files)</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    uploaded_file = st.file_uploader("", type=["log", "txt", "gz"], accept_multiple_files=False, label_visibility="collapsed") # Remove default label


    df = pd.DataFrame()

    if uploaded_file is not None:
        import io # Ensure io is imported here
        st.info("Processing log file... This may take a moment.")
        df = parse_log_file(uploaded_file)
        
        if not df.empty:
            st.success(f"Successfully loaded {len(df)} log entries.")
            # Ensure the df for filtering exists, even if no explicit filters are applied yet
            filtered_df_for_export = df.copy()

            # --- Metrics Cards (always visible after upload) ---
            st.markdown("<br>", unsafe_allow_html=True) # Add some space
            col1, col2, col3, col4 = st.columns(4)
            
            total_requests = len(df)
            bot_requests = df[df['is_bot']].shape[0]
            unique_ips = df['ip_address'].nunique()
            avg_response_time = "0ms" # Placeholder, as per screenshot

            with col1:
                st.metric("TOTAL REQUESTS", total_requests, delta_color="off") # delta_color="off" to match flat style
            with col2:
                st.metric("BOT REQUESTS", bot_requests, delta_color="off")
            with col3:
                st.metric("UNIQUE IPS", unique_ips, delta_color="off")
            with col4:
                st.metric("AVG RESPONSE TIME", avg_response_time, delta_color="off")

            # --- Filters Section (Looks like a grey box in screenshot) ---
            st.markdown(
                """
                <div style='background-color: #EFEFEF; padding: 20px 20px 5px 20px; border-radius: 8px; margin-top: 20px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);'>
                    <p style='font-weight: bold; color: #555; margin-bottom: 15px;'>Filters</p>
                """,
                unsafe_allow_html=True
            )
            
            filter_cols = st.columns([1, 1, 1, 1, 0.5]) # Adjust column widths for filters and button

            min_date = df['date'].min()
            max_date = df['date'].max()

            with filter_cols[0]:
                selected_start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date, key="start_date")
            with filter_cols[1]:
                selected_end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date, key="end_date")
            with filter_cols[2]:
                bot_options = ["All Traffic"] + sorted(df['bot_name'].unique().tolist())
                selected_bot_filter = st.selectbox("Bot Filter", bot_options, key="bot_filter")
            with filter_cols[3]:
                status_code_options = ["All Status Codes"] + sorted(df['status_code'].unique().tolist())
                selected_status_code = st.selectbox("Status Code", status_code_options, key="status_filter")
            with filter_cols[4]:
                st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True) # Spacer
                apply_filters = st.button("Apply Filters")
            
            st.markdown("</div>", unsafe_allow_html=True) # Close filter div

            filtered_df = df.copy() # Initialize filtered_df here

            # Apply filters on button click or initial load
            if apply_filters:
                st.session_state.filtered_df = df[
                    (df['date'] >= selected_start_date) & 
                    (df['date'] <= selected_end_date)
                ].copy() # Ensure we're working on a copy
                
                if selected_bot_filter != "All Traffic":
                    st.session_state.filtered_df = st.session_state.filtered_df[st.session_state.filtered_df['bot_name'] == selected_bot_filter]

                if selected_status_code != "All Status Codes":
                    st.session_state.filtered_df = st.session_state.filtered_df[st.session_state.filtered_df['status_code'] == selected_status_code]
            
            # Use session_state to persist filtered_df across reruns, ensuring filters stick
            if 'filtered_df' not in st.session_state or apply_filters:
                # If no filters applied yet or "Apply Filters" was clicked, initialize/update it
                st.session_state.filtered_df = df.copy()

            # Now, set filtered_df to the session state version for display
            filtered_df = st.session_state.filtered_df


            if not filtered_df.empty:
                # Update export buttons with current filtered data
                csv_data = filtered_df.to_csv(index=False).encode('utf-8')
                json_data = filtered_df.to_json(orient='records').encode('utf-8')

                with col_export_csv:
                    csv_placeholder.download_button(
                        label="Export CSV",
                        data=csv_data,
                        file_name="seo_log_analysis.csv",
                        mime="text/csv",
                        key="export_csv_btn" # Unique key for button
                    )
                with col_export_json:
                    json_placeholder.download_button(
                        label="Export JSON",
                        data=json_data,
                        file_name="seo_log_analysis.json",
                        mime="application/json",
                        key="export_json_btn" # Unique key for button
                    )

                st.markdown("<br>", unsafe_allow_html=True) # Spacer

                # --- Charts in a two-column layout matching screenshot ---
                chart_col1, chart_col2 = st.columns(2)

                # --- Bot Distribution (Pie Chart) ---
                with chart_col1:
                    st.subheader("Bot Distribution")
                    bot_distribution = filtered_df['bot_name'].value_counts()
                    
                    # Map colors to bot names for consistency
                    unique_bots = bot_distribution.index.tolist()
                    color_map = {bot: COLOR_PALETTE[i % len(COLOR_PALETTE)] for i, bot in enumerate(unique_bots)}

                    fig_pie = px.pie(
                        names=bot_distribution.index,
                        values=bot_distribution.values,
                        color_discrete_map=color_map,
                        hole=0.3, # For a donut chart look
                        color=bot_distribution.index, # Ensure color mapping uses the bot names
                    )
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='#000000', width=0.5)))
                    fig_pie.update_layout(
                        margin=dict(l=0, r=0, t=0, b=0), # Reduce margins
                        paper_bgcolor='white', # Set plot background to white
                        plot_bgcolor='white', # Set plot background to white
                        legend_title_text='Bots', # Add a legend title
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1) # Place legend on top like screenshot
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

                # --- Status Code Distribution (Bar Chart) ---
                with chart_col2:
                    st.subheader("Status Code Distribution")
                    status_code_distribution = filtered_df['status_code'].value_counts().sort_index()
                    
                    # Custom colors for status codes (e.g., green for 2xx, orange for 3xx, red for 4xx/5xx)
                    bar_colors = [
                        '#4CAF50' if str(code).startswith('2') else # Green for 2xx
                        '#FFC107' if str(code).startswith('3') else # Amber for 3xx
                        '#F44336' if str(code).startswith('4') or str(code).startswith('5') else # Red for 4xx/5xx
                        '#9E9E9E' # Grey for others
                        for code in status_code_distribution.index
                    ]

                    fig_bar_status = px.bar(
                        x=status_code_distribution.index.astype(str),
                        y=status_code_distribution.values,
                        color=status_code_distribution.index.astype(str), # Color based on status code
                        color_discrete_map={str(code): color for code, color in zip(status_code_distribution.index, bar_colors)},
                        labels={'x': 'Status Code', 'y': 'Number of Requests'},
                        title='Status Codes' # Title for legend as per screenshot
                    )
                    fig_bar_status.update_layout(
                        paper_bgcolor='white',
                        plot_bgcolor='white',
                        xaxis_title="", # Remove x-axis title to match screenshot
                        yaxis_title="", # Remove y-axis title to match screenshot
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1) # Place legend on top like screenshot
                    )
                    fig_bar_status.update_xaxes(showgrid=False) # Remove x-axis grid
                    fig_bar_status.update_yaxes(showgrid=True, gridcolor='#e0e0e0') # Light grey y-axis grid
                    st.plotly_chart(fig_bar_status, use_container_width=True)
                
                # --- Bottom Row for Most Requested Paths and Traffic Over Time ---
                st.markdown("<br>", unsafe_allow_html=True) # Add some space between rows
                bottom_chart_col1, bottom_chart_col2 = st.columns(2)

                # --- Most Requested Paths (Horizontal Bar Chart) ---
                with bottom_chart_col1:
                    st.subheader("Most Requested Paths")
                    top_paths = filtered_df['path'].value_counts().head(10).sort_values(ascending=True) # Sort for cleaner bar chart
                    
                    fig_bar_paths = px.bar(
                        x=top_paths.values,
                        y=top_paths.index,
                        orientation='h',
                        labels={'x': 'Number of Requests', 'y': 'Path'},
                        color_discrete_sequence=['#2196F3'], # A single blue color as in screenshot
                        title='Top Paths' # Title for legend as per screenshot
                    )
                    fig_bar_paths.update_layout(
                        paper_bgcolor='white',
                        plot_bgcolor='white',
                        xaxis_title="", # Remove x-axis title
                        yaxis_title="", # Remove y-axis title
                        showlegend=True, # Ensure legend is shown
                        legend_title_text='' # No legend title
                    )
                    fig_bar_paths.update_xaxes(showgrid=False)
                    fig_bar_paths.update_yaxes(showgrid=False) # Remove y-axis grid
                    st.plotly_chart(fig_bar_paths, use_container_width=True)

                # --- Traffic Over Time (Line Chart) ---
                with bottom_chart_col2:
                    st.subheader("Traffic Over Time")
                    traffic_over_time = filtered_df.groupby(filtered_df['timestamp'].dt.to_period('D')).size().sort_index().to_frame(name='count')
                    traffic_over_time.index = traffic_over_time.index.astype(str) # Convert PeriodIndex to string for plotting
                    traffic_over_time.reset_index(inplace=True)
                    traffic_over_time.columns = ['Date', 'Traffic'] # Rename columns for Plotly

                    fig_line = px.line(
                        traffic_over_time,
                        x='Date',
                        y='Traffic',
                        labels={'Traffic': 'Traffic'}, # Label for legend
                        line_shape="spline", # Smoother line
                        color_discrete_sequence=['#4CAF50'] # Green line as per screenshot
                    )
                    fig_line.update_layout(
                        paper_bgcolor='white',
                        plot_bgcolor='white',
                        xaxis_title="", # Remove x-axis title
                        yaxis_title="", # Remove y-axis title
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1) # Place legend on top like screenshot
                    )
                    fig_line.update_xaxes(showgrid=False)
                    fig_line.update_yaxes(showgrid=True, gridcolor='#e0e0e0')
                    st.plotly_chart(fig_line, use_container_width=True)

            else:
                st.warning("No data matches the selected filters.")

        else:
            st.info("Upload a log file to get started!")

    else:
        st.info("Upload a log file to get started!")
        # Ensure export buttons are hidden/disabled if no file is uploaded
        csv_placeholder.download_button(label="Export CSV", data=b"", file_name="empty.csv", mime="text/csv", disabled=True)
        json_placeholder.download_button(label="Export JSON", data=b"", file_name="empty.json", mime="application/json", disabled=True)


if __name__ == "__main__":
    main()
