import streamlit as st
import speech_recognition as sr
from faster_whisper import WhisperModel
import argostranslate.translate
import os
import time
import queue
import threading
import io

# 1. 페이지 설정
st.set_page_config(page_title="On-Device Translator", page_icon="📜", layout="wide")
st.title("📜 Scrollable Real-time Translator")

# 2. 스타일 정의 (스크롤 기능 추가됨)
st.markdown("""
<style>
    .main-container { display: flex; flex-direction: row; gap: 20px; }
    
    /* [핵심 수정] 박스 스타일 변경 */
    .box { 
        padding: 20px; 
        border-radius: 10px; 
        
        /* 높이를 고정하고 스크롤을 만듭니다 */
        height: 60vh;          /* 화면 높이의 60% 차지 */
        overflow-y: auto;      /* 세로 스크롤 자동 생성 */
        
        font-size: 18px;       /* 가독성을 위해 폰트 사이즈 조정 */
        line-height: 1.8;
    }
    
    .en-box { background-color: #f8f9fa; border: 2px solid #dee2e6; color: #212529; }
    .ko-box { background-color: #e3f2fd; border: 2px solid #90caf9; color: #0d47a1; }
    .label { font-weight: bold; margin-bottom: 10px; font-size: 16px; color: #555; }
    
    /* 버튼 스타일링 */
    div.stButton > button {
        width: 100%;
        height: 50px;
        font-size: 18px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# 3. 모델 로드
@st.cache_resource
def load_models():
    whisper = WhisperModel("tiny.en", device="cpu", compute_type="int8", cpu_threads=8)
    return whisper

try:
    with st.spinner("AI 모델 로딩 중..."):
        model_whisper = load_models()
except Exception as e:
    st.error(f"오류: {e}")
    st.stop()

# 4. 상태 변수
if "is_listening" not in st.session_state: st.session_state.is_listening = False
if "audio_queue" not in st.session_state: st.session_state.audio_queue = queue.Queue()
if "stop_event" not in st.session_state: st.session_state.stop_event = threading.Event()
if "live_en" not in st.session_state: st.session_state.live_en = ""
if "live_ko" not in st.session_state: st.session_state.live_ko = ""
if "history" not in st.session_state: st.session_state.history = []

# --- 녹음 스레드 ---
def record_thread(audio_queue, stop_event, energy_threshold):
    r = sr.Recognizer()
    r.energy_threshold = energy_threshold 
    r.dynamic_energy_threshold = False
    r.pause_threshold = 1.0

    try:
        with sr.Microphone() as source:
            accumulated_audio_data = io.BytesIO()
            speech_start_time = None
            has_speech = False
            MAX_SENTENCE_TIME = 10 

            while not stop_event.is_set():
                try:
                    audio_chunk = r.listen(source, timeout=1.0, phrase_time_limit=1.0)
                    accumulated_audio_data.write(audio_chunk.get_raw_data())

                    if not has_speech:
                        has_speech = True
                        speech_start_time = time.time()
                    
                    full_audio = sr.AudioData(accumulated_audio_data.getvalue(), source.SAMPLE_RATE, source.SAMPLE_WIDTH)
                    audio_queue.put((full_audio, False))

                    if time.time() - speech_start_time > MAX_SENTENCE_TIME:
                        audio_queue.put((full_audio, True))
                        accumulated_audio_data = io.BytesIO()
                        has_speech = False
                        speech_start_time = None
                
                except sr.WaitTimeoutError:
                    if has_speech:
                        full_audio = sr.AudioData(accumulated_audio_data.getvalue(), source.SAMPLE_RATE, source.SAMPLE_WIDTH)
                        audio_queue.put((full_audio, True))
                        accumulated_audio_data = io.BytesIO()
                        has_speech = False
                        speech_start_time = None
                    continue
                except:
                    break
    except:
        pass

# 5. UI 구성
sensitivity = st.slider("🎚️ 마이크 민감도", 100, 2000, 300, 50)

if st.session_state.is_listening:
    if st.button("⏹️ 통역 중지", type="primary"):
        st.session_state.is_listening = False
        st.session_state.stop_event.set()
        st.rerun()
else:
    if st.button("▶️ 통역 시작"):
        st.session_state.is_listening = True
        st.session_state.history = []
        st.session_state.live_en = ""
        st.session_state.live_ko = ""
        st.session_state.stop_event.clear()
        with st.session_state.audio_queue.mutex: st.session_state.audio_queue.queue.clear()
        
        t = threading.Thread(
            target=record_thread, 
            args=(st.session_state.audio_queue, st.session_state.stop_event, sensitivity), 
            daemon=True
        )
        t.start()
        st.rerun()

st.divider()

col1, col2 = st.columns(2)

# [UI 개선] 텍스트가 줄바꿈되어 보이도록 div 태그로 감싸서 결합
with col1:
    st.markdown("<div class='label'>🇺🇸 ENGLISH</div>", unsafe_allow_html=True)
    
    # 지난 대화들을 각각의 div로 묶음 (가독성 향상)
    history_html = "".join([f"<div style='margin-bottom:8px;'>{h[0]}</div>" for h in st.session_state.history])
    
    # 현재 말하고 있는 문장 (강조)
    if st.session_state.live_en:
        history_html += f"<div style='color:#d63384; font-weight:bold;'>{st.session_state.live_en} ...</div>"
    
    st.markdown(f"<div class='box en-box'>{history_html}</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='label'>🇰🇷 KOREAN</div>", unsafe_allow_html=True)
    
    history_html_ko = "".join([f"<div style='margin-bottom:8px;'>{h[1]}</div>" for h in st.session_state.history])
    
    if st.session_state.live_ko:
        history_html_ko += f"<div style='color:#d63384; font-weight:bold;'>{st.session_state.live_ko} ...</div>"
        
    st.markdown(f"<div class='box ko-box'>{history_html_ko}</div>", unsafe_allow_html=True)

# 6. 메인 로직
if st.session_state.is_listening:
    if not st.session_state.audio_queue.empty():
        try:
            audio_data, is_final = st.session_state.audio_queue.get()
            
            temp_file = "temp_scroll.wav"
            with open(temp_file, "wb") as f: f.write(audio_data.get_wav_data())
            
            # Tiny 모델, Beam=2
            segments, _ = model_whisper.transcribe(temp_file, beam_size=2, temperature=0.0, language="en")
            text_en = "".join([s.text for s in segments]).strip()
            
            if text_en:
                try:
                    text_ko = argostranslate.translate.translate(text_en, "en", "ko")
                except:
                    text_ko = "..."

                st.session_state.live_en = text_en
                st.session_state.live_ko = text_ko
                
                if is_final:
                    st.session_state.history.append((text_en, text_ko))
                    st.session_state.live_en = ""
                    st.session_state.live_ko = ""
            
            st.rerun()

        except Exception as e:
            st.rerun()
    else:
        time.sleep(0.05)
        st.rerun()
