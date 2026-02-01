import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from datetime import datetime
import json
import os
import base64

# 1. 페이지 기본 설정
st.set_page_config(page_title="업무 관리 시스템", layout="wide")
st.title("🎬 프로젝트 업무 관리")  # 제목 깔끔하게 수정됨

# --- [설정] 구글 시트 연결 ---
SHEET_URL = "WorkDB" 

@st.cache_resource
def connect_to_gsheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 1. 로컬 환경
    if os.path.exists("service_account.json"):
        creds = Credentials.from_service_account_file("service_account.json", scopes=scopes)
    
    # 2. 클라우드 환경 (Base64 암호문 해독)
    else:
        try:
            if "encoded_key" in st.secrets["gcp_service_account"]:
                encoded_val = st.secrets["gcp_service_account"]["encoded_key"]
                decoded_val = base64.b64decode(encoded_val).decode("utf-8")
                key_dict = json.loads(decoded_val)
                creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
            else:
                st.error("Secrets 설정을 확인해주세요 (encoded_key 없음).")
                st.stop()
            
        except Exception as e:
            st.error(f"⚠️ 인증 실패: {e}")
            st.stop()
            
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_URL).sheet1
    return sheet

try:
    worksheet = connect_to_gsheet()
except Exception as e:
    st.error(f"구글 시트 연결 실패! 시트 이름('{SHEET_URL}') 및 봇 초대를 확인하세요.\n에러: {e}")
    st.stop()

# 2. 데이터 불러오기
def load_data():
    # 컬럼 순서나 이름은 그대로 유지
    default_columns = ['년도', '월', '프로젝트명', '설명', '진행상태', '담당PD', '기획', '촬영', '편집', '디자인', 'CG', '색보정', 'SFX', 'BGM', '시사']
    try:
        df = get_as_dataframe(worksheet)
        if df.empty:
            df = pd.DataFrame(columns=default_columns)
        else:
            df = df.dropna(how='all').dropna(axis=1, how='all')
            for col in default_columns:
                if col not in df.columns:
                    df[col] = ""
        df = df.fillna("")
        df['진행상태'] = df['진행상태'].replace('', '기획')
        return df
    except Exception as e:
        return pd.DataFrame(columns=default_columns)

# 3. 데이터 저장하기
def save_data(df):
    try:
        worksheet.clear()
        set_with_dataframe(worksheet, df)
        st.toast("저장 완료! ☁️")
    except Exception as e:
        st.error(f"저장 실패: {e}")

df = load_data()

# 4. 사이드바 - 필터링 (년도, 월, 담당PD)
st.sidebar.header("🔍 프로젝트 검색")
current_year = datetime.now().year
current_month = datetime.now().month

# (1) 년도/월 데이터 추출 및 선택
if not df.empty and '년도' in df.columns and len(df) > 0:
    df['년도'] = pd.to_numeric(df['년도'], errors='coerce').fillna(current_year).astype(int)
    df['월'] = pd.to_numeric(df['월'], errors='coerce').fillna(current_month).astype(int)
    
    unique_years = sorted(df['년도'].unique().tolist(), reverse=True)
    if not unique_years: unique_years = [current_year]
    selected_year = st.sidebar.selectbox("년도", unique_years)

    unique_months = sorted(df[df['년도'] == selected_year]['월'].unique().tolist())
    if not unique_months: unique_months = [current_month]
    selected_month = st.sidebar.selectbox("월", unique_months)
else:
    selected_year = current_year
    selected_month = current_month
    st.sidebar.info("등록된 프로젝트가 없습니다.")

# (2) 담당PD 필터 추가 (새로운 기능!)
selected_pd = "전체"
if not df.empty and '담당PD' in df.columns:
    # 빈칸 제외하고 PD 목록 만들기
    pd_list = sorted([pd for pd in df['담당PD'].unique().tolist() if str(pd).strip() != ""])
    pd_list.insert(0, "전체") # 맨 앞에 '전체' 옵션 추가
    selected_pd = st.sidebar.selectbox("담당 PD", pd_list)

# 진행 상태 옵션 (요청하신 순서대로 변경)
status_options = ['기획', '촬영', '컷편집', '그래픽', '음향', '수정', '시사', '완료', '보류']

# 상태별 색상 매핑
status_colors = {
    '기획': 'blue',    # 파랑
    '촬영': 'red',     # 빨강
    '컷편집': 'orange', # 주황
    '그래픽': 'violet', # 보라
    '음향': 'green',   # 초록
    '수정': 'red',     # 빨강 (긴급 느낌)
    '시사': 'blue',    # 파랑 (완료 직전)
    '완료': 'grey',    # 회색
    '보류': 'grey'     # 회색
}

# 5. 새 프로젝트 추가
with st.expander("➕ 새 프로젝트 추가하기"):
    with st.form("new_project_form"):
        col1, col2 = st.columns(2)
        new_year = col1.number_input("년도", value=selected_year, step=1)
        new_month = col2.number_input("월", value=selected_month, min_value=1, max_value=12)
        new_name = st.text_input("프로젝트명")
        new_desc = st.text_area("상세 설명")
        new_status = st.selectbox("초기 진행 상태", status_options)
        new_sisa_date = st.date_input("시사 예정일 (선택)", value=None)
        
        # 새 프로젝트 담당자는 현재 선택된 PD가 '전체'가 아니면 자동으로 입력
        default_pd_val = selected_pd if selected_pd != "전체" else ""
        new_pd = st.text_input("담당PD", value=default_pd_val)
        
        if st.form_submit_button("프로젝트 생성"):
            if new_name.strip() == "":
                st.error("프로젝트 이름을 입력해주세요!")
            else:
                new_data = {
                    '년도': new_year, '월': new_month, '프로젝트명': new_name, '설명': new_desc, '진행상태': new_status,
                    '담당PD': new_pd, '기획': '', '촬영': '', '편집': '', '디자인': '', 
                    'CG': '', '색보정': '', 'SFX': '', 'BGM': '', 
                    '시사': str(new_sisa_date) if new_sisa_date else ''
                }
                new_df = pd.DataFrame([new_data])
                if df.empty: df = new_df
                else: df = pd.concat([df, new_df], ignore_index=True)
                save_data(df)
                st.success(f"✅ '{new_name}' 추가됨")
                st.rerun()

# 6. 메인 화면 리스트 출력
st.divider()

# 제목에 필터링 상태 표시
pd_title_suffix = f" ({selected_pd})" if selected_pd != "전체" else ""
st.subheader(f"{selected_year}년 {selected_month}월 프로젝트{pd_title_suffix}")

# [필터링 로직]
if not df.empty:
    # 1. 년/월 필터
    current_df = df[(df['년도'] == selected_year) & (df['월'] == selected_month)]
    
    # 2. 담당PD 필터 (전체가 아닐 때만 적용)
    if selected_pd != "전체":
        current_df = current_df[current_df['담당PD'] == selected_pd]
else:
    current_df = pd.DataFrame(columns=df.columns)

# 진행 중 / 완료 분리
if not current_df.empty:
    active_df = current_df[current_df['진행상태'] != '완료']
    completed_df = current_df[current_df['진행상태'] == '완료']
else:
    active_df = pd.DataFrame(columns=df.columns)
    completed_df = pd.DataFrame(columns=df.columns)

tab1, tab2 = st.tabs([f"🔥 진행 중 ({len(active_df)})", f"✅ 완료됨 ({len(completed_df)})"])

def render_project_list(target_df):
    if target_df.empty:
        st.info("조건에 맞는 프로젝트가 없습니다.")
        return
        
    today = datetime.now().date()
    
    for index, row in target_df.iterrows():
        current_status = row['진행상태'] if pd.notna(row['진행상태']) else '기획'
        # 상태값이 리스트에 없으면 기본 회색 처리 (에러 방지)
        base_color = status_colors.get(current_status, 'grey')
        
        is_urgent = False
        d_day_str = ""
        sisa_val = row['시사']
        sisa_date_obj = None 
        
        if pd.notna(sisa_val) and str(sisa_val).strip() != "":
            try:
                sisa_date_obj = datetime.strptime(str(sisa_val), "%Y-%m-%d").date()
                days_left = (sisa_date_obj - today).days
                if days_left < 0: 
                    d_day_str = f"(D+{abs(days_left)})"
                elif days_left == 0: 
                    d_day_str = "(D-Day)"
                    is_urgent = True
                else: 
                    d_day_str = f"(D-{days_left})"
                    if days_left <= 3: is_urgent = True
            except:
                pass 

        # 제목 포맷팅
        if is_urgent and current_status != '완료':
            expander_title = f"🚨 :red[**[긴급 {d_day_str}]** {row['프로젝트명']}] (PD: {row['담당PD']})"
        else:
            expander_title = f":{base_color}[[{current_status}]] {row['프로젝트명']} {d_day_str} (PD: {row['담당PD']})"
        
        with st.expander(expander_title):
            with st.form(f"edit_form_{index}"):
                st.markdown(f"#### 🚦 상태: :{base_color}[{current_status}]")
                # 인덱스 에러 방지 (옵션에 없는 값이 들어있을 경우 대비)
                try:
                    status_index = status_options.index(current_status)
                except ValueError:
                    status_index = 0
                    
                edit_status = st.selectbox("진행 상태 변경", status_options, index=status_index)
                
                st.markdown("---")
                
                edit_desc = st.text_area("상세 설명", value=str(row['설명']))
                edit_pd = st.text_input("담당PD", value=str(row['담당PD']))
                
                c1, c2 = st.columns(2)
                edit_plan = c1.text_input("기획", value=str(row['기획']))
                edit_shoot = c2.text_input("촬영", value=str(row['촬영']))
                
                c3, c4 = st.columns(2)
                edit_edit = c3.text_input("편집 (컷편집)", value=str(row['편집'])) # 컬럼명은 유지하되 라벨만 변경
                edit_design = c4.text_input("디자인 (그래픽)", value=str(row['디자인']))
                
                c5, c6 = st.columns(2)
                edit_cg = c5.text_input("CG", value=str(row['CG']))
                edit_color = c6.text_input("색보정", value=str(row['색보정']))
                
                c7, c8 = st.columns(2)
                edit_sfx = c7.text_input("음향 (SFX)", value=str(row['SFX']))
                edit_bgm = c8.text_input("BGM", value=str(row['BGM']))
                
                st.markdown(f"##### 📅 시사 일정 {d_day_str}")
                edit_sisa = st.date_input("날짜 선택", value=sisa_date_obj if sisa_date_obj else None)

                if st.form_submit_button("수정사항 저장"):
                    df.at[index, '진행상태'] = edit_status
                    df.at[index, '설명'] = edit_desc
                    df.at[index, '담당PD'] = edit_pd
                    df.at[index, '기획'] = edit_plan
                    df.at[index, '촬영'] = edit_shoot
                    df.at[index, '편집'] = edit_edit
                    df.at[index, '디자인'] = edit_design
                    df.at[index, 'CG'] = edit_cg
                    df.at[index, '색보정'] = edit_color
                    df.at[index, 'SFX'] = edit_sfx
                    df.at[index, 'BGM'] = edit_bgm
                    df.at[index, '시사'] = str(edit_sisa) if edit_sisa else ''
                    
                    save_data(df)
                    st.rerun()

            st.markdown("")
            col_empty, col_del = st.columns([6, 1])
            with col_del:
                if st.button("🗑️ 삭제", key=f"del_{index}"):
                    df.drop(index, inplace=True)
                    save_data(df)
                    st.toast("프로젝트가 삭제되었습니다.")
                    st.rerun()

with tab1:
    render_project_list(active_df)

with tab2:
    render_project_list(completed_df)