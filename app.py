import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from datetime import datetime
import json
import os

# 1. 페이지 기본 설정
st.set_page_config(page_title="업무 관리 시스템", layout="wide")
st.title("🎬 프로젝트 업무 관리 (Google Sheets Ver.)")

# --- [설정] 구글 시트 연결 ---
# 구글 시트 이름 (본인의 구글 시트 제목과 똑같이 적으세요!)
SHEET_URL = "WorkDB" 

# 구글 시트 인증 및 연결 함수 (로컬/클라우드 호환 버전)
# --- [수정된 연결 함수] ---
@st.cache_resource
def connect_to_gsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 1. 로컬 환경: 내 컴퓨터에 파일이 있는지 확인
    if os.path.exists("service_account.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    
    # 2. 클라우드 환경: Secrets 확인
    else:
        try:
            # secrets에서 가져오기
            secret_val = st.secrets["gcp_service_account"]["json_key"]
            
            # [에러 해결 핵심] secret_val이 이미 딕셔너리인지, 문자열인지 확인해서 처리
            if isinstance(secret_val, str):
                key_dict = json.loads(secret_val) # 문자열이면 변환 (반드시 loads 사용!)
            else:
                key_dict = secret_val # 이미 딕셔너리라면 그대로 사용
                
            creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
            
        except Exception as e:
            st.error(f"⚠️ 인증 정보 오류: Secrets 설정을 확인해주세요.\n에러 내용: {e}")
            st.stop()
            
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_URL).sheet1
    return sheet

try:
    worksheet = connect_to_gsheet()
    # 연결 성공 시 토스트 메시지는 너무 자주 뜨면 귀찮으므로 주석 처리 가능
    # st.toast("구글 시트 연결 성공! 🟢")
except Exception as e:
    st.error(f"구글 시트 연결 실패! 시트 이름('{SHEET_URL}')이 맞는지, 봇 계정이 초대되었는지 확인하세요.\n에러: {e}")
    st.stop()

# 2. 데이터 불러오기 (구글 시트 -> 데이터프레임)
def load_data():
    default_columns = ['년도', '월', '프로젝트명', '설명', '진행상태', '담당PD', '기획', '촬영', '편집', '디자인', 'CG', '색보정', 'SFX', 'BGM', '시사']
    
    try:
        df = get_as_dataframe(worksheet)
        
        # 빈 시트일 경우 기본 컬럼 생성
        if df.empty:
            df = pd.DataFrame(columns=default_columns)
        else:
            # gspread가 가져오는 불필요한 빈 행/열 제거
            df = df.dropna(how='all').dropna(axis=1, how='all')
            
            # 필수 컬럼이 없으면 추가
            for col in default_columns:
                if col not in df.columns:
                    df[col] = ""
        
        # 데이터 정제 (NaN -> 빈 문자열)
        df = df.fillna("")
        # 진행상태 빈 곳 채우기
        df['진행상태'] = df['진행상태'].replace('', '기획')
        
        return df
        
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        return pd.DataFrame(columns=default_columns)

# 3. 데이터 저장하기 (데이터프레임 -> 구글 시트)
def save_data(df):
    try:
        worksheet.clear() # 기존 내용 삭제
        set_with_dataframe(worksheet, df) # 새 내용 덮어쓰기
        st.toast("저장 완료! ☁️")
    except Exception as e:
        st.error(f"저장 실패: {e}")

# 데이터 로드 실행
df = load_data()

# 4. 사이드바 - 년/월 필터링 로직
st.sidebar.header("📅 날짜 선택")
current_year = datetime.now().year
current_month = datetime.now().month

if not df.empty and '년도' in df.columns and len(df) > 0:
    # 데이터 타입을 숫자로 강제 변환 (에러 방지)
    df['년도'] = pd.to_numeric(df['년도'], errors='coerce').fillna(current_year).astype(int)
    df['월'] = pd.to_numeric(df['월'], errors='coerce').fillna(current_month).astype(int)
    
    unique_years = sorted(df['년도'].unique().tolist(), reverse=True)
    if not unique_years: unique_years = [current_year]
    selected_year = st.sidebar.selectbox("년도 선택", unique_years)

    unique_months = sorted(df[df['년도'] == selected_year]['월'].unique().tolist())
    if not unique_months: unique_months = [current_month]
    selected_month = st.sidebar.selectbox("월 선택", unique_months)
else:
    selected_year = current_year
    selected_month = current_month
    st.sidebar.info("등록된 프로젝트가 없습니다.")

# 상태 옵션 및 색상 정의
status_options = ['기획', '촬영', '편집', '후반작업', '시사', '완료', '보류']
status_colors = {
    '기획': 'blue', '촬영': 'red', '편집': 'orange',
    '후반작업': 'violet', '시사': 'green', '완료': 'grey', '보류': 'grey'
}

# 5. 새 프로젝트 추가 (Expander)
with st.expander("➕ 새 프로젝트 추가하기"):
    with st.form("new_project_form"):
        col1, col2 = st.columns(2)
        new_year = col1.number_input("년도", value=selected_year, step=1)
        new_month = col2.number_input("월", value=selected_month, min_value=1, max_value=12)
        new_name = st.text_input("프로젝트명")
        new_desc = st.text_area("상세 설명")
        new_status = st.selectbox("초기 진행 상태", status_options)
        new_sisa_date = st.date_input("시사 예정일 (선택)", value=None)
        
        if st.form_submit_button("프로젝트 생성"):
            if new_name.strip() == "":
                st.error("프로젝트 이름을 입력해주세요!")
            else:
                new_data = {
                    '년도': new_year, '월': new_month, '프로젝트명': new_name, '설명': new_desc, '진행상태': new_status,
                    '담당PD': '', '기획': '', '촬영': '', '편집': '', '디자인': '', 
                    'CG': '', '색보정': '', 'SFX': '', 'BGM': '', 
                    '시사': str(new_sisa_date) if new_sisa_date else ''
                }
                new_df = pd.DataFrame([new_data])
                
                # 기존 데이터에 추가
                if df.empty:
                    df = new_df
                else:
                    df = pd.concat([df, new_df], ignore_index=True)
                
                save_data(df)
                st.success(f"✅ '{new_name}' 프로젝트 추가됨")
                st.rerun()

# 6. 메인 화면 - 탭 구성 및 리스트 출력
st.divider()
st.subheader(f"{selected_year}년 {selected_month}월 프로젝트")

# 현재 년/월 필터링
if not df.empty:
    current_df = df[(df['년도'] == selected_year) & (df['월'] == selected_month)]
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

# 리스트 렌더링 함수
def render_project_list(target_df):
    if target_df.empty:
        st.info("이 항목에 해당하는 프로젝트가 없습니다.")
        return

    today = datetime.now().date()
    
    # iterrows 사용 (행 단위 반복)
    for index, row in target_df.iterrows():
        current_status = row['진행상태'] if pd.notna(row['진행상태']) else '기획'
        base_color = status_colors.get(current_status, 'grey')
        
        # D-Day 계산 로직
        is_urgent = False
        d_day_str = ""
        sisa_val = row['시사']
        sisa_date_obj = None 
        
        if pd.notna(sisa_val) and str(sisa_val).strip() != "":
            try:
                # 문자열을 날짜 객체로 변환
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
        
        # 상세 내용 (Expander)
        with st.expander(expander_title):
            with st.form(f"edit_form_{index}"):
                st.markdown(f"#### 🚦 상태: :{base_color}[{current_status}]")
                edit_status = st.selectbox("진행 상태 변경", status_options, index=status_options.index(current_status))
                
                st.markdown("---")
                
                edit_desc = st.text_area("상세 설명", value=str(row['설명']))
                edit_pd = st.text_input("담당PD", value=str(row['담당PD']))
                
                # 담당자 입력칸 (2열 배치)
                c1, c2 = st.columns(2)
                edit_plan = c1.text_input("기획", value=str(row['기획']))
                edit_shoot = c2.text_input("촬영", value=str(row['촬영']))
                
                c3, c4 = st.columns(2)
                edit_edit = c3.text_input("편집", value=str(row['편집']))
                edit_design = c4.text_input("디자인", value=str(row['디자인']))
                
                c5, c6 = st.columns(2)
                edit_cg = c5.text_input("CG", value=str(row['CG']))
                edit_color = c6.text_input("색보정", value=str(row['색보정']))
                
                c7, c8 = st.columns(2)
                edit_sfx = c7.text_input("SFX", value=str(row['SFX']))
                edit_bgm = c8.text_input("BGM", value=str(row['BGM']))
                
                st.markdown(f"##### 📅 시사 일정 {d_day_str}")
                edit_sisa = st.date_input("날짜 선택", value=sisa_date_obj if sisa_date_obj else None)

                # 수정 버튼
                if st.form_submit_button("수정사항 저장"):
                    # 데이터프레임 값 업데이트
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
                    
                    save_data(df) # 구글 시트 저장
                    st.rerun() # 새로고침

            # 삭제 버튼 (실수 방지용 우측 하단 배치)
            st.markdown("")
            col_empty, col_del = st.columns([6, 1])
            with col_del:
                if st.button("🗑️ 삭제", key=f"del_{index}"):
                    df.drop(index, inplace=True)
                    save_data(df)
                    st.toast("프로젝트가 삭제되었습니다.")
                    st.rerun()

# 탭 내용 표시
with tab1:
    render_project_list(active_df)

with tab2:
    render_project_list(completed_df)