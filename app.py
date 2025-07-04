from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import json
import os

app = Flask(__name__)
CORS(app)

# 구글 시트 설정 (환경변수 지원)
KEY_FILE_PATH = os.environ.get('GOOGLE_CREDENTIALS_PATH', r'C:\Users\aizim\OneDrive\Desktop\pdf-automation\phone-billing-automation-ea8799f52353.json')
SPREADSHEET_NAME = 'CFC 전화번호 현황 및 요금'

class PhoneBillingDashboard:
    def __init__(self):
        self.gc = None
        self.spreadsheet = None
        self.master_ws = None
        self.data_ws = None
        self.init_google_sheets()
    
    def init_google_sheets(self):
        """구글 시트 초기화"""
        try:
            scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            
            # 환경변수 확인 로그
            credentials_json = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON')
            print(f"🔍 환경변수 GOOGLE_APPLICATION_CREDENTIALS_JSON 존재: {bool(credentials_json)}")
            if credentials_json:
                print(f"🔍 환경변수 길이: {len(credentials_json)} 문자")
            
            if credentials_json:
                try:
                    # JSON 문자열을 딕셔너리로 변환
                    credentials_dict = json.loads(credentials_json)
                    print(f"✅ JSON 파싱 성공, project_id: {credentials_dict.get('project_id', 'N/A')}")
                    print(f"✅ client_email: {credentials_dict.get('client_email', 'N/A')}")
                    creds = Credentials.from_service_account_info(credentials_dict, scopes=scope)
                    print("✅ 환경변수에서 구글 크리덴셜 로드 성공")
                except json.JSONDecodeError as je:
                    print(f"❌ JSON 파싱 실패: {je}")
                    print(f"🔍 JSON 앞부분 미리보기: {credentials_json[:100]}...")
                    raise
                except Exception as ce:
                    print(f"❌ 크리덴셜 로드 실패: {ce}")
                    raise
            else:
                # 로컬 파일 사용 (fallback)
                print("⚠️ 환경변수가 없음, 로컬 파일 사용 시도")
                if os.path.exists(KEY_FILE_PATH):
                    creds = Credentials.from_service_account_file(KEY_FILE_PATH, scopes=scope)
                    print("✅ 로컬 파일에서 구글 크리덴셜 로드 성공")
                else:
                    print(f"❌ 로컬 파일 없음: {KEY_FILE_PATH}")
                    raise FileNotFoundError("구글 인증 파일을 찾을 수 없습니다")
            
            # 구글 시트 연결
            print("🔄 구글 시트 연결 시도...")
            self.gc = gspread.authorize(creds)
            print(f"🔄 스프레드시트 열기 시도: '{SPREADSHEET_NAME}'")
            self.spreadsheet = self.gc.open(SPREADSHEET_NAME)
            print("✅ 스프레드시트 열기 성공")
            
            # 워크시트 연결 테스트
            print("🔄 워크시트 연결 테스트...")
            worksheets = self.spreadsheet.worksheets()
            worksheet_titles = [ws.title for ws in worksheets]
            print(f"📋 사용 가능한 워크시트: {worksheet_titles}")
            
            self.master_ws = self.spreadsheet.worksheet("전화번호 마스터")
            print("✅ 마스터 워크시트 연결 성공")
            
            self.data_ws = self.spreadsheet.worksheet("청구내역 원본")
            print("✅ 데이터 워크시트 연결 성공")
            
            # 실제 데이터 읽기 테스트
            print("🔄 데이터 읽기 테스트...")
            test_records = self.data_ws.get_all_records()
            print(f"📊 청구내역 데이터 개수: {len(test_records)}개")
            
            master_records = self.master_ws.get_all_records()
            print(f"📋 마스터 데이터 개수: {len(master_records)}개")
            
            print("🎉 구글 시트 연결 및 데이터 읽기 완료!")
            
        except Exception as e:
            print(f"🚨 구글 시트 연결 실패: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            self.gc = None
            self.spreadsheet = None
            self.master_ws = None
            self.data_ws = None
    
    def get_all_data(self):
        """모든 청구 데이터 가져오기"""
        try:
            records = self.data_ws.get_all_records()
            df = pd.DataFrame(records)
            return df
        except Exception as e:
            print(f"데이터 가져오기 실패: {e}")
            return pd.DataFrame()
    
    def get_master_data(self):
        """마스터 데이터 가져오기"""
        try:
            records = self.master_ws.get_all_records()
            df = pd.DataFrame(records)
            return df
        except Exception as e:
            print(f"마스터 데이터 가져오기 실패: {e}")
            return pd.DataFrame()

    def check_duplicates(self, billing_month):
        """특정 청구월의 중복 데이터 확인"""
        try:
            if not self.data_ws:
                return False, []
            
            existing_records = self.data_ws.get_all_records()
            duplicates = [record for record in existing_records if record.get('청구월') == billing_month]
            
            return len(duplicates) > 0, duplicates
        except Exception as e:
            print(f"중복 체크 실패: {e}")
            return False, []
    
    def delete_billing_month_data(self, billing_month):
        """특정 청구월의 모든 데이터 삭제"""
        try:
            if not self.data_ws:
                return {"success": False, "error": "워크시트가 연결되지 않음"}
            
            # 모든 데이터 가져오기
            all_records = self.data_ws.get_all_values()
            if not all_records:
                return {"success": False, "error": "데이터가 없습니다"}
            
            # 헤더 행과 삭제할 행 찾기
            header_row = all_records[0]
            billing_month_col = None
            
            # 청구월 컬럼 찾기
            for i, col in enumerate(header_row):
                if '청구월' in col:
                    billing_month_col = i
                    break
            
            if billing_month_col is None:
                return {"success": False, "error": "청구월 컬럼을 찾을 수 없습니다"}
            
            # 삭제할 행 번호 찾기 (역순으로 삭제해야 인덱스가 안 꼬임)
            rows_to_delete = []
            for i, row in enumerate(all_records[1:], start=2):  # 2부터 시작 (헤더 제외)
                if i <= len(all_records) and billing_month_col < len(row):
                    if row[billing_month_col] == billing_month:
                        rows_to_delete.append(i)
            
            # 역순으로 삭제
            deleted_count = 0
            for row_num in reversed(rows_to_delete):
                self.data_ws.delete_rows(row_num)
                deleted_count += 1
            
            return {"success": True, "deleted_count": deleted_count}
            
        except Exception as e:
            print(f"데이터 삭제 실패: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def update_spreadsheet_data(self, invoice_data, billing_month, overwrite=False):
        """구글 시트에 데이터 업데이트 (중복 체크 및 덮어쓰기 옵션 포함)"""
        try:
            # 중복 체크
            has_duplicates, existing_data = self.check_duplicates(billing_month)
            
            if has_duplicates and not overwrite:
                return {
                    "success": False, 
                    "duplicate": True,
                    "message": f"{billing_month} 청구월 데이터가 이미 존재합니다 ({len(existing_data)}건)",
                    "existing_count": len(existing_data)
                }
            
            # 덮어쓰기인 경우 기존 데이터 삭제
            if overwrite and has_duplicates:
                delete_result = self.delete_billing_month_data(billing_month)
                if not delete_result["success"]:
                    return {"success": False, "error": f"기존 데이터 삭제 실패: {delete_result['error']}"}
                print(f"기존 데이터 {delete_result['deleted_count']}건 삭제 완료")
            
            # 마스터 데이터 가져오기
            master_records = self.master_ws.get_all_records()
            master_phone_list = {str(record['전화번호']).strip(): record['지점명'] for record in master_records}
            
            # 업데이트할 데이터 준비
            rows_to_append = []
            for data in invoice_data:
                pdf_phone_number = data['전화번호']  # 예: "070-XX95-3210"
                pdf_suffix = pdf_phone_number[-7:]  # 뒷자리 7글자 "95-3210"
                
                branch_name = '미배정'
                full_phone_number = pdf_phone_number
                
                # 부분 일치로 지점명 찾기
                for master_phone, master_branch in master_phone_list.items():
                    if master_phone.endswith(pdf_suffix):
                        branch_name = master_branch
                        full_phone_number = master_phone
                        break
                
                row = [
                    billing_month, branch_name, full_phone_number,
                    data.get('기본료', 0), data.get('시내통화료', 0), data.get('이동통화료', 0),
                    data.get('070통화료', 0), data.get('정보통화료', 0), data.get('부가서비스료', 0),
                    data.get('사용요금계', 0), data.get('할인액', 0), data.get('부가세', 0), data.get('최종합계', 0)
                ]
                rows_to_append.append(row)
            
            # 구글 시트에 추가
            if rows_to_append:
                self.data_ws.append_rows(rows_to_append, value_input_option='USER_ENTERED')
                return {
                    "success": True, 
                    "rows_added": len(rows_to_append),
                    "overwritten": overwrite and has_duplicates
                }
            
            return {"success": False, "message": "추가할 데이터가 없습니다"}
            
        except Exception as e:
            print(f"데이터 업데이트 실패: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

dashboard = PhoneBillingDashboard()

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/dashboard')
def get_dashboard_data():
    """대시보드 기본 데이터"""
    try:
        df = dashboard.get_all_data()
        
        if df.empty:
            return jsonify({"error": "데이터가 없습니다"})
        
        # 최신 월 데이터 추출
        latest_month = df['청구월'].max() if '청구월' in df.columns else "알 수 없음"
        
        # KPI 계산
        total_cost = df['최종합계'].sum() if '최종합계' in df.columns else 0
        active_lines = len(df) if not df.empty else 0
        # 기본료만 발생한 회선: 사용요금계 = 기본료 (통화를 안 한 회선)
        basic_only_lines = len(df[df['사용요금계'] == df['기본료']]) if '사용요금계' in df.columns and '기본료' in df.columns else 0
        vas_fee = df['부가서비스료'].sum() if '부가서비스료' in df.columns else 0
        
        # 지점별 요금 상위 5개
        if '지점명' in df.columns and '최종합계' in df.columns:
            top_branches = df.groupby('지점명')['최종합계'].sum().sort_values(ascending=False).head(5)
            top_branches_data = [[branch, int(cost)] for branch, cost in top_branches.items()]
        else:
            top_branches_data = []
        
        # 문제 회선 (기본료만 발생하는 회선): 사용요금계 = 기본료
        if '사용요금계' in df.columns and '기본료' in df.columns:
            problem_lines = df[df['사용요금계'] == df['기본료']]
            problem_lines_data = []
            for _, row in problem_lines.head(10).iterrows():
                problem_lines_data.append([
                    row.get('지점명', ''),
                    row.get('전화번호', ''),
                    int(row.get('최종합계', 0))
                ])
        else:
            problem_lines_data = []
        
        return jsonify({
            "kpi": {
                "latestMonth": latest_month,
                "totalCost": int(total_cost),
                "activeLines": active_lines,
                "basicFeeOnlyLines": basic_only_lines,
                "totalVasFee": int(vas_fee)
            },
            "top5Branches": top_branches_data,
            "problemLines": problem_lines_data
        })
        
    except Exception as e:
        print(f"대시보드 데이터 오류: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/filter')
def filter_data():
    """필터링된 데이터 반환"""
    try:
        df = dashboard.get_all_data()
        
        # 필터 파라미터 받기
        branch = request.args.get('branch')
        month = request.args.get('month')
        phone_type = request.args.get('type')  # 'basic', 'vas', 'all'
        
        # 필터 적용
        filtered_df = df.copy()
        
        if branch and branch != 'all':
            filtered_df = filtered_df[filtered_df['지점명'] == branch]
        
        if month and month != 'all':
            filtered_df = filtered_df[filtered_df['청구월'] == month]
        
        if phone_type == 'basic':
            # 기본료만 발생하는 회선: 사용요금계 = 기본료
            filtered_df = filtered_df[filtered_df['사용요금계'] == filtered_df['기본료']]
        elif phone_type == 'vas':
            # 부가서비스 사용 회선
            filtered_df = filtered_df[filtered_df['부가서비스료'] > 0]
        
        # 결과 변환
        result = []
        for _, row in filtered_df.iterrows():
            result.append({
                "청구월": row.get('청구월', ''),
                "지점명": row.get('지점명', ''),
                "전화번호": row.get('전화번호', ''),
                "기본료": int(row.get('기본료', 0)),
                "시내통화료": int(row.get('시내통화료', 0)),
                "이동통화료": int(row.get('이동통화료', 0)),
                "070통화료": int(row.get('070통화료', 0)),
                "정보통화료": int(row.get('정보통화료', 0)),
                "부가서비스료": int(row.get('부가서비스료', 0)),
                "사용요금계": int(row.get('사용요금계', 0)),
                "할인액": int(row.get('할인액', 0)),
                "부가세": int(row.get('부가세', 0)),
                "최종합계": int(row.get('최종합계', 0))
            })
        
        return jsonify({
            "data": result,
            "total": len(result),
            "totalCost": sum([row["최종합계"] for row in result])
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/branches')
def get_branches():
    """지점 목록 반환"""
    try:
        df = dashboard.get_all_data()
        branches = sorted(df['지점명'].unique().tolist()) if '지점명' in df.columns else []
        return jsonify(branches)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/months')
def get_months():
    """청구월 목록 반환"""
    try:
        df = dashboard.get_all_data()
        months = sorted(df['청구월'].unique().tolist(), reverse=True) if '청구월' in df.columns else []
        return jsonify(months)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/search')
def search_data():
    """통합 검색 및 필터링"""
    try:
        df = dashboard.get_all_data()
        
        if df.empty:
            return jsonify({"error": "데이터가 없습니다", "data": [], "total": 0, "kpi": {}})
        
        # 필터 파라미터 받기
        branch = request.args.get('branch', '').strip()
        month = request.args.get('month', '').strip()
        phone_type = request.args.get('type', '').strip()
        search_text = request.args.get('q', '').strip()  # 통합검색
        phone_search = request.args.get('phone', '').strip()  # 전화번호 검색
        
        print(f"검색 파라미터: branch={branch}, month={month}, type={phone_type}, search={search_text}, phone={phone_search}")
        
        # 필터 적용
        filtered_df = df.copy()
        
        # 지점 필터
        if branch and branch != 'all':
            filtered_df = filtered_df[filtered_df['지점명'] == branch]
        
        # 월 필터
        if month and month != 'all':
            filtered_df = filtered_df[filtered_df['청구월'] == month]
        
        # 전화 타입 필터
        if phone_type == 'basic':
            # 기본료만 발생하는 회선: 사용요금계 = 기본료
            filtered_df = filtered_df[filtered_df['사용요금계'] == filtered_df['기본료']]
        elif phone_type == 'vas':
            # 부가서비스 사용 회선
            filtered_df = filtered_df[filtered_df['부가서비스료'] > 0]
        
        # 통합검색 (지점명, 전화번호, 모든 텍스트 컬럼)
        if search_text:
            mask = (
                filtered_df['지점명'].str.contains(search_text, na=False, case=False) |
                filtered_df['전화번호'].str.contains(search_text, na=False, case=False) |
                filtered_df['청구월'].str.contains(search_text, na=False, case=False)
            )
            filtered_df = filtered_df[mask]
        
        # 전화번호 검색 (기존 호환성)
        if phone_search:
            filtered_df = filtered_df[filtered_df['전화번호'].str.contains(phone_search, na=False)]
        
        # KPI 계산 (필터링된 데이터 기준)
        if not filtered_df.empty:
            total_cost = filtered_df['최종합계'].sum()
            active_lines = len(filtered_df)
            basic_only_lines = len(filtered_df[filtered_df['사용요금계'] == filtered_df['기본료']])
            vas_fee = filtered_df['부가서비스료'].sum()
            avg_cost = total_cost / active_lines if active_lines > 0 else 0
        else:
            total_cost = active_lines = basic_only_lines = vas_fee = avg_cost = 0
        
        # 결과 변환
        result = []
        for _, row in filtered_df.iterrows():
            result.append({
                "청구월": row.get('청구월', ''),
                "지점명": row.get('지점명', ''),
                "전화번호": row.get('전화번호', ''),
                "기본료": int(row.get('기본료', 0)),
                "시내통화료": int(row.get('시내통화료', 0)),
                "이동통화료": int(row.get('이동통화료', 0)),
                "070통화료": int(row.get('070통화료', 0)),
                "정보통화료": int(row.get('정보통화료', 0)),
                "부가서비스료": int(row.get('부가서비스료', 0)),
                "사용요금계": int(row.get('사용요금계', 0)),
                "할인액": int(row.get('할인액', 0)),
                "부가세": int(row.get('부가세', 0)),
                "최종합계": int(row.get('최종합계', 0))
            })
        
        return jsonify({
            "data": result,
            "total": len(result),
            "kpi": {
                "totalCost": int(total_cost),
                "activeLines": active_lines,
                "basicFeeOnlyLines": basic_only_lines,
                "totalVasFee": int(vas_fee),
                "avgCost": int(avg_cost)
            }
        })
        
    except Exception as e:
        print(f"검색 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "data": [], "total": 0, "kpi": {}})

@app.route('/api/upload', methods=['POST'])
def upload_pdf():
    """PDF 파일 업로드 및 처리"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "파일이 없습니다"})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "파일이 선택되지 않았습니다"})
        
        # 덮어쓰기 옵션 확인
        overwrite = request.form.get('overwrite', 'false').lower() == 'true'
        print(f"덮어쓰기 옵션: {overwrite}")
        
        if file and file.filename.lower().endswith('.pdf'):
            # 임시 파일로 저장
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                file.save(tmp_file.name)
                
                # PDF 처리
                invoice_data, billing_month = process_pdf(tmp_file.name)
                
                # 임시 파일 삭제
                os.unlink(tmp_file.name)
                
                if invoice_data:
                    # 구글 시트에 업데이트 (덮어쓰기 옵션 포함)
                    update_result = dashboard.update_spreadsheet_data(invoice_data, billing_month, overwrite)
                    
                    if update_result.get("duplicate") and not overwrite:
                        # 중복 데이터 발견
                        return jsonify({
                            "duplicate": True,
                            "billing_month": billing_month,
                            "message": update_result["message"],
                            "existing_count": update_result["existing_count"],
                            "new_data_count": len(invoice_data)
                        })
                    elif update_result["success"]:
                        # 성공
                        message = f"{len(invoice_data)}개의 데이터가 처리되었습니다"
                        if update_result.get("overwritten"):
                            message += " (기존 데이터 덮어쓰기 완료)"
                        
                        return jsonify({
                            "success": True,
                            "message": message,
                            "billing_month": billing_month,
                            "data_count": len(invoice_data),
                            "overwritten": update_result.get("overwritten", False)
                        })
                    else:
                        # 실패
                        return jsonify({"error": update_result.get("error", "알 수 없는 오류")})
                else:
                    return jsonify({"error": "PDF에서 데이터를 추출할 수 없습니다"})
        else:
            return jsonify({"error": "PDF 파일만 업로드 가능합니다"})
            
    except Exception as e:
        print(f"PDF 업로드 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"파일 처리 중 오류: {str(e)}"})

@app.route('/api/delete', methods=['POST'])
def delete_billing_data():
    """특정 청구월 데이터 삭제"""
    try:
        data = request.get_json()
        billing_month = data.get('billing_month')
        
        if not billing_month:
            return jsonify({"error": "청구월을 선택해주세요"})
        
        print(f"청구월 삭제 요청: {billing_month}")
        
        # 구글 시트 연결 확인
        if not dashboard.gc:
            return jsonify({"error": "구글 시트에 연결할 수 없습니다"})
        
        # 삭제 실행
        delete_result = dashboard.delete_billing_month_data(billing_month)
        
        if delete_result["success"]:
            return jsonify({
                "success": True,
                "message": f"{billing_month} 청구월 데이터 {delete_result['deleted_count']}건이 삭제되었습니다",
                "deleted_count": delete_result['deleted_count']
            })
        else:
            return jsonify({"error": delete_result["error"]})
            
    except Exception as e:
        print(f"삭제 API 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"삭제 중 오류: {str(e)}"})

def process_pdf(file_path):
    """PDF 파일에서 데이터 추출 (기존 main.py 로직 활용)"""
    import pypdf
    import re
    
    try:
        # PDF 읽기
        with open(file_path, 'rb') as pdf_file:
            reader = pypdf.PdfReader(pdf_file)
            full_text = "".join(page.extract_text() for page in reader.pages)
        
        # 청구월 추출
        billing_month_match = re.search(r'(\d{4})년\s*(\d{2})월', full_text)
        billing_month = f"{billing_month_match.group(1)}-{billing_month_match.group(2)}" if billing_month_match else "날짜모름"
        
        # 데이터 파싱
        blocks = re.split(r'유선전화', full_text)
        parsed_data = []
        
        for block in blocks[1:]:
            phone_match = re.search(r'070\)\*\*(\d{2}-\d{4})', block)
            if not phone_match:
                continue
            
            phone_number = f"070-XX{phone_match.group(1)}"
            
            def find_amount(pattern):
                match = re.search(pattern, block)
                return int(match.group(1).replace(',', '')) if match else 0
            
            data = {
                '전화번호': phone_number,
                '기본료': find_amount(r'인터넷전화기본료\s+([\d,]+)'),
                '시내통화료': find_amount(r'시내통화료\s+([\d,]+)'),
                '이동통화료': find_amount(r'이동통화료\s+([\d,]+)'),
                '070통화료': find_amount(r'인터넷전화통화료\(070\)\s+([\d,]+)'),
                '정보통화료': find_amount(r'정보통화료\s+([\d,]+)'),
                '부가서비스료': find_amount(r'부가서비스이용료\s+([\d,]+)'),
                '사용요금계': find_amount(r'사용요금 계\s+([\d,]+)'),
                '할인액': find_amount(r'할인\s+-([\d,]+)'),
                '부가세': find_amount(r'부가가치세\(세금\)\*\s+([\d,]+)'),
                '최종합계': find_amount(r'합계\s+([\d,]+)')
            }
            parsed_data.append(data)
            
        return parsed_data, billing_month
        
    except Exception as e:
        print(f"PDF 처리 오류: {e}")
        return None, None

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
