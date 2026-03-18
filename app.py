import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re

# --- 1. 페이지 및 테마 설정 ---
st.set_page_config(page_title="김청축 FC Analytics Dashboard", page_icon="⚽", layout="wide")

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    
    .stApp { background-color: #0E1117 !important; color: #FAFAFA !important; font-family: 'Pretendard', sans-serif !important; }
    
    [data-testid="stMetric"] { background-color: #1E1E2E !important; border: 1px solid #333344 !important; border-radius: 12px !important; padding: 15px !important; box-shadow: 0 4px 10px rgba(0,0,0,0.8) !important; text-align: center !important; }
    [data-testid="stMetricLabel"] { font-size: 1.0rem !important; color: #A0A0B0 !important; }
    [data-testid="stMetricValue"] { font-size: 2.0rem !important; color: #00E676 !important; }

    .stTabs [data-baseweb="tab-list"] { background-color: #0E1117; }
    .stTabs [data-baseweb="tab"] { color: #A0A0B0; font-weight: bold; }
    .stTabs [aria-selected="true"] { color: #00D2FF !important; border-bottom-color: #00D2FF !important; }
    
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0E1117; }
    ::-webkit-scrollbar-thumb { background: #333344; border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: #555566; }
    .empty-cell { color: #555; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 엑셀 파일 자동 스캔 ---
available_files = [f for f in os.listdir() if '김청축' in f and '출석부' in f and f.endswith('.xlsx')]
year_to_file = {}

for f in available_files:
    m = re.search(r'(\d{4})', f)
    year = m.group(1) if m else "기타"
    year_to_file[year] = f

if not year_to_file:
    year_to_file = {"2025": "김청축_2025_출석부.xlsx"}

years = sorted(list(year_to_file.keys()), reverse=True)

col_title, col_selectbox = st.columns([4, 1])

with col_selectbox:
    st.write("") 
    selected_year = st.selectbox("📅 시즌 (Year) 선택", years)

with col_title:
    st.title(f"⚽ 김청축 FC Data Analytics ({selected_year})")
    st.markdown(f"<span style='color:#A0A0B0;'>{selected_year} Season Performance Dashboard</span>", unsafe_allow_html=True)

selected_file = year_to_file[selected_year]

# --- 3. 데이터 로딩 및 전처리 함수 ---
@st.cache_data
def load_data(file_path):
    if not os.path.exists(file_path): return None, None, None, None
    
    try:
        df_personal = pd.read_excel(file_path, sheet_name="개인기록Sheet", skiprows=2).dropna(subset=['이름']).copy()
        df_total_raw = pd.read_excel(file_path, sheet_name="종합Sheet", skiprows=2).dropna(subset=['이름']).copy()
        df_total_subset = df_total_raw[['이름', '입단년도', '종합 Point', '출전 Point']].copy()
        df_merged = pd.merge(df_personal, df_total_subset, on='이름', how='left')
        
        attendance_dict = {}
        date_cols = [c for c in df_total_raw.columns if re.match(r'^202\d-\d{2}-\d{2}', str(c))]
        
        for index, row in df_total_raw.iterrows():
            p_name = str(row['이름']).strip()
            attended_dates = set()
            for dc in date_cols:
                if str(row[dc]).strip() == '출전':
                    attended_dates.add(str(dc)[:10])
            attendance_dict[p_name] = attended_dates

        df_match_raw = pd.read_excel(file_path, sheet_name="경기기록Sheet", header=None)
        match_data = []
        current_match = None
        
        def safe_iloc(row_data, idx, default=""):
            if idx < len(row_data):
                val = row_data.iloc[idx]
                return str(val).strip() if pd.notna(val) else default
            return default

        def parse_score(val):
            if not val or val == 'nan': return "-"
            try: return str(int(float(val)))
            except: return val

        for index, row in df_match_raw.iterrows():
            col_1 = safe_iloc(row, 1) 
            
            if col_1.startswith('202') or safe_iloc(row, 4) == 'Goal': 
                date_str = col_1[:10] if col_1.startswith('202') else "날짜 미상"
                current_match = {
                    'Date': date_str,
                    'Home': safe_iloc(row, 2, 'Home'),
                    'Away': safe_iloc(row, 3, 'Away'),
                    'Quarters': []
                }
                match_data.append(current_match)
                
            elif col_1 in ['1Q', '2Q', '3Q', '4Q', '5Q', '6Q', 'Total'] and current_match is not None:
                def get_players(start_idx, end_idx):
                    players = []
                    for i in range(start_idx, end_idx):
                        p = safe_iloc(row, i)
                        if p and p not in ['nan', '-']:
                            players.append(p)
                    return players
                
                score_h = parse_score(safe_iloc(row, 2))
                score_a = parse_score(safe_iloc(row, 3))
                
                quarter_info = {
                    'Quarter': col_1,
                    'Score': f"{score_h} : {score_a}" if score_h != "-" else "-",
                    'Goals': get_players(4, 9),
                    'Assists': get_players(9, 14),
                    'Balances': get_players(14, 19),
                    'Clean_Sheets': get_players(19, 26)
                }
                
                if quarter_info['Goals'] or quarter_info['Assists'] or quarter_info['Balances'] or quarter_info['Clean_Sheets'] or col_1 == 'Total' or score_h != "-":
                    current_match['Quarters'].append(quarter_info)

        return df_personal, df_merged, match_data, attendance_dict
    
    except Exception as e:
        st.error(f"데이터를 읽는 중 오류가 발생했습니다: {e}")
        return None, None, None, None

df_personal, df_merged, match_data, attendance_dict = load_data(selected_file)

# --- 4. 차트 생성 헬퍼 함수 ---
def create_top10_chart(df, column, title, color):
    df_temp = df.copy()
    df_temp[column] = pd.to_numeric(df_temp[column], errors='coerce').fillna(0)
    
    df_top10 = df_temp.nlargest(10, column).reset_index(drop=True)
    df_top10['Rank'] = df_top10.index + 1
    df_top10['표시이름'] = df_top10['Rank'].astype(str) + ". " + df_top10['이름']
    
    df_top10 = df_top10.sort_values(by='Rank', ascending=False)
    
    fig = px.bar(df_top10, x=column, y="표시이름", orientation='h', text=column)
    fig.update_traces(marker_color=color, textposition='outside', textfont=dict(color='white', size=13))
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color='white')),
        template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=20, t=50, b=0), xaxis=dict(showgrid=False, visible=False),
        yaxis=dict(title="", showgrid=False, tickfont=dict(size=14)), height=400
    )
    return fig

# --- 5. 검색어 하이라이트 헬퍼 함수 ---
def format_stat_with_highlight(players_list, search_keyword):
    if not players_list:
        return "<span class='empty-cell'>-</span>"
    if not search_keyword:
        return ", ".join(players_list)
    
    highlighted_list = []
    for p in players_list:
        if search_keyword in p:
            highlighted_list.append(f"<span style='background-color:#FFEA00; color:#000; font-weight:bold; padding:2px 5px; border-radius:4px;'>{p}</span>")
        else:
            highlighted_list.append(p)
    return ", ".join(highlighted_list)

# --- 6. 메인 화면 구성 ---
if df_merged is None:
    st.error(f"⚠️ '{selected_file}' 파일을 찾을 수 없거나 형식이 잘못되었습니다.")
else:
    tab_main, tab_match = st.tabs(["📊 Main (개인기록 종합)", "🏟️ Match (상세 경기기록)"])
    
    with tab_main:
        st.write("")
        if len(df_merged) > 0:
            top_overall = df_merged.sort_values(by="종합 Point", ascending=False).iloc[0]
            
            r1_col1, r1_col2 = st.columns(2)
            r1_col1.metric("👥 Total Players", f"{len(df_merged)} 명")
            r1_col2.metric("🏆 Overall 1st", f"{top_overall['이름']}", f"{round(top_overall['종합 Point'], 2)} P")

            st.write("")
            for col in ['Goal (0.2)', 'Assist (0.2)', 'Balance (0.3)', 'C/S DF (0.2)', 'C/S GK (0.2)']:
                df_merged[col] = pd.to_numeric(df_merged[col], errors='coerce').fillna(0)
                
            t_goal = df_merged.sort_values(by="Goal (0.2)", ascending=False).iloc[0]
            t_assist = df_merged.sort_values(by="Assist (0.2)", ascending=False).iloc[0]
            t_bal = df_merged.sort_values(by="Balance (0.3)", ascending=False).iloc[0]
            t_csdf = df_merged.sort_values(by="C/S DF (0.2)", ascending=False).iloc[0]
            t_csgk = df_merged.sort_values(by="C/S GK (0.2)", ascending=False).iloc[0]

            r2_col1, r2_col2, r2_col3, r2_col4, r2_col5 = st.columns(5)
            r2_col1.metric("⚽ Goal 1st", f"{t_goal['이름']}", f"{int(t_goal['Goal (0.2)'])} 골")
            r2_col2.metric("🎯 Assist 1st", f"{t_assist['이름']}", f"{int(t_assist['Assist (0.2)'])} 도움")
            r2_col3.metric("⚖️ Balance 1st", f"{t_bal['이름']}", f"{int(t_bal['Balance (0.3)'])} 개")
            r2_col4.metric("🛡️ C/S (DF) 1st", f"{t_csdf['이름']}", f"{int(t_csdf['C/S DF (0.2)'])} 회")
            r2_col5.metric("🧤 C/S (GK) 1st", f"{t_csgk['이름']}", f"{int(t_csgk['C/S GK (0.2)'])} 회")

            st.divider()

            st.subheader("🔥 Top 10 Leaderboards")
            cat_tabs = st.tabs(["종합 Point", "출전 Point", "Goal", "Assist", "Balance", "C/S DF", "C/S GK"])
            categories = [
                ("종합 Point", "#FFD700", "🏆 종합 Point"), ("출전 Point", "#4DB6AC", "🏃 출전 Point"),
                ("Goal (0.2)", "#FF4B4B", "⚽ Goal"), ("Assist (0.2)", "#00D2FF", "🎯 Assist"),
                ("Balance (0.3)", "#B388FF", "⚖️ Balance"), ("C/S DF (0.2)", "#00E676", "🛡️ C/S (DF)"),
                ("C/S GK (0.2)", "#FFA726", "🧤 C/S (GK)")
            ]
            
            for i, (col_name, color, title) in enumerate(categories):
                with cat_tabs[i]:
                    st.plotly_chart(create_top10_chart(df_merged, col_name, f"{title} Top 10", color), use_container_width=True)

            st.divider()

            st.subheader("📋 개인 전체 기록 (Total Database)")
            
            st.info("💡 **종합 Point 계산식:** 출전 Point + (Goal × 0.2) + (Assist × 0.2) + (Balance × 0.3) + (C/S DF × 0.2) + (C/S GK × 0.2)")
            
            search_main = st.text_input("🔍 내 기록 찾기 (이름 검색)", placeholder="선수 이름을 입력하세요...", key="search_main")

            display_cols = ['이름', '입단년도', '종합 Point', '출전 Point', 'Goal (0.2)', 'Assist (0.2)', 'Balance (0.3)', 'C/S DF (0.2)', 'C/S GK (0.2)']
            df_display = df_merged[display_cols].sort_values(by="종합 Point", ascending=False).reset_index(drop=True)
            df_display.columns = ['선수', '입단', '종합P', '출전P', '⚽골', '🎯도움', '⚖️밸런스', '🛡️DF', '🧤GK']
            
            if search_main:
                df_display = df_display[df_display['선수'].str.contains(search_main, na=False)]
            
            for col in ['종합P', '출전P']:
                df_display[col] = pd.to_numeric(df_display[col], errors='coerce').round(2)
                
            st.dataframe(
                df_display.style.background_gradient(cmap='Blues_r', subset=['종합P']).format({'종합P': '{:.2f}', '출전P': '{:.2f}'}), 
                use_container_width=True, 
                hide_index=True, 
                height=500
            )

    with tab_match:
        st.subheader("🏟️ 매치 리포트 (Match Records)")
        
        search_player = st.text_input("🔍 특정 선수 기록 모아보기 (이름 입력)", placeholder="선수 이름을 입력하면 출전한 경기가 필터링되고, 이름이 형광펜으로 칠해집니다.", key="search_match")
        st.write("")
        
        if not match_data:
            st.info("경기 기록 데이터가 비어있거나 올바르지 않습니다.")
        else:
            filtered_matches = []
            for match in reversed(match_data):
                show_match = False
                
                if not search_player:
                    show_match = True
                else:
                    matching_players = [p for p in attendance_dict.keys() if search_player in p]
                    for p in matching_players:
                        if match['Date'] in attendance_dict[p]:
                            show_match = True
                            break
                    
                    if not show_match:
                        for q in match['Quarters']:
                            all_involved = q['Goals'] + q['Assists'] + q['Balances'] + q['Clean_Sheets']
                            if any(search_player in p for p in all_involved):
                                show_match = True
                                break
                                
                if show_match:
                    filtered_matches.append(match)

            cols = st.columns(2)
            
            for i, match in enumerate(filtered_matches):
                with cols[i % 2]:
                    with st.container(border=True):
                        st.markdown(f"#### 📅 {match['Date']}")
                        st.markdown(f"**{match['Home']}** ⚔️ **{match['Away']}**")
                        
                        for q in match['Quarters']:
                            is_total = (q['Quarter'] == 'Total')
                            bg_color = "#2A2D3E" if is_total else "#1E1E2E"
                            text_color = "#FFD700" if is_total else "#00D2FF"
                            
                            goals = format_stat_with_highlight(q['Goals'], search_player)
                            asts = format_stat_with_highlight(q['Assists'], search_player)
                            bals = format_stat_with_highlight(q['Balances'], search_player)
                            cs = format_stat_with_highlight(q['Clean_Sheets'], search_player)
                            
                            # 🔥 [정렬 완벽 해결] CSS Grid를 활용한 칼각 정렬 로직 적용
                            html_q = f"""
                            <div style="background-color: {bg_color}; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid {text_color};">
                                <div style="margin-bottom: 10px;">
                                    <strong style="color: {text_color}; font-size:1.1rem;">{q['Quarter']}</strong> 
                                    <span style="color: #A0A0B0; font-size:1.0rem; margin-left:10px;">Score: {q['Score']}</span>
                                </div>
                                <div style="display: grid; grid-template-columns: repeat(2, 1fr); row-gap: 8px; column-gap: 12px; font-size: 0.95rem; line-height: 1.4;">
                                    <div style="display: flex;"><span style="width:24px; flex-shrink:0;">⚽</span> <span style="flex-grow:1;">{goals}</span></div>
                                    <div style="display: flex;"><span style="width:24px; flex-shrink:0;">🎯</span> <span style="flex-grow:1;">{asts}</span></div>
                                    <div style="display: flex;"><span style="width:24px; flex-shrink:0;">⚖️</span> <span style="flex-grow:1;">{bals}</span></div>
                                    <div style="display: flex;"><span style="width:24px; flex-shrink:0;">🛡️</span> <span style="flex-grow:1;">{cs}</span></div>
                                </div>
                            </div>
                            """
                            st.markdown(html_q, unsafe_allow_html=True)