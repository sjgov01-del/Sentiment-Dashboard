import streamlit as st
import requests 
import time
import openai

POLYGON_API_KEY = st.secrets["POLYGON_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

st.title("Stock sentiment Dashboard")
st.subheader("AI-Powered Market Sentiment Analysis")

tickers_input = st.text_input("Enter Stock Tickers (comma separated)", value="AAPL, TSLA, NVDA")
tickers = [t.strip().upper() for t in tickers_input.split(",")]

if st.button("Analyze Sentiment"):
    for ticker in tickers:
        st.write(f"---")
        st.subheader(f"Analyzing {ticker}...") 
        time.sleep(1) 
        url = f"https://api.polygon.io/v2/reference/news?ticker={ticker}&limit=10&order=desc&apiKey={POLYGON_API_KEY}"
    
        response = requests.get(url)
        data = response.json()
        if 'results' not in data:
            st.error(f"API Error: {data}")
            st.stop()
        news = data['results']
        st.write(f"Found {len(news)} articles for {ticker}")
        total_score = 0
        count = 0
        for article in news:
            headline = article['title']
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": f"Score the sentiment of this stock news headline from 0 to 100 (0=very negative, 50=neutral, 100=very positive). Reply with just the number and a one sentence explanation. Headline: {headline}"}
                ]
            )
            sentiment = response.choices[0].message.content
            score = int(''.join(filter(str.isdigit, sentiment.split('.')[0][:3])))
            total_score += score
            count += 1
            if score >= 70:
                color = "green"
            elif score <= 40:
                color = "red"
            else:
                color = "orange"
            st.write(f"**{headline}**")
            st.markdown(f"<h3 style='color:{color}'>Sentiment Score: {score}/100</h3>", unsafe_allow_html=True)
            st.write(sentiment)
            st.write("---")
        average = total_score // count
        if average >= 70:        
            color = "green"
        elif average <=40:  
            color = "red" 
        else:    
            color = "orange"
        st.markdown(f"<h2 style='color:{color}'>Overall Sentiment Score for {ticker}: {average}/100</h2>", unsafe_allow_html=True)   

   
   
   
   
   


