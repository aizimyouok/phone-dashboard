// ===============================
// 전화요금 대시보드 - Google Apps Script
// ===============================

const SPREADSHEET_NAME = 'CFC 전화번호 현황 및 요금';
const MASTER_SHEET_NAME = '전화번호 마스터';
const DATA_SHEET_NAME = '청구내역 원본';

// 웹앱 진입점
function doGet() {
  return HtmlService.createTemplateFromFile('index')
    .evaluate()
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

// HTML 파일 include 기능
function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}

// ===============================
// API 함수들
// ===============================

// 대시보드 데이터 가져오기
function getDashboardData() {
  try {
    const ss = SpreadsheetApp.openByUrl(getSpreadsheetUrl());
    const dataSheet = ss.getSheetByName(DATA_SHEET_NAME);
    
    if (!dataSheet) {
      throw new Error(`시트 '${DATA_SHEET_NAME}'를 찾을 수 없습니다.`);
    }
    
    const data = dataSheet.getDataRange().getValues();
    if (data.length <= 1) {
      return {
        kpi: {
          latestMonth: "데이터 없음",
          totalCost: 0,
          activeLines: 0,
          basicFeeOnlyLines: 0,
          totalVasFee: 0
        },
        top5Branches: [],
        problemLines: []
      };
    }
    
    const headers = data[0];
    const rows = data.slice(1);
    
    // 컬럼 인덱스 찾기
    const getColumnIndex = (name) => headers.findIndex(h => h === name);
    
    const monthIdx = getColumnIndex('청구월');
    const branchIdx = getColumnIndex('지점명');
    const phoneIdx = getColumnIndex('전화번호');
    const totalIdx = getColumnIndex('최종합계');
    const basicIdx = getColumnIndex('기본료');
    const usageIdx = getColumnIndex('사용요금계');
    const vasIdx = getColumnIndex('부가서비스료');
    
    // KPI 계산
    const latestMonth = rows.length > 0 ? rows[rows.length - 1][monthIdx] : "데이터 없음";
    const totalCost = rows.reduce((sum, row) => sum + (parseFloat(row[totalIdx]) || 0), 0);
    const activeLines = rows.length;
    
    // 기본료만 발생한 회선: 사용요금계 = 기본료
    const basicFeeOnlyLines = rows.filter(row => 
      parseFloat(row[usageIdx]) === parseFloat(row[basicIdx])
    ).length;
    
    const totalVasFee = rows.reduce((sum, row) => sum + (parseFloat(row[vasIdx]) || 0), 0);
    
    // 지점별 요금 상위 5개
    const branchTotals = {};
    rows.forEach(row => {
      const branch = row[branchIdx];
      const amount = parseFloat(row[totalIdx]) || 0;
      branchTotals[branch] = (branchTotals[branch] || 0) + amount;
    });
    
    const top5Branches = Object.entries(branchTotals)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([branch, total]) => [branch, Math.round(total)]);
    
    // 문제 회선 목록 (기본료만 발생)
    const problemLines = rows
      .filter(row => parseFloat(row[usageIdx]) === parseFloat(row[basicIdx]))
      .slice(0, 10)
      .map(row => [
        row[branchIdx],
        row[phoneIdx],
        Math.round(parseFloat(row[totalIdx]) || 0)
      ]);
    
    return {
      kpi: {
        latestMonth: latestMonth,
        totalCost: Math.round(totalCost),
        activeLines: activeLines,
        basicFeeOnlyLines: basicFeeOnlyLines,
        totalVasFee: Math.round(totalVasFee)
      },
      top5Branches: top5Branches,
      problemLines: problemLines
    };
    
  } catch (error) {
    console.error('대시보드 데이터 오류:', error);
    throw new Error('데이터를 불러오는데 실패했습니다: ' + error.message);
  }
}

// 지점 목록 가져오기
function getBranches() {
  try {
    const ss = SpreadsheetApp.openByUrl(getSpreadsheetUrl());
    const dataSheet = ss.getSheetByName(DATA_SHEET_NAME);
    
    if (!dataSheet) return [];
    
    const data = dataSheet.getDataRange().getValues();
    if (data.length <= 1) return [];
    
    const headers = data[0];
    const branchIdx = headers.findIndex(h => h === '지점명');
    
    if (branchIdx === -1) return [];
    
    const branches = [...new Set(data.slice(1).map(row => row[branchIdx]).filter(Boolean))];
    return branches.sort();
    
  } catch (error) {
    console.error('지점 목록 오류:', error);
    return [];
  }
}

// 청구월 목록 가져오기
function getMonths() {
  try {
    const ss = SpreadsheetApp.openByUrl(getSpreadsheetUrl());
    const dataSheet = ss.getSheetByName(DATA_SHEET_NAME);
    
    if (!dataSheet) return [];
    
    const data = dataSheet.getDataRange().getValues();
    if (data.length <= 1) return [];
    
    const headers = data[0];
    const monthIdx = headers.findIndex(h => h === '청구월');
    
    if (monthIdx === -1) return [];
    
    const months = [...new Set(data.slice(1).map(row => row[monthIdx]).filter(Boolean))];
    return months.sort().reverse();
    
  } catch (error) {
    console.error('청구월 목록 오류:', error);
    return [];
  }
}

// 필터링된 데이터 가져오기
function getFilteredData(branch, month, type) {
  try {
    const ss = SpreadsheetApp.openByUrl(getSpreadsheetUrl());
    const dataSheet = ss.getSheetByName(DATA_SHEET_NAME);
    
    if (!dataSheet) return { data: [], total: 0, totalCost: 0 };
    
    const data = dataSheet.getDataRange().getValues();
    if (data.length <= 1) return { data: [], total: 0, totalCost: 0 };
    
    const headers = data[0];
    let rows = data.slice(1);
    
    // 컬럼 인덱스
    const getColumnIndex = (name) => headers.findIndex(h => h === name);
    
    const branchIdx = getColumnIndex('지점명');
    const monthIdx = getColumnIndex('청구월');
    const phoneIdx = getColumnIndex('전화번호');
    const basicIdx = getColumnIndex('기본료');
    const usageIdx = getColumnIndex('사용요금계');
    const vasIdx = getColumnIndex('부가서비스료');
    const totalIdx = getColumnIndex('최종합계');
    
    // 필터 적용
    if (branch && branch !== 'all') {
      rows = rows.filter(row => row[branchIdx] === branch);
    }
    
    if (month && month !== 'all') {
      rows = rows.filter(row => row[monthIdx] === month);
    }
    
    if (type === 'basic') {
      // 기본료만 발생: 사용요금계 = 기본료
      rows = rows.filter(row => parseFloat(row[usageIdx]) === parseFloat(row[basicIdx]));
    } else if (type === 'vas') {
      // 부가서비스 사용
      rows = rows.filter(row => parseFloat(row[vasIdx]) > 0);
    }
    
    // 결과 생성
    const result = rows.map(row => ({
      청구월: row[monthIdx],
      지점명: row[branchIdx],
      전화번호: row[phoneIdx],
      기본료: parseFloat(row[basicIdx]) || 0,
      시내통화료: parseFloat(row[getColumnIndex('시내통화료')]) || 0,
      이동통화료: parseFloat(row[getColumnIndex('이동통화료')]) || 0,
      '070통화료': parseFloat(row[getColumnIndex('070통화료')]) || 0,
      정보통화료: parseFloat(row[getColumnIndex('정보통화료')]) || 0,
      부가서비스료: parseFloat(row[vasIdx]) || 0,
      사용요금계: parseFloat(row[usageIdx]) || 0,
      할인액: parseFloat(row[getColumnIndex('할인액')]) || 0,
      부가세: parseFloat(row[getColumnIndex('부가세')]) || 0,
      최종합계: parseFloat(row[totalIdx]) || 0
    }));
    
    const totalCost = result.reduce((sum, item) => sum + item.최종합계, 0);
    
    return {
      data: result,
      total: result.length,
      totalCost: Math.round(totalCost)
    };
    
  } catch (error) {
    console.error('필터링 오류:', error);
    throw new Error('필터링 실패: ' + error.message);
  }
}

// 전화번호 검색
function searchPhone(query) {
  try {
    const ss = SpreadsheetApp.openByUrl(getSpreadsheetUrl());
    const dataSheet = ss.getSheetByName(DATA_SHEET_NAME);
    
    if (!dataSheet || !query) return [];
    
    const data = dataSheet.getDataRange().getValues();
    if (data.length <= 1) return [];
    
    const headers = data[0];
    const rows = data.slice(1);
    
    const getColumnIndex = (name) => headers.findIndex(h => h === name);
    
    const phoneIdx = getColumnIndex('전화번호');
    const branchIdx = getColumnIndex('지점명');
    const monthIdx = getColumnIndex('청구월');
    const totalIdx = getColumnIndex('최종합계');
    const vasIdx = getColumnIndex('부가서비스료');
    
    // 전화번호로 검색
    const results = rows
      .filter(row => row[phoneIdx] && row[phoneIdx].toString().includes(query))
      .map(row => ({
        청구월: row[monthIdx],
        지점명: row[branchIdx],
        전화번호: row[phoneIdx],
        최종합계: parseFloat(row[totalIdx]) || 0,
        부가서비스료: parseFloat(row[vasIdx]) || 0
      }));
    
    return results;
    
  } catch (error) {
    console.error('검색 오류:', error);
    throw new Error('검색 실패: ' + error.message);
  }
}

// PDF 업로드 및 처리 (파일 업로드는 Apps Script 웹앱에서 제한적)
function processPdfText(text) {
  try {
    // 청구월 추출
    const monthMatch = text.match(/(\d{4})년\s*(\d{2})월/);
    const billingMonth = monthMatch ? `${monthMatch[1]}-${monthMatch[2]}` : "날짜모름";
    
    // 유선전화별 데이터 파싱
    const blocks = text.split('유선전화').slice(1);
    const parsedData = [];
    
    blocks.forEach(block => {
      const phoneMatch = block.match(/070\)\*\*(\d{2}-\d{4})/);
      if (!phoneMatch) return;
      
      const phoneNumber = `070-XX${phoneMatch[1]}`;
      
      // 금액 추출 함수
      const findAmount = (pattern) => {
        const match = block.match(pattern);
        return match ? parseInt(match[1].replace(/,/g, '')) : 0;
      };
      
      const data = {
        전화번호: phoneNumber,
        기본료: findAmount(/인터넷전화기본료\s+([\d,]+)/),
        시내통화료: findAmount(/시내통화료\s+([\d,]+)/),
        이동통화료: findAmount(/이동통화료\s+([\d,]+)/),
        '070통화료': findAmount(/인터넷전화통화료\(070\)\s+([\d,]+)/),
        정보통화료: findAmount(/정보통화료\s+([\d,]+)/),
        부가서비스료: findAmount(/부가서비스이용료\s+([\d,]+)/),
        사용요금계: findAmount(/사용요금 계\s+([\d,]+)/),
        할인액: findAmount(/할인\s+-([\d,]+)/),
        부가세: findAmount(/부가가치세\(세금\)\*\s+([\d,]+)/),
        최종합계: findAmount(/합계\s+([\d,]+)/)
      };
      
      parsedData.push(data);
    });
    
    return { parsedData, billingMonth };
    
  } catch (error) {
    console.error('PDF 처리 오류:', error);
    throw new Error('PDF 처리 실패: ' + error.message);
  }
}

// 구글 시트에 데이터 업데이트
function updateSpreadsheet(invoiceData, billingMonth) {
  try {
    const ss = SpreadsheetApp.openByUrl(getSpreadsheetUrl());
    const masterSheet = ss.getSheetByName(MASTER_SHEET_NAME);
    const dataSheet = ss.getSheetByName(DATA_SHEET_NAME);
    
    if (!masterSheet || !dataSheet) {
      throw new Error('필요한 시트를 찾을 수 없습니다.');
    }
    
    // 마스터 데이터 가져오기
    const masterData = masterSheet.getDataRange().getValues();
    const masterMap = {};
    
    if (masterData.length > 1) {
      const masterHeaders = masterData[0];
      const phoneIdx = masterHeaders.findIndex(h => h === '전화번호');
      const branchIdx = masterHeaders.findIndex(h => h === '지점명');
      
      masterData.slice(1).forEach(row => {
        const phone = row[phoneIdx]?.toString().trim();
        const branch = row[branchIdx];
        if (phone && branch) {
          masterMap[phone] = branch;
        }
      });
    }
    
    // 새 데이터 준비
    const newRows = [];
    const columnOrder = [
      '청구월', '지점명', '전화번호', '기본료', '시내통화료', '이동통화료',
      '070통화료', '정보통화료', '부가서비스료', '사용요금계', '할인액', '부가세', '최종합계'
    ];
    
    invoiceData.forEach(data => {
      const pdfPhoneNumber = data.전화번호; // "070-XX95-3210"
      const suffix = pdfPhoneNumber.slice(-7); // "95-3210"
      
      let branchName = '미배정';
      let fullPhoneNumber = pdfPhoneNumber;
      
      // 부분 일치로 지점명 찾기
      for (const [masterPhone, masterBranch] of Object.entries(masterMap)) {
        if (masterPhone.endsWith(suffix)) {
          branchName = masterBranch;
          fullPhoneNumber = masterPhone;
          break;
        }
      }
      
      const row = [
        billingMonth, branchName, fullPhoneNumber,
        data.기본료 || 0, data.시내통화료 || 0, data.이동통화료 || 0,
        data['070통화료'] || 0, data.정보통화료 || 0, data.부가서비스료 || 0,
        data.사용요금계 || 0, data.할인액 || 0, data.부가세 || 0, data.최종합계 || 0
      ];
      
      newRows.push(row);
    });
    
    // 시트에 데이터 추가
    if (newRows.length > 0) {
      const lastRow = dataSheet.getLastRow();
      const range = dataSheet.getRange(lastRow + 1, 1, newRows.length, newRows[0].length);
      range.setValues(newRows);
    }
    
    return {
      success: true,
      message: `${newRows.length}개의 데이터가 처리되었습니다`,
      billingMonth: billingMonth,
      dataCount: newRows.length
    };
    
  } catch (error) {
    console.error('시트 업데이트 오류:', error);
    throw new Error('시트 업데이트 실패: ' + error.message);
  }
}

// 구글 시트 URL 가져오기 (실제 사용시 수정 필요)
function getSpreadsheetUrl() {
  // 실제 구글 시트 URL로 변경하세요
  return 'https://docs.google.com/spreadsheets/d/1SULlqe7hiRHu7mFLcCUqkkc8BJ1vsnxPrMkIE8GCUU8/edit';
}
