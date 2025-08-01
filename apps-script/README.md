# 📱 Google Apps Script 배포 가이드

## 🚀 Google Apps Script로 웹앱 배포하기

### 1단계: Google Apps Script 프로젝트 생성

1. **https://script.google.com** 접속
2. **"새 프로젝트"** 클릭
3. **프로젝트 이름**: "전화요금 대시보드"로 변경

### 2단계: 코드 복사

#### 📄 Code.gs 파일
1. 기본 `Code.gs` 파일에 `apps-script/Code.gs` 내용 전체 복사
2. **중요**: `getSpreadsheetUrl()` 함수에서 구글 시트 URL을 실제 URL로 변경
   ```javascript
   function getSpreadsheetUrl() {
     return 'https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit';
   }
   ```

#### 🌐 index.html 파일 추가
1. **"파일" → "HTML" → "새 파일"** 클릭
2. 파일명: `index` (자동으로 .html 확장자 추가됨)
3. `apps-script/index.html` 내용 전체 복사

### 3단계: 구글 시트 URL 설정

**구글 시트 URL 찾는 방법:**
1. 구글 시트 열기
2. 브라우저 주소창에서 URL 복사
3. `Code.gs`의 `getSpreadsheetUrl()` 함수에 붙여넣기

**예시:**
```javascript
function getSpreadsheetUrl() {
  return 'https://docs.google.com/spreadsheets/d/1SULlqe7hiRHu7mFLcCUqkkc8BJ1vsnxPrMkIE8GCUU8/edit';
}
```

### 4단계: 권한 설정

1. **"서비스"** 메뉴 클릭
2. **"Google Sheets API"** 추가
3. **"Google Drive API"** 추가 (필요시)

### 5단계: 웹앱 배포

1. **"배포" → "새 배포"** 클릭
2. **유형 선택**: "웹 앱" 선택
3. **설정**:
   - **설명**: "전화요금 대시보드 v1.0"
   - **다음 사용자로 실행**: 나
   - **액세스 권한**: "모든 사용자" (조직 내부만 원하면 "조직 내 사용자")
4. **"배포"** 클릭
5. **권한 승인**: "액세스 승인" → Google 계정으로 로그인 → "허용"

### 6단계: 웹앱 URL 받기

배포 완료 후 **웹앱 URL**이 제공됩니다:
```
https://script.google.com/macros/s/AKfycby.../exec
```

## 🌐 사용 방법

### ✅ 완전한 기능 (무료 영구 사용!)

1. **웹앱 URL 접속** (어디서든 가능)
2. **PDF 텍스트 붙여넣기**: PDF에서 전체 텍스트 복사 → 붙여넣기
3. **"텍스트 처리 및 시트 업데이트"** 클릭
4. **실시간 조회**: 필터링, 검색, 차트 모든 기능 사용

### 📊 주요 기능들

- ✅ **PDF 텍스트 자동 처리**
- ✅ **구글 시트 실시간 업데이트**
- ✅ **지점별/월별 필터링**
- ✅ **전화번호 검색**
- ✅ **KPI 대시보드**
- ✅ **차트 시각화**

## 💰 비용 분석

### 🆓 Google Apps Script 무료 한도

| 기능 | 무료 한도 | 예상 사용량 |
|------|----------|------------|
| 웹앱 접속 | **무제한** | ✅ 무제한 사용 |
| 스크립트 실행 | 일일 6시간 | 월 몇 번 × 몇 초 = 충분 |
| 구글 시트 연동 | **무제한** | ✅ 데이터 무제한 |

### 💡 예상 사용 패턴
- **월 1-2회 PDF 업로드**: 총 실행시간 < 1분
- **일일 대시보드 조회**: 무제한 무료
- **데이터 누적**: 구글 시트 15GB까지 무료

→ **결론: 영구 무료 사용 가능!** 🎉

## 🔧 업데이트 방법

### 코드 수정시:
1. Apps Script 에디터에서 코드 수정
2. **저장** (Ctrl+S)
3. **새 배포** 또는 **배포 관리**에서 기존 배포 업데이트

### URL 변경 없이 업데이트:
1. **"배포" → "배포 관리"**
2. 기존 배포 선택 → **"새 버전"**
3. URL은 그대로 유지됨

## 🛠️ 문제 해결

### 권한 오류시:
1. **실행 로그 확인**: "실행" → "실행 기록"
2. 구글 시트 공유 권한 확인
3. Google Sheets API 활성화 확인

### 데이터 안 나올시:
1. 구글 시트 URL 정확한지 확인
2. 시트 이름 정확한지 확인:
   - "전화번호 마스터"
   - "청구내역 원본"

### PDF 처리 안될시:
1. 전체 텍스트가 정확히 복사되었는지 확인
2. "유선전화" 키워드가 포함되어 있는지 확인

## 📱 모바일 접속

Apps Script 웹앱은 **모바일에서도 완벽하게 작동**합니다:
- 📱 스마트폰 브라우저에서 접속
- 💻 태블릿에서 접속
- 🌐 어떤 기기든 URL만 있으면 접속 가능

## 🔒 보안

- ✅ **Google 계정 인증** 자동 적용
- ✅ **HTTPS 자동 제공**
- ✅ **구글 인프라** 사용으로 안전
- ✅ **데이터는 구글 시트에만** 저장

## 🎯 최종 결과

✅ **영구 무료 웹앱**: 언제든지 어디서든 접속  
✅ **PDF 자동 처리**: 텍스트 붙여넣기만으로 처리  
✅ **실시간 대시보드**: KPI, 차트, 필터링 모든 기능  
✅ **모바일 지원**: 스마트폰에서도 완벽 작동  
✅ **무제한 데이터**: 구글 시트로 계속 쌓기  

이제 **완전한 클라우드 전화요금 관리 시스템**이 완성되었습니다! 🚀
