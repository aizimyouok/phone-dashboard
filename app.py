from flask import Flask, jsonify, render_template, request, send_file, redirect
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import json
import os
import tempfile
import io
import pypdf
import re

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
            print(f"환경변수 GOOGLE_APPLICATION_CREDENTIALS_JSON 존재: {bool(credentials_json)}")
            if credentials_json:
                print(f"환경변수 길이: {len(credentials_json)} 문자")
            
            if credentials_json:
                try:
                    # JSON 문자열을 딕셔너리로 변환
                    credentials_dict = json.loads(credentials_json)
                    print(f"JSON 파싱 성공, project_id: {credentials_dict.get('project_id', 'N/A')}")
                    print(f"client_email: {credentials_dict.get('client_email', 'N/A')}")
                    creds = Credentials.from_service_account_info(credentials_dict, scopes=scope)
                    print("환경변수에서 구글 크리덴셜 로드 성공")
                except json.JSONDecodeError as je:
                    print(f"JSON 파싱 실패: {je}")
                    print(f"JSON 앞부분 미리보기: {credentials_json[:100]}...")
                    raise
                except Exception as ce:
                    print(f"크리덴셜 로드 실패: {ce}")
                    raise
            else:
                # 로컬 파일 사용 (fallback)
                print("환경변수가 없음, 로컬 파일 사용 시도")
                if os.path.exists(KEY_FILE_PATH):
                    creds = Credentials.from_service_account_file(KEY_FILE_PATH, scopes=scope)
                    print("로컬 파일에서 구글 크리덴셜 로드 성공")
                else:
                    print(f"로컬 파일 없음: {KEY_FILE_PATH}")
                    raise FileNotFoundError("구글 인증 파일을 찾을 수 없습니다")
            
            # 구글 시트 연결
            print("구글 시트 연결 시도...")
            self.gc = gspread.authorize(creds)
            print(f"스프레드시트 열기 시도: '{SPREADSHEET_NAME}'")
            self.spreadsheet = self.gc.open(SPREADSHEET_NAME)
            print("스프레드시트 열기 성공")
            
            # 워크시트 연결 테스트
            print("워크시트 연결 테스트...")
            worksheets = self.spreadsheet.worksheets()
            worksheet_titles = [ws.title for ws in worksheets]
            print(f"사용 가능한 워크시트: {worksheet_titles}")
            
            self.master_ws = self.spreadsheet.worksheet("전화번호 마스터")
            print("마스터 워크시트 연결 성공")
            
            self.data_ws = self.spreadsheet.worksheet("청구내역 원본")
            print("데이터 워크시트 연결 성공")
            
            # 실제 데이터 읽기 테스트
            print("데이터 읽기 테스트...")
            test_records = self.data_ws.get_all_records()
            print(f"청구내역 데이터 개수: {len(test_records)}개")
            
            master_records = self.master_ws.get_all_records()
            print(f"마스터 데이터 개수: {len(master_records)}개")
            
            print("구글 시트 연결 및 데이터 읽기 완료!")
            
        except Exception as e:
            print(f"구글 시트 연결 실패: {type(e).__name__}: {e}")
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

    def check_duplicates(self, invoice_data, billing_month):
        """청구월 + 전화번호 + 최종합계 기준으로 중복 데이터 확인"""
        try:
            if not self.data_ws:
                return False, []
            
            existing_records = self.data_ws.get_all_records()
            
            # 새로 업로드할 데이터와 기존 데이터 비교
            duplicates = []
            for new_data in invoice_data:
                new_phone = new_data['전화번호']
                new_amount = new_data['최종합계']
                
                # PDF 전화번호에서 뒷자리 패턴 추출
                pdf_suffix = None
                # 뒷자리 패턴 추출
                suffix_patterns = [
                    r'XX(\d{2}-\d{4})$',      # 070-XX95-3210, 02-XX98-7065
                    r'XXXX-(\d{2}-\d{4})$',   # XXXX-99-2593  
                    r'XX(\d{1,2}-\d{4})$',    # 기타 변형
                    r'XX(\d{1}-\d{4})$',      # 080-XX0-7100 형태
                ]
                
                for pattern in suffix_patterns:
                    match = re.search(pattern, new_phone)
                    if match:
                        pdf_suffix = match.group(1)
                        break
                
                # 뒷자리가 추출되지 않았다면 전체 번호에서 마지막 7글자 시도
                if not pdf_suffix:
                    clean_number = re.sub(r'[^0-9-]', '', new_phone)
                    if len(clean_number) >= 7:
                        pdf_suffix = clean_number[-7:]
                
                # 청구월 + 전화번호 + 최종합계가 모두 일치하는 기존 데이터 찾기
                for existing in existing_records:
                    if existing.get('청구월') != billing_month:
                        continue
                    
                    if existing.get('최종합계') != new_amount:
                        continue
                    
                    existing_phone = existing.get('전화번호', '')
                    
                    # 전화번호 매칭 (다양한 방식으로 시도)
                    is_phone_match = False
                    
                    if pdf_suffix:
                        # 1. 뒷자리 매칭
                        if existing_phone.endswith(pdf_suffix):
                            is_phone_match = True
                        # 2. 숫자만 비교
                        else:
                            existing_digits = re.sub(r'[^0-9]', '', existing_phone)
                            pdf_digits = re.sub(r'[^0-9]', '', pdf_suffix)
                            if len(existing_digits) >= len(pdf_digits) and existing_digits.endswith(pdf_digits):
                                is_phone_match = True
                    
                    if is_phone_match:
                        duplicates.append({
                            'new': new_data,
                            'existing': existing
                        })
                        break
            
            return len(duplicates) > 0, duplicates
        except Exception as e:
            print(f"중복 체크 실패: {e}")
            return False, []
    
    def delete_duplicate_data(self, duplicates):
        """중복된 특정 데이터들만 삭제"""
        try:
            if not self.data_ws or not duplicates:
                return {"success": False, "error": "삭제할 데이터가 없습니다"}
            
            # 모든 데이터 가져오기
            all_records = self.data_ws.get_all_values()
            if not all_records:
                return {"success": False, "error": "데이터가 없습니다"}
            
            # 헤더 행과 컬럼 인덱스 찾기
            header_row = all_records[0]
            phone_col = billing_month_col = amount_col = None
            
            for i, col in enumerate(header_row):
                if '전화번호' in col:
                    phone_col = i
                elif '청구월' in col:
                    billing_month_col = i
                elif '최종합계' in col:
                    amount_col = i
            
            if phone_col is None or billing_month_col is None or amount_col is None:
                return {"success": False, "error": "필요한 컬럼을 찾을 수 없습니다"}
            
            # 삭제할 행 번호 찾기 (역순으로 삭제해야 인덱스가 안 꼬임)
            rows_to_delete = []
            for duplicate in duplicates:
                existing_data = duplicate['existing']
                target_phone = existing_data.get('전화번호', '')
                target_month = existing_data.get('청구월', '')
                target_amount = existing_data.get('최종합계', 0)
                
                for i, row in enumerate(all_records[1:], start=2):  # 2부터 시작 (헤더 제외)
                    if (i <= len(all_records) and 
                        phone_col < len(row) and billing_month_col < len(row) and amount_col < len(row)):
                        row_phone = row[phone_col]
                        row_month = row[billing_month_col]
                        try:
                            row_amount = int(row[amount_col]) if row[amount_col] else 0
                        except:
                            row_amount = 0
                        
                        if (row_month == target_month and 
                            row_phone == target_phone and 
                            row_amount == target_amount):
                            rows_to_delete.append(i)
                            break
            
            # 중복 제거 후 역순으로 삭제
            rows_to_delete = sorted(set(rows_to_delete), reverse=True)
            deleted_count = 0
            for row_num in rows_to_delete:
                self.data_ws.delete_rows(row_num)
                deleted_count += 1
            
            return {"success": True, "deleted_count": deleted_count}
            
        except Exception as e:
            print(f"중복 데이터 삭제 실패: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def delete_billing_month_data(self, billing_month):
        """특정 청구월의 모든 데이터 삭제 (월별 데이터 삭제용)"""
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
            print(f"월별 데이터 삭제 실패: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
            
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
        """구글 시트에 데이터 업데이트 (정밀한 중복 체크 및 덮어쓰기 옵션 포함)"""
        try:
            # 중복 체크 (청구월 + 전화번호 + 최종합계 기준)
            has_duplicates, duplicates = self.check_duplicates(invoice_data, billing_month)
            
            if has_duplicates and not overwrite:
                return {
                    "success": False, 
                    "duplicate": True,
                    "message": f"{billing_month} 청구월에서 {len(duplicates)}건의 중복 데이터가 발견되었습니다",
                    "existing_count": len(duplicates),
                    "duplicates": duplicates  # 중복 상세 정보 포함
                }
            
            # 덮어쓰기인 경우 중복 데이터만 삭제
            if overwrite and has_duplicates:
                delete_result = self.delete_duplicate_data(duplicates)
                if not delete_result["success"]:
                    return {"success": False, "error": f"중복 데이터 삭제 실패: {delete_result['error']}"}
                print(f"중복 데이터 {delete_result['deleted_count']}건 삭제 완료")
            
            # 마스터 데이터 가져오기
            master_records = self.master_ws.get_all_records()
            master_phone_list = {str(record['전화번호']).strip(): record['지점명'] for record in master_records}
            # 사용자 정보도 함께 저장
            master_user_list = {str(record['전화번호']).strip(): record.get('사용자', '') for record in master_records}
            
            # 업데이트할 데이터 준비
            rows_to_append = []
            for data in invoice_data:
                pdf_phone_number = data['전화번호']  # 예: "070-XX95-3210", "02-XX98-7065", "XXXX-99-2593"
                
                # 다양한 전화번호 형태에서 뒷자리 추출
                branch_name = '미배정'
                user_name = ''
                full_phone_number = pdf_phone_number
                
                # PDF 전화번호에서 뒷자리 패턴 추출
                pdf_suffix = None
                
                # 뒷자리 패턴 추출 (다양한 형태 지원)
                suffix_patterns = [
                    r'XX(\d{2}-\d{4})$',      # 070-XX95-3210, 02-XX98-7065
                    r'XXXX-(\d{2}-\d{4})$',   # XXXX-99-2593  
                    r'XX(\d{1,2}-\d{4})$',    # 기타 변형
                    r'XX(\d{1}-\d{4})$',      # 080-XX0-7100 형태
                ]
                
                for pattern in suffix_patterns:
                    match = re.search(pattern, pdf_phone_number)
                    if match:
                        pdf_suffix = match.group(1)
                        break
                
                # 뒷자리가 추출되지 않았다면 전체 번호에서 마지막 7글자 시도
                if not pdf_suffix:
                    # 숫자와 하이픈만 추출해서 뒷자리 7글자 사용
                    clean_number = re.sub(r'[^0-9-]', '', pdf_phone_number)
                    if len(clean_number) >= 7:
                        pdf_suffix = clean_number[-7:]
                
                # 마스터 데이터와 매칭
                if pdf_suffix:
                    for master_phone, master_branch in master_phone_list.items():
                        # 1. 정확한 뒷자리 매칭 (우선순위 1)
                        if master_phone.endswith(pdf_suffix):
                            branch_name = master_branch
                            user_name = master_user_list.get(master_phone, '')
                            full_phone_number = master_phone
                            break
                        
                        # 2. 숫자만 비교 매칭 (우선순위 2)
                        master_digits = re.sub(r'[^0-9]', '', master_phone)
                        pdf_digits = re.sub(r'[^0-9]', '', pdf_suffix)
                        
                        if len(master_digits) >= len(pdf_digits) and master_digits.endswith(pdf_digits):
                            branch_name = master_branch
                            user_name = master_user_list.get(master_phone, '')
                            full_phone_number = master_phone
                            break
                
                # 새로운 열 구조에 맞게 데이터 배열 (사용자 열 추가)
                row = [
                    billing_month, branch_name, user_name, full_phone_number,  # 사용자 열 추가!
                    data.get('기본료', 0), data.get('시내통화료', 0), data.get('이동통화료', 0),
                    data.get('070통화료', 0), data.get('정보통화료', 0), data.get('부가서비스료', 0),
                    data.get('사용요금계', 0), data.get('할인액', 0), data.get('부가세', 0), data.get('최종합계', 0)
                ]
                rows_to_append.append(row)
            
            # 구글 시트에 배치별로 추가 (API 제한 해결)
            if rows_to_append:
                import time
                
                # 배치 크기 설정 (한번에 최대 20행씩 업로드)
                BATCH_SIZE = 20
                DELAY_SECONDS = 2  # 배치 간 2초 대기
                
                total_rows = len(rows_to_append)
                uploaded_count = 0
                
                print(f"총 {total_rows}개의 행을 배치별로 업로드 시작... (배치크기: {BATCH_SIZE})")
                
                # 배치별로 나누어 업로드
                for i in range(0, total_rows, BATCH_SIZE):
                    batch = rows_to_append[i:i + BATCH_SIZE]
                    batch_num = (i // BATCH_SIZE) + 1
                    
                    try:
                        self.data_ws.append_rows(batch, value_input_option='USER_ENTERED')
                        uploaded_count += len(batch)
                        print(f"배치 {batch_num}: {len(batch)}개 행 업로드 완료 ({uploaded_count}/{total_rows})")
                        
                        # 마지막 배치가 아니면 대기
                        if i + BATCH_SIZE < total_rows:
                            time.sleep(DELAY_SECONDS)
                            
                    except Exception as e:
                        print(f"배치 {batch_num} 업로드 실패: {e}")
                        # 재시도 로직
                        time.sleep(10)
                        try:
                            self.data_ws.append_rows(batch, value_input_option='USER_ENTERED')
                            uploaded_count += len(batch)
                            print(f"배치 {batch_num} 재시도 성공!")
                        except Exception as retry_e:
                            print(f"배치 {batch_num} 재시도도 실패: {retry_e}")
                            continue
                
                return {
                    "success": True, 
                    "rows_added": uploaded_count,
                    "overwritten": overwrite and has_duplicates,
                    "duplicates_removed": len(duplicates) if overwrite and has_duplicates else 0
                }
            
            return {"success": False, "message": "추가할 데이터가 없습니다"}
            
        except Exception as e:
            print(f"데이터 업데이트 실패: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

dashboard = PhoneBillingDashboard()

# ==================== PDF 처리 함수 ====================

def get_billing_month(text):
    """텍스트에서 'YYYY년 MM월'을 찾아 'YYYY-MM' 형식으로 반환합니다."""
    match = re.search(r'(\d{4})년\s*(\d{2})월', text)
    if match:
        year, month = match.groups()
        return f"{year}-{month}"
    return "날짜모름"

def parse_invoice_data(text):
    """PDF 텍스트에서 청구 데이터를 파싱합니다. (개선된 버전)"""
    # 서비스 구분별로 블록을 나누기 (더 정확한 패턴)
    service_blocks = []
    
    # 다양한 서비스 구분 패턴들
    service_patterns = [
        r'유선전화\s*\(TL\)전국대표번호\(mig\)',
        r'유선전화\s*\(TL\)소호',
        r'유선전화\s*\(TL\)링크기본형\(가상\)',
        r'유선전화\s*\(TL\)링크기본형\(실선\)',
        r'유선전화\s*\(TL\)소호\(가상중계실\)',
        r'유선전화\s*\(TL\)착신과금\(mig\)',
        r'유선전화\s*\(TL\)웹팩스',
        r'유선전화\s*(?!\(TL\))',  # 일반 유선전화
    ]
    
    # 전체 텍스트를 서비스 블록으로 나누기
    split_pattern = '|'.join(service_patterns)
    blocks = re.split(f'({split_pattern})', text)
    
    parsed_data = []
    
    # 블록들을 순회하면서 처리
    for i in range(1, len(blocks), 2):  # 서비스명과 데이터가 번갈아 나타남
        if i + 1 < len(blocks):
            service_type = blocks[i].strip()
            block_content = blocks[i + 1]
            
            # 각 블록에서 개별 전화번호 항목들 추출
            phone_entries = extract_phone_entries_from_block(service_type, block_content)
            parsed_data.extend(phone_entries)
    
    return parsed_data

def extract_phone_entries_from_block(service_type, block_content):
    """서비스 블록 내에서 개별 전화번호 항목들을 추출"""
    entries = []
    
    # 전화번호별로 데이터를 나누기 (합계 기준으로 분리)
    # "합계 XXXXX원" 패턴으로 각 전화번호의 끝을 구분
    phone_sections = re.split(r'합계\s+[\d,]+\s*원', block_content)
    
    for section in phone_sections[:-1]:  # 마지막 섹션은 빈 내용이므로 제외
        entry = extract_single_phone_data(service_type, section)
        if entry:
            entries.append(entry)
    
    return entries

def extract_single_phone_data(service_type, section):
    """개별 전화번호 섹션에서 데이터 추출"""
    # 전화번호 패턴 매칭 (실제 PDF 형태에 맞게 개선)
    phone_number = None
    phone_patterns = [
        # 전국대표번호: **99-2593, **00-1631
        (r'\*\*(\d{2}-\d{4})', 'XXXX-{}'),
        # 070 번호: 070)**03-2573
        (r'070\)\*\*(\d{2}-\d{4})', '070-XX{}'),
        # 02 번호: 02)**35-6493  
        (r'02\)\*\*(\d{2}-\d{4})', '02-XX{}'),
        # 080 번호: 080)**0-7100
        (r'080\)\*\*(\d{1}-\d{4})', '080-XX{}'),
        # 일반 지역번호: 031)**12-3456 등
        (r'(\d{2,3})\)\*\*(\d{2}-\d{4})', '{}-XX{}'),
        # 4자리 번호: 1588)**12-3456 등
        (r'(\d{4})\)\*\*(\d{1,2}-\d{4})', '{}-XX{}'),
    ]
    
    for pattern, format_str in phone_patterns:
        match = re.search(pattern, section)
        if match:
            if '{}' in format_str and len(match.groups()) == 2:
                # 지역번호가 있는 경우
                area_code = match.group(1)
                suffix = match.group(2)
                phone_number = format_str.format(area_code, suffix)
            elif 'XXXX' in format_str:
                # 전국대표번호 등에서 앞부분이 완전 마스킹된 경우
                suffix = match.group(1)
                phone_number = format_str.format(suffix)
            else:
                # 고정 접두사가 있는 경우
                suffix = match.group(1)
                phone_number = format_str.format(suffix)
            break
    
    if not phone_number:
        return None
    
    def find_amount(patterns):
        """여러 패턴을 시도해서 금액을 찾습니다"""
        if isinstance(patterns, str):
            patterns = [patterns]
        
        for pattern in patterns:
            match = re.search(pattern, section)
            if match:
                return int(match.group(1).replace(',', ''))
        return 0
    
    # 서비스 타입에 따른 기본료 패턴 결정
    basic_fee_patterns = []
    if '전국대표번호' in service_type:
        basic_fee_patterns = [
            r'전국대표번호부가이용료\s+([\d,]+)',
            r'기본료\s+([\d,]+)'
        ]
    elif '웹팩스' in service_type:
        basic_fee_patterns = [
            r'웹팩스 기본료\s+([\d,]+)',
            r'기본료\s+([\d,]+)'
        ]
    else:
        basic_fee_patterns = [
            r'인터넷전화기본료\s+([\d,]+)',
            r'기본료\s+([\d,]+)'
        ]
    
    # 부가서비스료 패턴도 서비스별로 구분
    vas_fee_patterns = [
        r'부가서비스이용료\s+([\d,]+)',
        r'전국대표번호부가이용료\s+([\d,]+)',
        r'웹팩스 국내이용료\s+([\d,]+)',
        r'Biz ARS\s+([\d,]+)',
        r'착신과금 접속료\s+([\d,]+)',
        r'부가서비스료\s+([\d,]+)'
    ]
    
    data = {
        '전화번호': phone_number,
        '기본료': find_amount(basic_fee_patterns),
        '시내통화료': find_amount(r'시내통화료\s+([\d,]+)'),
        '이동통화료': find_amount(r'이동통화료\s+([\d,]+)'),
        '070통화료': find_amount([
            r'인터넷전화통화료\(070\)\s+([\d,]+)',
            r'국제통화료\s+([\d,]+)'
        ]),
        '정보통화료': find_amount(r'정보통화료\s+([\d,]+)'),
        '부가서비스료': find_amount(vas_fee_patterns),
        '사용요금계': find_amount([
            r'사용요금 계\s+([\d,]+)',
            r'사용요금계\s+([\d,]+)'
        ]),
        '할인액': find_amount([
            r'할인\s+-([\d,]+)',
            r'할인액\s+-([\d,]+)'
        ]),
        '부가세': find_amount([
            r'부가가치세\(세금\)\*\s+([\d,]+)',
            r'부가세\s+([\d,]+)'
        ]),
        '최종합계': find_amount([
            r'합계\s+([\d,]+)',
            r'최종합계\s+([\d,]+)'
        ])
    }
    
    return data

def read_pdf(file_path):
    """PDF 파일을 읽고 텍스트를 추출합니다."""
    try:
        with open(file_path, 'rb') as pdf_file:
            reader = pypdf.PdfReader(pdf_file)
            full_text = "".join(page.extract_text() for page in reader.pages)
            return full_text
    except Exception as e:
        print(f"PDF 읽기 에러: {e}")
        return None

def process_pdf(file_path):
    """PDF 파일을 처리하여 청구 데이터와 청구월을 반환합니다."""
    try:
        pdf_text = read_pdf(file_path)
        if not pdf_text:
            return None, None
        
        invoice_data = parse_invoice_data(pdf_text)
        billing_month = get_billing_month(pdf_text)
        
        # 디버깅 정보 출력
        print(f"PDF 파싱 결과:")
        print(f"   청구월: {billing_month}")
        print(f"   추출된 회선 수: {len(invoice_data)}")
        
        if invoice_data:
            print(f"   추출된 전화번호들:")
            for i, data in enumerate(invoice_data[:5], 1):  # 최대 5개만 출력
                print(f"     {i}. {data['전화번호']} (최종합계: {data['최종합계']:,}원)")
            if len(invoice_data) > 5:
                print(f"     ... 외 {len(invoice_data) - 5}개 더")
        
        return invoice_data, billing_month
    except Exception as e:
        print(f"PDF 처리 오류: {e}")
        return None, None

# ==================== 페이지 라우트 ====================

@app.route('/')
def index():
    return redirect('/dashboard')

@app.route('/dashboard')
def dashboard_page():
    return render_template('dashboard.html')

@app.route('/search')
def search_page():
    return render_template('search.html')

@app.route('/analytics')
def analytics_page():
    return render_template('analytics.html')

# ==================== 기존 API 엔드포인트 ====================

@app.route('/api/dashboard')
def get_dashboard_data():
    """대시보드 기본 데이터"""
    try:
        df = dashboard.get_all_data()
        
        if df.empty:
            return jsonify({"error": "데이터가 없습니다"})
        
        # 필터 파라미터 받기
        branch = request.args.get('branch', 'all')
        month = request.args.get('month', 'all')
        
        # 필터 적용
        filtered_df = df.copy()
        
        if branch != 'all':
            filtered_df = filtered_df[filtered_df['지점명'] == branch]
        
        if month != 'all':
            filtered_df = filtered_df[filtered_df['청구월'] == month]
        
        # 최신 월 데이터 추출
        latest_month = filtered_df['청구월'].max() if '청구월' in filtered_df.columns and not filtered_df.empty else "알 수 없음"
        
        # KPI 계산
        total_cost = filtered_df['최종합계'].sum() if '최종합계' in filtered_df.columns else 0
        active_lines = len(filtered_df) if not filtered_df.empty else 0
        # 기본료만 발생한 회선: 기본료 + 부가서비스료 = 사용요금계 (통화를 안 한 회선)
        basic_only_lines = len(filtered_df[(filtered_df['기본료'] + filtered_df['부가서비스료']) == filtered_df['사용요금계']]) if '사용요금계' in filtered_df.columns and '기본료' in filtered_df.columns and '부가서비스료' in filtered_df.columns else 0
        vas_fee = filtered_df['부가서비스료'].sum() if '부가서비스료' in filtered_df.columns else 0
        
        # 지점별 요금 상위 5개
        if '지점명' in filtered_df.columns and '최종합계' in filtered_df.columns and not filtered_df.empty:
            top_branches = filtered_df.groupby('지점명')['최종합계'].sum().sort_values(ascending=False).head(5)
            top_branches_data = [[branch, int(cost)] for branch, cost in top_branches.items()]
        else:
            top_branches_data = []
        
        # 월별 추이 데이터 (최근 6개월)
        monthly_trend_data = {"months": [], "totalCosts": []}
        if '청구월' in df.columns and '최종합계' in df.columns and not df.empty:
            # 지점 필터만 적용하고 월별 추이는 전체 기간 보여주기
            trend_df = df.copy()
            if branch != 'all':
                trend_df = trend_df[trend_df['지점명'] == branch]
            
            monthly_totals = trend_df.groupby('청구월')['최종합계'].sum().sort_index()
            monthly_trend_data = {
                "months": monthly_totals.index.tolist()[-6:],  # 최근 6개월
                "totalCosts": [int(cost) for cost in monthly_totals.values[-6:]]
            }
        
        # 문제 회선 (기본료만 발생하는 회선): 기본료 + 부가서비스료 = 사용요금계
        if '사용요금계' in filtered_df.columns and '기본료' in filtered_df.columns and '부가서비스료' in filtered_df.columns:
            problem_lines = filtered_df[(filtered_df['기본료'] + filtered_df['부가서비스료']) == filtered_df['사용요금계']].sort_values('지점명')
            problem_lines_data = []
            for _, row in problem_lines.iterrows():
                problem_lines_data.append([
                    row.get('지점명', ''),
                    row.get('전화번호', ''),
                    int(row.get('사용요금계', 0)),
                    int(row.get('할인액', 0)),
                    int(row.get('부가세', 0)),
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
            "monthlyTrend": monthly_trend_data,
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
        
        # 결과 변환 (filter_data API)
        result = []
        for _, row in filtered_df.iterrows():
            result.append({
                "청구월": row.get('청구월', ''),
                "지점명": row.get('지점명', ''),
                "사용자": row.get('사용자', ''),  # 사용자 정보 추가
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

@app.route('/api/users')
def get_users():
    """사용자 목록 반환"""
    try:
        df = dashboard.get_all_data()
        users = sorted(df['사용자'].dropna().unique().tolist()) if '사용자' in df.columns else []
        # 빈 값 제거
        users = [user for user in users if user and user.strip()]
        return jsonify(users)
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
        user = request.args.get('user', '').strip()  # 사용자 필터 추가
        phone_type = request.args.get('type', '').strip()
        search_text = request.args.get('q', '').strip()  # 통합검색
        phone_search = request.args.get('phone', '').strip()  # 전화번호 검색
        
        print(f"검색 파라미터: branch={branch}, month={month}, user={user}, type={phone_type}, search={search_text}, phone={phone_search}")
        
        # 필터 적용
        filtered_df = df.copy()
        
        # 지점 필터
        if branch and branch != 'all':
            filtered_df = filtered_df[filtered_df['지점명'] == branch]
        
        # 월 필터
        if month and month != 'all':
            filtered_df = filtered_df[filtered_df['청구월'] == month]
        
        # 사용자 필터 추가
        if user and user != 'all':
            filtered_df = filtered_df[filtered_df['사용자'] == user]
        
        # 전화 타입 필터
        if phone_type == 'basic':
            # 기본료만 발생하는 회선: 기본료 + 부가서비스료 = 사용요금계
            filtered_df = filtered_df[(filtered_df['기본료'] + filtered_df['부가서비스료']) == filtered_df['사용요금계']]
        elif phone_type == 'vas':
            # 부가서비스 사용 회선
            filtered_df = filtered_df[filtered_df['부가서비스료'] > 0]
        
        # 통합검색 (지점명, 전화번호, 사용자, 모든 텍스트 컬럼)
        if search_text:
            mask = (
                filtered_df['지점명'].str.contains(search_text, na=False, case=False) |
                filtered_df['전화번호'].str.contains(search_text, na=False, case=False) |
                filtered_df['사용자'].str.contains(search_text, na=False, case=False) |  # 사용자도 검색 대상에 추가
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
        
        # 결과 변환 (search_data API)
        result = []
        for _, row in filtered_df.iterrows():
            result.append({
                "청구월": row.get('청구월', ''),
                "지점명": row.get('지점명', ''),
                "사용자": row.get('사용자', ''),  # 사용자 정보 추가
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
                        # 중복 데이터 발견 - 상세 정보 제공
                        duplicate_details = []
                        for dup in update_result.get("duplicates", []):
                            new_data = dup['new']
                            existing_data = dup['existing']
                            duplicate_details.append({
                                "phone": new_data['전화번호'],
                                "amount": new_data['최종합계'],
                                "existing_branch": existing_data.get('지점명', '알 수 없음')
                            })
                        
                        return jsonify({
                            "duplicate": True,
                            "billing_month": billing_month,
                            "message": f"{billing_month} 청구월에서 {len(duplicate_details)}건의 중복 발견",
                            "existing_count": len(duplicate_details),
                            "new_data_count": len(invoice_data),
                            "duplicate_details": duplicate_details[:5]  # 최대 5개까지만 표시
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

# ==================== 분석 및 리포트 API ====================

@app.route('/api/analytics/comprehensive')
def get_comprehensive_analytics():
    """종합 분석 데이터"""
    try:
        period = int(request.args.get('period', 6))  # 기본 6개월
        branch = request.args.get('branch', 'all')
        
        df = dashboard.get_all_data()
        if df.empty:
            return jsonify({"error": "분석할 데이터가 없습니다"})
        
        # 날짜 필터링
        df['청구월_date'] = pd.to_datetime(df['청구월'], format='%Y-%m', errors='coerce')
        recent_date = df['청구월_date'].max()
        start_date = recent_date - pd.DateOffset(months=period-1)
        filtered_df = df[df['청구월_date'] >= start_date]
        
        # 지점 필터링
        if branch != 'all':
            filtered_df = filtered_df[filtered_df['지점명'] == branch]
        
        # 월별 비교 데이터
        monthly_comparison = generate_monthly_comparison(filtered_df)
        
        # 트렌드 분석
        trends = generate_trend_analysis(filtered_df)
        
        # 이상 사용 감지
        anomalies = detect_anomalies(filtered_df)
        
        # 비용 절감 제안
        suggestions = generate_cost_saving_suggestions(filtered_df)
        
        return jsonify({
            "monthlyComparison": monthly_comparison,
            "trends": trends,
            "anomalies": anomalies,
            "suggestions": suggestions
        })
        
    except Exception as e:
        print(f"종합 분석 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)})

@app.route('/api/analytics/branch-details')
def get_branch_details():
    """지점별 상세 분석"""
    try:
        branch = request.args.get('branch', 'all')
        
        df = dashboard.get_all_data()
        if df.empty:
            return jsonify({"error": "분석할 데이터가 없습니다"})
        
        if branch == 'all':
            # 전체 지점 요약
            branches = []
            for branch_name in df['지점명'].unique():
                branch_df = df[df['지점명'] == branch_name]
                branch_data = generate_branch_summary(branch_df, branch_name)
                branches.append(branch_data)
            
            return jsonify({"branches": branches})
        else:
            # 특정 지점 상세
            branch_df = df[df['지점명'] == branch]
            if branch_df.empty:
                return jsonify({"error": f"{branch} 지점의 데이터가 없습니다"})
            
            detailed_data = generate_detailed_branch_report(branch_df, branch)
            return jsonify(detailed_data)
        
    except Exception as e:
        print(f"지점별 상세 분석 오류: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/export/excel')
def export_excel():
    """전체 데이터 Excel 내보내기"""
    try:
        df = dashboard.get_all_data()
        if df.empty:
            return jsonify({"error": "내보낼 데이터가 없습니다"})
        
        # Excel 파일 생성
        excel_file = create_excel_report(df, "전체_데이터")
        
        return send_file(
            excel_file,
            as_attachment=True,
            download_name=f'전화요금_전체데이터_{datetime.now().strftime("%Y%m%d")}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        print(f"Excel 내보내기 오류: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/export/excel-filtered')
def export_filtered_excel():
    """필터링된 데이터 Excel 내보내기"""
    try:
        # 검색 파라미터와 동일한 필터링 로직 사용
        df = dashboard.get_all_data()
        if df.empty:
            return jsonify({"error": "내보낼 데이터가 없습니다"})
        
        # 필터 적용
        branch = request.args.get('branch', '').strip()
        month = request.args.get('month', '').strip()
        user = request.args.get('user', '').strip()  # 사용자 필터 추가
        phone_type = request.args.get('type', '').strip()
        search_text = request.args.get('q', '').strip()
        phone_search = request.args.get('phone', '').strip()
        
        filtered_df = df.copy()
        
        if branch and branch != 'all':
            filtered_df = filtered_df[filtered_df['지점명'] == branch]
        
        if month and month != 'all':
            filtered_df = filtered_df[filtered_df['청구월'] == month]
        
        if user and user != 'all':
            filtered_df = filtered_df[filtered_df['사용자'] == user]
        
        if phone_type == 'basic':
            # 기본료만 발생하는 회선: 기본료 + 부가서비스료 = 사용요금계
            filtered_df = filtered_df[(filtered_df['기본료'] + filtered_df['부가서비스료']) == filtered_df['사용요금계']]
        elif phone_type == 'vas':
            filtered_df = filtered_df[filtered_df['부가서비스료'] > 0]
        
        if search_text:
            mask = (
                filtered_df['지점명'].str.contains(search_text, na=False, case=False) |
                filtered_df['전화번호'].str.contains(search_text, na=False, case=False) |
                filtered_df['사용자'].str.contains(search_text, na=False, case=False) |  # 사용자도 검색 대상에 추가
                filtered_df['청구월'].str.contains(search_text, na=False, case=False)
            )
            filtered_df = filtered_df[mask]
        
        if phone_search:
            filtered_df = filtered_df[filtered_df['전화번호'].str.contains(phone_search, na=False)]
        
        # Excel 파일 생성
        excel_file = create_excel_report(filtered_df, "필터_검색결과")
        
        return send_file(
            excel_file,
            as_attachment=True,
            download_name=f'필터_검색결과_{datetime.now().strftime("%Y%m%d")}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        print(f"필터 Excel 내보내기 오류: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/analytics/monthly-report')
def generate_monthly_report_api():
    """월간 리포트 PDF 생성"""
    try:
        period = int(request.args.get('period', 6))
        branch = request.args.get('branch', 'all')
        
        df = dashboard.get_all_data()
        if df.empty:
            return jsonify({"error": "리포트 생성할 데이터가 없습니다"})
        
        # 리포트 데이터 준비
        report_data = prepare_monthly_report_data(df, period, branch)
        
        # PDF 생성
        pdf_file = create_pdf_report(report_data, "월간_분석_리포트")
        
        return send_file(
            pdf_file,
            as_attachment=True,
            download_name=f'월간_분석_리포트_{datetime.now().strftime("%Y%m%d")}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"월간 리포트 생성 오류: {e}")
        return jsonify({"error": str(e)})

@app.route('/api/analytics/branch-report')
def generate_branch_report_api():
    """지점별 리포트 Excel 생성"""
    try:
        branch = request.args.get('branch')
        if not branch or branch == 'all':
            return jsonify({"error": "특정 지점을 선택해주세요"})
        
        df = dashboard.get_all_data()
        branch_df = df[df['지점명'] == branch]
        
        if branch_df.empty:
            return jsonify({"error": f"{branch} 지점의 데이터가 없습니다"})
        
        # 지점별 상세 리포트 생성
        excel_file = create_branch_excel_report(branch_df, branch)
        
        return send_file(
            excel_file,
            as_attachment=True,
            download_name=f'{branch}_상세리포트_{datetime.now().strftime("%Y%m%d")}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        print(f"지점 리포트 생성 오류: {e}")
        return jsonify({"error": str(e)})

# ==================== 분석 로직 함수들 ====================

def generate_monthly_comparison(df):
    """월별 비교 데이터 생성"""
    try:
        if df.empty:
            return {"months": [], "totalCosts": [], "averageCosts": [], "lineCounts": []}
        
        # 월별 그룹화
        monthly_stats = df.groupby('청구월').agg({
            '최종합계': ['sum', 'mean', 'count']
        }).round(0)
        
        monthly_stats.columns = ['총요금', '평균요금', '회선수']
        monthly_stats = monthly_stats.sort_index()
        
        return {
            "months": monthly_stats.index.tolist(),
            "totalCosts": monthly_stats['총요금'].astype(int).tolist(),
            "averageCosts": monthly_stats['평균요금'].astype(int).tolist(),
            "lineCounts": monthly_stats['회선수'].astype(int).tolist()
        }
    except Exception as e:
        print(f"월별 비교 데이터 생성 오류: {e}")
        return {"months": [], "totalCosts": [], "averageCosts": [], "lineCounts": []}

def generate_trend_analysis(df):
    """트렌드 분석"""
    try:
        if df.empty:
            return []
        
        trends = []
        
        # 지점별 트렌드 분석
        for branch in df['지점명'].unique():
            branch_df = df[df['지점명'] == branch]
            monthly_totals = branch_df.groupby('청구월')['최종합계'].sum().sort_index()
            
            if len(monthly_totals) < 2:
                continue
            
            # 최근 3개월 vs 이전 3개월 비교
            if len(monthly_totals) >= 6:
                recent_avg = monthly_totals.tail(3).mean()
                previous_avg = monthly_totals.iloc[-6:-3].mean()
            else:
                recent_avg = monthly_totals.tail(1).iloc[0]
                previous_avg = monthly_totals.head(1).iloc[0]
            
            if previous_avg > 0:
                change_percent = ((recent_avg - previous_avg) / previous_avg * 100)
                
                direction = 'up' if change_percent > 5 else 'down' if change_percent < -5 else 'stable'
                
                trend_description = f"최근 요금이 {'증가' if change_percent > 0 else '감소' if change_percent < 0 else '안정'}하고 있습니다"
                
                trends.append({
                    "branch": branch,
                    "direction": direction,
                    "changePercent": f"{abs(change_percent):.1f}",
                    "period": f"최근 {min(len(monthly_totals), 3)}개월",
                    "description": trend_description
                })
        
        return trends[:10]  # 상위 10개만 반환
        
    except Exception as e:
        print(f"트렌드 분석 오류: {e}")
        return []

def detect_anomalies(df):
    """이상 사용 감지"""
    try:
        if df.empty:
            return []
        
        anomalies = []
        
        # 전화번호별 이상 사용 감지
        for phone in df['전화번호'].unique():
            phone_df = df[df['전화번호'] == phone].sort_values('청구월')
            
            if len(phone_df) < 3:  # 최소 3개월 데이터 필요
                continue
            
            amounts = phone_df['최종합계'].values
            
            # 최근 달과 이전 평균 비교
            recent_amount = amounts[-1]
            historical_avg = amounts[:-1].mean()
            
            if historical_avg > 0:
                increase_percent = ((recent_amount - historical_avg) / historical_avg * 100)
                
                # 100% 이상 증가한 경우 이상으로 판단
                if increase_percent > 100:
                    branch = phone_df.iloc[-1]['지점명']
                    anomalies.append({
                        "branch": branch,
                        "phone": phone,
                        "currentAmount": int(recent_amount),
                        "previousAverage": int(historical_avg),
                        "increasePercent": f"{increase_percent:.0f}",
                        "description": f"평소 대비 {increase_percent:.0f}% 증가하여 이상 사용으로 감지되었습니다"
                    })
        
        return sorted(anomalies, key=lambda x: float(x['increasePercent']), reverse=True)[:10]
        
    except Exception as e:
        print(f"이상 사용 감지 오류: {e}")
        return []

def generate_cost_saving_suggestions(df):
    """비용 절감 제안"""
    try:
        if df.empty:
            return []
        
        suggestions = []
        
        # 1. 기본료만 발생하는 회선 (3개월 연속)
        basic_only_lines = []
        for phone in df['전화번호'].unique():
            phone_df = df[df['전화번호'] == phone].sort_values('청구월').tail(3)
            if len(phone_df) >= 3 and all((phone_df['기본료'] + phone_df['부가서비스료']) == phone_df['사용요금계']):
                basic_only_lines.append(phone)
        
        if basic_only_lines:
            avg_basic_fee = df[df['전화번호'].isin(basic_only_lines)]['기본료'].mean()
            suggestions.append({
                "title": "미사용 회선 해지",
                "description": f"3개월 연속 기본료만 발생하는 {len(basic_only_lines)}개 회선을 해지하여 비용 절감",
                "targetCount": len(basic_only_lines),
                "potentialSavings": int(avg_basic_fee * len(basic_only_lines)),
                "priority": "높음"
            })
        
        # 2. 부가서비스 과다 사용 회선
        high_vas_lines = df[df['부가서비스료'] > df['부가서비스료'].quantile(0.9)]
        if not high_vas_lines.empty:
            avg_vas_saving = high_vas_lines['부가서비스료'].mean() * 0.3  # 30% 절감 가정
            suggestions.append({
                "title": "부가서비스 최적화",
                "description": f"부가서비스 사용량이 많은 회선의 서비스 재검토",
                "targetCount": len(high_vas_lines),
                "potentialSavings": int(avg_vas_saving * len(high_vas_lines)),
                "priority": "중간"
            })
        
        # 3. 요금제 최적화
        high_cost_lines = df[df['최종합계'] > df['최종합계'].quantile(0.95)]
        if not high_cost_lines.empty:
            avg_optimization_saving = high_cost_lines['최종합계'].mean() * 0.15  # 15% 절감 가정
            suggestions.append({
                "title": "요금제 최적화",
                "description": f"고액 요금 발생 회선의 요금제 변경 검토",
                "targetCount": len(high_cost_lines),
                "potentialSavings": int(avg_optimization_saving * len(high_cost_lines)),
                "priority": "중간"
            })
        
        return suggestions
        
    except Exception as e:
        print(f"비용 절감 제안 생성 오류: {e}")
        return []

def generate_branch_summary(branch_df, branch_name):
    """지점 요약 데이터 생성"""
    try:
        total_cost = branch_df['최종합계'].sum()
        line_count = len(branch_df)
        average_cost = total_cost / line_count if line_count > 0 else 0
        
        # 트렌드 계산 (최근 2개월 비교)
        monthly_totals = branch_df.groupby('청구월')['최종합계'].sum().sort_index()
        
        if len(monthly_totals) >= 2:
            recent = monthly_totals.iloc[-1]
            previous = monthly_totals.iloc[-2]
            change_percent = ((recent - previous) / previous * 100) if previous > 0 else 0
            direction = 'up' if change_percent > 0 else 'down' if change_percent < 0 else 'stable'
        else:
            change_percent = 0
            direction = 'stable'
        
        return {
            "name": branch_name,
            "totalCost": int(total_cost),
            "lineCount": line_count,
            "averageCost": int(average_cost),
            "trend": {
                "direction": direction,
                "changePercent": f"{abs(change_percent):.1f}"
            }
        }
    except Exception as e:
        print(f"지점 요약 생성 오류: {e}")
        return {"name": branch_name, "totalCost": 0, "lineCount": 0, "averageCost": 0, "trend": {"direction": "stable", "changePercent": "0"}}

def generate_detailed_branch_report(branch_df, branch_name):
    """상세 지점 리포트 데이터 생성"""
    try:
        total_lines = len(branch_df['전화번호'].unique())
        monthly_average = branch_df.groupby('청구월')['최종합계'].sum().mean()
        
        # 최고 사용 월
        monthly_totals = branch_df.groupby('청구월')['최종합계'].sum()
        peak_month = monthly_totals.idxmax()
        peak_amount = monthly_totals.max()
        
        # 기본료만 발생 회선
        basic_only_lines = len(branch_df[(branch_df['기본료'] + branch_df['부가서비스료']) == branch_df['사용요금계']])
        
        # 회선별 상세
        phone_details = []
        for phone in branch_df['전화번호'].unique():
            phone_data = branch_df[branch_df['전화번호'] == phone]
            avg_cost = phone_data['최종합계'].mean()
            phone_details.append({
                "number": phone,
                "averageCost": int(avg_cost)
            })
        
        phone_details.sort(key=lambda x: x['averageCost'], reverse=True)
        
        return {
            "branchName": branch_name,
            "totalLines": total_lines,
            "monthlyAverage": int(monthly_average),
            "peakMonth": peak_month,
            "peakAmount": int(peak_amount),
            "basicOnlyLines": basic_only_lines,
            "phoneDetails": phone_details[:20]  # 상위 20개만
        }
    except Exception as e:
        print(f"상세 지점 리포트 생성 오류: {e}")
        return {"branchName": branch_name, "error": str(e)}

# ==================== Excel/PDF 생성 함수들 ====================

def create_excel_report(df, report_name):
    """Excel 리포트 생성"""
    try:
        # 메모리에서 Excel 파일 생성
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 메인 데이터 시트
            df_export = df.copy()
            # 불필요한 컬럼 제거
            if '청구월_date' in df_export.columns:
                df_export = df_export.drop('청구월_date', axis=1)
            
            df_export.to_excel(writer, sheet_name='데이터', index=False)
            
            # 요약 시트
            summary_data = []
            summary_data.append(['항목', '값'])
            summary_data.append(['총 레코드 수', len(df)])
            summary_data.append(['총 요금', f"{df['최종합계'].sum():,} 원"])
            summary_data.append(['평균 요금', f"{df['최종합계'].mean():.0f} 원"])
            summary_data.append(['총 회선 수', df['전화번호'].nunique()])
            summary_data.append(['지점 수', df['지점명'].nunique()])
            
            # 기본료만 발생 회선
            basic_only = len(df[df['사용요금계'] == df['기본료']])
            summary_data.append(['기본료만 발생 회선', f"{basic_only} 개"])
            
            summary_df = pd.DataFrame(summary_data[1:], columns=summary_data[0])
            summary_df.to_excel(writer, sheet_name='요약', index=False)
            
            # 지점별 통계
            if not df.empty:
                branch_stats = df.groupby('지점명').agg({
                    '최종합계': ['sum', 'mean', 'count'],
                    '부가서비스료': 'sum'
                }).round(0)
                
                branch_stats.columns = ['총요금', '평균요금', '회선수', '부가서비스료합계']
                branch_stats = branch_stats.sort_values('총요금', ascending=False)
                branch_stats.to_excel(writer, sheet_name='지점별_통계')
        
        output.seek(0)
        return output
        
    except Exception as e:
        print(f"Excel 생성 오류: {e}")
        raise

def create_branch_excel_report(branch_df, branch_name):
    """지점별 상세 Excel 리포트 생성"""
    try:
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 상세 데이터
            df_export = branch_df.copy()
            if '청구월_date' in df_export.columns:
                df_export = df_export.drop('청구월_date', axis=1)
            
            df_export.to_excel(writer, sheet_name=f'{branch_name}_상세데이터', index=False)
            
            # 월별 통계
            monthly_stats = branch_df.groupby('청구월').agg({
                '최종합계': ['sum', 'mean', 'count'],
                '부가서비스료': 'sum',
                '기본료': 'sum'
            }).round(0)
            
            monthly_stats.columns = ['총요금', '평균요금', '회선수', '부가서비스료', '기본료합계']
            monthly_stats.to_excel(writer, sheet_name='월별_통계')
            
            # 회선별 통계
            phone_stats = branch_df.groupby('전화번호').agg({
                '최종합계': ['sum', 'mean', 'count'],
                '부가서비스료': 'sum'
            }).round(0)
            
            phone_stats.columns = ['총요금', '평균요금', '청구횟수', '부가서비스료합계']
            phone_stats = phone_stats.sort_values('총요금', ascending=False)
            phone_stats.to_excel(writer, sheet_name='회선별_통계')
        
        output.seek(0)
        return output
        
    except Exception as e:
        print(f"지점 Excel 리포트 생성 오류: {e}")
        raise

def create_pdf_report(report_data, report_name):
    """PDF 리포트 생성 (기본 구조)"""
    try:
        # 간단한 텍스트 기반 PDF 생성 (향후 개선 가능)
        output = io.BytesIO()
        
        # 현재는 기본적인 텍스트 파일로 생성
        # 실제 환경에서는 reportlab 등을 사용하여 PDF 생성
        content = f"""
{report_name}
생성일: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

=== 분석 리포트 ===

이 리포트는 전화요금 대시보드에서 생성되었습니다.

상세한 분석 결과는 웹 대시보드에서 확인해주세요.
        """
        
        # 임시로 텍스트 파일로 반환 (PDF 라이브러리 없이)
        output.write(content.encode('utf-8'))
        output.seek(0)
        
        return output
        
    except Exception as e:
        print(f"PDF 생성 오류: {e}")
        raise

def prepare_monthly_report_data(df, period, branch):
    """월간 리포트 데이터 준비"""
    try:
        # 기본적인 통계 데이터 준비
        report_data = {
            "period": period,
            "branch": branch,
            "total_records": len(df),
            "total_cost": df['최종합계'].sum(),
            "average_cost": df['최종합계'].mean(),
            "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return report_data
        
    except Exception as e:
        print(f"월간 리포트 데이터 준비 오류: {e}")
        return {}

# ==================== PDF 처리 함수 ====================

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

# ==================== 리포트 생성 함수들 ====================

def create_excel_report(df, report_name):
    """Excel 리포트 생성"""
    try:
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 데이터 시트
            df.to_excel(writer, sheet_name='데이터', index=False)
            
            # 요약 시트
            if not df.empty:
                summary_data = {
                    '항목': ['총 요금', '총 회선수', '기본료만 발생 회선', '평균 요금'],
                    '값': [
                        df['최종합계'].sum() if '최종합계' in df.columns else 0,
                        len(df),
                        len(df[(df['기본료'] + df['부가서비스료']) == df['사용요금계']]) if '사용요금계' in df.columns and '기본료' in df.columns and '부가서비스료' in df.columns else 0,
                        df['최종합계'].mean() if '최종합계' in df.columns and len(df) > 0 else 0
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='요약', index=False)
        
        output.seek(0)
        return output
        
    except Exception as e:
        print(f"Excel 리포트 생성 오류: {e}")
        return None

def create_branch_excel_report(branch_df, branch_name):
    """지점별 상세 Excel 리포트 생성"""
    try:
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 상세 데이터
            branch_df.to_excel(writer, sheet_name=f'{branch_name}_상세', index=False)
            
            # 월별 요약
            if not branch_df.empty and '청구월' in branch_df.columns:
                monthly_summary = branch_df.groupby('청구월').agg({
                    '최종합계': ['sum', 'mean', 'count']
                }).round(0)
                monthly_summary.columns = ['총요금', '평균요금', '회선수']
                monthly_summary.to_excel(writer, sheet_name='월별요약')
        
        output.seek(0)
        return output
        
    except Exception as e:
        print(f"지점별 Excel 리포트 생성 오류: {e}")
        return None

def create_pdf_report(report_data, report_name):
    """PDF 리포트 생성 (기본 구현)"""
    # 실제 구현에서는 reportlab 등을 사용
    output = io.BytesIO()
    output.write(b"PDF report placeholder")
    output.seek(0)
    return output

def prepare_monthly_report_data(df, period, branch):
    """월간 리포트 데이터 준비"""
    # 리포트 데이터 준비 로직
    return {"data": "월간 리포트 데이터"}

def generate_detailed_branch_report(branch_df, branch):
    """지점별 상세 리포트 생성"""
    # 상세 리포트 로직
    return {"branch": branch, "data": "상세 리포트"}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
