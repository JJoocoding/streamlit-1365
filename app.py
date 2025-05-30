import streamlit as st
import pandas as pd
import numpy as np
import requests
import itertools
import json
import xmltodict
from datetime import datetime

st.set_page_config(layout="wide")
st.title("🏗️ 1365 사정율 분석 도구")
st.markdown("공고번호를 입력하면 복수예가 조합, 낙찰하한율, 개찰결과를 분석해 드립니다.")

# 사용자 입력
Gongo_Nm = st.text_input("🔍 공고번호를 입력하세요", "")

if st.button("분석 시작") and Gongo_Nm:

    with st.spinner("📊 데이터를 불러오는 중입니다..."):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            service_key = 'NXIL0ccBuaYTU1TvOY7wEfHJzR%2FqBRUCwoIIWHdw%2Bcfy3qy8tVEHktbZ5o95y8XqdW4GrQaj%2FSawwFq7gmkhfA%3D%3D'

            # ▶ 복수예가 상세
            url1 = f'http://apis.data.go.kr/1230000/as/ScsbidInfoService/getOpengResultListInfoCnstwkPreparPcDetail?inqryDiv=2&bidNtceNo={Gongo_Nm}&bidNtceOrd=00&pageNo=1&numOfRows=15&type=json&ServiceKey={service_key}'
            df1 = pd.json_normalize(json.loads(requests.get(url1).text)['response']['body']['items'])
            df1 = df1[['bssamt', 'bsisPlnprc']].astype('float')
            df1['SA_rate'] = df1['bsisPlnprc'] / df1['bssamt'] * 100
            base_price = df1.iloc[1]['bssamt']

            # ▶ 조합 평균 계산
            combs = itertools.combinations(df1['SA_rate'], 4)
            rates = [np.mean(c) for c in combs]
            df_rates = pd.DataFrame(rates, columns=['rate']).sort_values('rate').reset_index(drop=True)
            df_rates['조합순번'] = range(1, len(df_rates)+1)

            # ▶ 낙찰하한율 조회
            url2 = f'http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwk?inqryDiv=2&bidNtceNo={Gongo_Nm}&pageNo=1&numOfRows=10&type=json&ServiceKey={service_key}'
            df2 = pd.json_normalize(json.loads(requests.get(url2).text)['response']['body']['items'])
            sucsfbidLwltRate = float(df2.loc[0, 'sucsfbidLwltRate'])

            # ▶ A값 계산
            url3 = f'http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkBsisAmount?inqryDiv=2&bidNtceNo={Gongo_Nm}&pageNo=1&numOfRows=10&type=json&ServiceKey={service_key}'
            df3 = pd.json_normalize(json.loads(requests.get(url3).text)['response']['body']['items'])
            cost_cols = ['sftyMngcst','sftyChckMngcst','rtrfundNon','mrfnHealthInsrprm','npnInsrprm','odsnLngtrmrcprInsrprm','qltyMngcst']
            A_value = df3[cost_cols].apply(pd.to_numeric).sum(axis=1).iloc[0]

            # ▶ 개찰결과 (여기서 맨 첫 번째 업체가 1순위)
            url4 = f'http://apis.data.go.kr/1230000/as/ScsbidInfoService/getOpengResultListInfoOpengCompt?serviceKey={service_key}&pageNo=1&numOfRows=999&bidNtceNo={Gongo_Nm}'
            response4 = requests.get(url4)
            items = json.loads(json.dumps(xmltodict.parse(response4.text)))['response']['body']['items']['item']
            df4 = pd.DataFrame(items)
            df4['bidprcAmt'] = pd.to_numeric(df4['bidprcAmt'])
            df4['rate'] = (((df4['bidprcAmt'] - A_value) * 100 / sucsfbidLwltRate) + A_value) * 100 / base_price
            df4 = df4.drop_duplicates(['rate'])
            df4 = df4[(df4['rate'] >= 98) & (df4['rate'] <= 102)].copy()
            df4 = df4[['prcbdrNm', 'rate']].rename(columns={'prcbdrNm': '업체명'})

            # ▶ 1순위 업체는 API 데이터에서 첫 번째 업체명
            top_bidder = df4.iloc[0]['업체명']

            # ▶ 사정율 + 업체명 결합
            df_combined = pd.concat([
                df_rates[['rate', '조합순번']].rename(columns={'조합순번': '업체명'}),
                df4.rename(columns={'업체명': '업체명'})
            ], ignore_index=True).sort_values('rate').reset_index(drop=True)
            df_combined['rate'] = round(df_combined['rate'], 5)

            # ▶ 강조 컬럼 추가: 1순위 업체명과 일치하면 강조
            df_combined['강조_업체명'] = df_combined['업체명'].apply(
                lambda x: f"🟢 {x}" if x == top_bidder else x
            )

            # ▶ 결과 출력
            st.subheader("📈 분석 결과")
            st.dataframe(df_combined[['rate', '강조_업체명']], use_container_width=True)

            # ▶ 엑셀 다운로드 기능
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"사정율분석_{Gongo_Nm}_{now}.xlsx"
            df_combined[['rate', '업체명']].to_excel(filename, index=False)
            with open(filename, "rb") as f:
                st.download_button("📥 결과 엑셀 다운로드", f, file_name=filename)

        except Exception as e:
            st.error(f"❌ 오류 발생: {e}")
