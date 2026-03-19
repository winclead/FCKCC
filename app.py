import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re
import datetime

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

selected_file = year_to_file[selected_year]

with col_title:
    st.title(f"⚽ 김청축 FC Data Analytics ({selected_year})")
    try:
        timestamp = os.path.getmtime(selected_file)
        dt_utc = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
        dt_kst = dt_utc.astimezone(datetime.timezone(datetime.timedelta(hours=9)))
        update_str = dt_kst.strftime("%Y-%m-%d %H:%M")
        st.markdown(f"<span style='color:#A0A0B0;'>{selected_year} Season Performance Dashboard &nbsp;|&nbsp; 🔄 Last Updated: {update_str}</span>", unsafe_allow_html=True)
    except:
        st.markdown(f"<span style='color:#A0A0B0;'>{selected_year} Season Performance Dashboard</span>", unsafe_allow_html=True)

# --- 3. 데이터 로딩 및 전처리 함수 ---
@st.cache_data
def load_data(file_path):
    if not os.path.exists(file_path): return None, None, None, None
    
    try:
        df_personal = pd.read_excel(file_path, sheet_name="개인기록Sheet", skiprows=2).dropna(subset=['이름']).copy()
        df_total_raw = pd.read_excel(file_path, sheet_name="종합Sheet", skiprows=2).dropna(subset=['이름']).copy()
        
        required_cols = ['이름', '입단년도', '종합 Point', '출전 Point']
        for c in required_cols:
            if c not in df_total_raw.columns:
                df_total_raw[c] = 0
                
        df_total_subset = df_total_raw[required_cols].copy()
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
            
        def ensure_total(match):
            has_total = False
            total_q = None
            sum_h = 0
            sum_a = 0
            
            for q in match['Quarters']:
                if q['Quarter'] == 'Total':
                    has_total = True
                    total_q = q
                else:
                    if str(q['ScoreH']).isdigit(): sum_h += int(q['ScoreH'])
                    if str(q['ScoreA']).isdigit(): sum_a += int(q['ScoreA'])
            
            if not has_total:
                match['Quarters'].append({
                    'Quarter': 'Total', 'ScoreH': str(sum_h), 'ScoreA': str(sum_a), 'Score': f"{sum_h} : {sum_a}",
                    'Goals': [], 'Assists': [], 'Balances': [], 'DF_CS': [], 'GK_CS': []
                })
            else:
                if total_q['ScoreH'] == "-" or total_q['ScoreA'] == "-" or total_q['ScoreH'] == "" or total_q['ScoreA'] == "":
                    total_q['ScoreH'] = str(sum_h)
                    total_q['ScoreA'] = str(sum_a)
                    total_q['Score'] = f"{sum_h} : {sum_a}"

        for index, row in df_match_raw.iterrows():
            col_1 = safe_iloc(row, 1) 
            
            if re.match(r'^20\d\d-\d{2}-\d{2}', col_1): 
                if current_match is not None:
                    ensure_total(current_match)
                    match_data.append(current_match)
                
                current_match = {
                    'Date': col_1[:10],
                    'Home': safe_iloc(row, 2, 'Home'),
                    'Away': safe_iloc(row, 3, 'Away'),
                    'Quarters': []
                }
                
            elif current_match is not None:
                def get_players(start_idx, end_idx):
                    players = []
                    for i in range(start_idx, end_idx):
                        p = safe_iloc(row, i)
                        if p and p not in ['nan', '-']:
                            players.append(p)
                    return players
                
                score_h = parse_score(safe_iloc(row, 2))
                score_a = parse_score(safe_iloc(row, 3))
                
                goals = get_players(4, 9)
                assists = get_players(9, 14)
                balances = get_players(14, 19)
                df_cs = get_players(19, 21)
                gk_cs = get_players(21, 22)
                
                is_empty = (score_h == "-" and score_a == "-" and not goals and not assists and not balances and not df_cs and not gk_cs)
                is_header = (str(safe_iloc(row, 2)) == 'Home')
                
                if not is_empty and not is_header:
                    q_name = col_1 if col_1 else f"{len([q for q in current_match['Quarters'] if q['Quarter'] != 'Total']) + 1}Q"
                    if 'total' in str(q_name).lower():
                        q_name = 'Total'
                        
                    current_match['Quarters'].append({
                        'Quarter': q_name, 'ScoreH': score_h, 'ScoreA': score_a, 
                        'Score': f"{score_h} : {score_a}" if score_h != "-" else "-",
                        'Goals': goals, 'Assists': assists, 'Balances': balances, 'DF_CS': df_cs, 'GK_CS': gk_cs
                    })
                    
                    if q_name == 'Total':
                        ensure_total(current_match)
                        match_data.append(current_match)
                        current_match = None

        if current_match is not None:
            ensure_total(current_match)
            match_data.append(current_match)

        return df_personal, df_merged, match_data, attendance_dict
    
    except Exception as e:
        st.error(f"데이터를 읽는 중 오류가 발생했습니다: {e}")
        return None, None, None, None

df_personal, df_merged, match_data, attendance_dict = load_data(selected_file)

# --- 4. 차트 생성 헬퍼 함수 ---
def create_top10_chart(df, column, title, color):
    df_temp = df.copy()
    if column not in df_temp.columns: df_temp[column] = 0
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
        margin=dict(l=0, r=20, t=50, b=0), 
        xaxis=dict(showgrid=False, visible=False, fixedrange=True),
        yaxis=dict(title="", showgrid=False, tickfont=dict(size=14), fixedrange=True), 
        height=400, dragmode=False
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
    tab_main, tab_match = st.tabs(["📊 Main (개인기록)", "🏟️ Match (경기기록)"])
    
    with tab_main:
        st.write("")
        if len(df_merged) > 0:
            if "종합 Point" not in df_merged.columns: df_merged["종합 Point"] = 0
            top_overall = df_merged.sort_values(by="종합 Point", ascending=False).iloc[0]
            
            r1_col1, r1_col2 = st.columns(2)
            r1_col1.metric("👥 Total Players", f"{len(df_merged)} 명")
            r1_col2.metric("🏆 Overall 1st", f"{top_overall['이름']}", f"{round(top_overall['종합 Point'], 2)} P")

            st.write("")
            for col in ['Goal (0.2)', 'Assist (0.2)', 'Balance (0.3)', 'C/S DF (0.2)', 'C/S GK (0.2)']:
                if col not in df_merged.columns: df_merged[col] = 0
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
            r2_col4.metric("🛡️ DF 1st", f"{t_csdf['이름']}", f"{int(t_csdf['C/S DF (0.2)'])} 회")
            r2_col5.metric("🧤 GK 1st", f"{t_csgk['이름']}", f"{int(t_csgk['C/S GK (0.2)'])} 회")

            st.divider()

            st.subheader("🔥 Top 10 Leaderboards")
            cat_tabs = st.tabs(["종합", "출전", "Goal", "Assist", "Balance", "DF", "GK"])
            categories = [
                ("종합 Point", "#FFD700", "🏆 종합"), ("출전 Point", "#4DB6AC", "🏃 출전"),
                ("Goal (0.2)", "#FF4B4B", "⚽ Goal"), ("Assist (0.2)", "#00D2FF", "🎯 Assist"),
                ("Balance (0.3)", "#B388FF", "⚖️ Balance"), ("C/S DF (0.2)", "#00E676", "🛡️ DF"),
                ("C/S GK (0.2)", "#FFA726", "🧤 GK")
            ]
            
            for i, (col_name, color, title) in enumerate(categories):
                with cat_tabs[i]:
                    st.plotly_chart(create_top10_chart(df_merged, col_name, f"{title} Top 10", color), width='stretch', config={'displayModeBar': False})

            st.divider()

            st.subheader("📋 개인 전체 기록 (Total Database)")
            st.info("💡 **종합 점수 계산식:** 출전 + (Goal × 0.2) + (Assist × 0.2) + (Balance × 0.3) + (DF × 0.2) + (GK × 0.2)")
            search_main = st.text_input("🔍 내 기록 찾기 (이름 검색)", placeholder="선수 이름을 입력하세요...", key="search_main")

            display_cols = ['이름', '입단년도', '종합 Point', '출전 Point', 'Goal (0.2)', 'Assist (0.2)', 'Balance (0.3)', 'C/S DF (0.2)', 'C/S GK (0.2)']
            
            for c in display_cols:
                if c not in df_merged.columns: df_merged[c] = 0
                
            df_display = df_merged[display_cols].sort_values(by="종합 Point", ascending=False).reset_index(drop=True)
            df_display.columns = ['선수', '입단', '종합', '출전', '⚽골', '🎯도움', '⚖️밸런스', '🛡️DF', '🧤GK']
            df_display.insert(0, '순위', range(1, len(df_display) + 1))
            
            if search_main:
                df_display = df_display[df_display['선수'].str.contains(search_main, na=False)]
            
            # 🔥 [에러 완벽 방어] 입단년도나 선수이름에 이상한 텍스트가 섞여있어도 표를 그릴 때 충돌하지 않도록 모두 안전한 문자열로 변경
            df_display['입단'] = df_display['입단'].astype(str)
            df_display['선수'] = df_display['선수'].astype(str)
            
            for col in ['종합', '출전']:
                df_display[col] = pd.to_numeric(df_display[col], errors='coerce').apply(lambda x: f"{x:.2f}")
                
            # 최신 버전의 Streamlit 문법 경고 해결을 위해 width='stretch' 사용
            st.dataframe(
                df_display, 
                width='stretch', hide_index=True, height=500
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
                            all_involved = q['Goals'] + q['Assists'] + q['Balances'] + q['DF_CS'] + q['GK_CS']
                            if any(search_player in p for p in all_involved):
                                show_match = True
                                break
                                
                if show_match:
                    filtered_matches.append(match)

            cols = st.columns(2)
            
            for i, match in enumerate(filtered_matches):
                with cols[i % 2]:
                    html_content = f"""
                    <div style="background-color: #1A1C24; border-radius: 10px; padding: 12px; border: 1px solid #333344; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                        <div style="text-align:center; font-weight:700; color:#00D2FF; margin-bottom: 10px; font-size: 1.05rem; border-bottom: 1px solid #2A2D3E; padding-bottom: 6px;">
                            📅 {match['Date']} &nbsp;|&nbsp; <span style="color:#FFF;">{match['Home']}</span> vs <span style="color:#FFF;">{match['Away']}</span>
                        </div>
                        <table style="width:100%; text-align:center; font-size:0.85rem; border-collapse: collapse; line-height: 1.3;">
                            <thead>
                                <tr style="background-color:#2A2D3E; color:#A0A0B0;">
                                    <th style="padding:6px 2px; width:10%; border-radius: 4px 0 0 0;">Q</th>
                                    <th style="padding:6px 2px; width:15%;">Score</th>
                                    <th style="padding:6px 2px; width:15%;">⚽</th>
                                    <th style="padding:6px 2px; width:15%;">🎯</th>
                                    <th style="padding:6px 2px; width:15%;">⚖️</th>
                                    <th style="padding:6px 2px; width:15%;">🛡️</th>
                                    <th style="padding:6px 2px; width:15%; border-radius: 0 4px 0 0;">🧤</th>
                                </tr>
                            </thead>
                            <tbody>
                    """
                    
                    for q in match['Quarters']:
                        is_total = (q['Quarter'] == 'Total')
                        row_style = "background-color:#252836; font-weight:bold; color:#FFD700; border-top: 1px solid #444;" if is_total else "border-bottom: 1px solid #2A2D3E;"
                        
                        goals = format_stat_with_highlight(q['Goals'], search_player)
                        asts = format_stat_with_highlight(q['Assists'], search_player)
                        bals = format_stat_with_highlight(q['Balances'], search_player)
                        df_cs = format_stat_with_highlight(q['DF_CS'], search_player)
                        gk_cs = format_stat_with_highlight(q['GK_CS'], search_player)
                        
                        html_content += f"""
                                <tr style="{row_style}">
                                    <td style="padding:6px 2px;">{q['Quarter']}</td>
                                    <td style="padding:6px 2px;">{q['Score']}</td>
                                    <td style="padding:6px 2px;">{goals}</td>
                                    <td style="padding:6px 2px;">{asts}</td>
                                    <td style="padding:6px 2px;">{bals}</td>
                                    <td style="padding:6px 2px;">{df_cs}</td>
                                    <td style="padding:6px 2px; color:#FFA726;">{gk_cs}</td>
                                </tr>
                        """
                        
                    html_content += """
                            </tbody>
                        </table>
                    </div>
                    """
                    st.markdown(html_content, unsafe_allow_html=True)

# --- 7. 관리자 전용 데이터 업데이트 (엑셀 업로드) ---
st.divider()
with st.expander("🔒 관리자 전용 메뉴 (데이터 업데이트)"):
    pw_input = st.text_input("관리자 비밀번호를 입력하세요", type="password")
    admin_pw = st.secrets.get("ADMIN_PW", "설정안됨")
    
    if pw_input == admin_pw:
        st.success("인증 완료! 최신 엑셀 파일을 업로드하면 대시보드가 업데이트됩니다.")
        uploaded_file = st.file_uploader(f"수정된 '{selected_file}' 등 최신 파일 선택", type=['xlsx'])
        
        if uploaded_file is not None:
            if st.button("데이터 덮어쓰기 & 업데이트 진행"):
                with st.spinner("GitHub에 업로드 중... 잠시만 기다려주세요 ⏳"):
                    try:
                        from github import Github
                        g = Github(st.secrets["GITHUB_TOKEN"])
                        repo = g.get_repo(st.secrets["REPO_NAME"])
                        file_name = uploaded_file.name
                        content = uploaded_file.getvalue()
                        
                        try:
                            contents = repo.get_contents(file_name)
                            repo.update_file(contents.path, f"Update {file_name} via Dashboard", content, contents.sha)
                            st.success(f"✅ [{file_name}] 파일 덮어쓰기 성공! 대시보드를 새로고침 해주세요.")
                            st.cache_data.clear()
                        except Exception as e:
                            repo.create_file(file_name, f"Create {file_name} via Dashboard", content)
                            st.success(f"✅ [{file_name}] 신규 업로드 성공! 대시보드를 새로고침 해주세요.")
                            st.cache_data.clear()
                            
                    except Exception as e:
                        st.error(f"❌ 업로드 실패: {e} (Settings > Secrets에서 토큰과 레포지토리 이름을 확인하세요)")
