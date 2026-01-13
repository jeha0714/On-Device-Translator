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
st.set_page_config(page_title="Custom Control Translator", page_icon="🎛️", layout="wide")
st.title("🎛️ On-Device Real-time Translator")

# 2. 스타일 정의 (버튼 및 슬라이더 디자인)
st.markdown("""
<style>
    .main-container { display: flex; flex-direction: row; gap: 20px; }
    .box { 
        padding: 20px; 
        border-radius: 10px; 
        min-height: 300px;
        font-size: 22px;
        line-height: 1.6;
    }
    .en-box { background-color: #f8f9fa; border: 2px solid #dee2e6; color: #212529; }
    .ko-box { background-color: #e3f2fd; border: 2px solid #90caf9; color: #0d47a1; }
    .label { font-weight: bold; margin-bottom: 10px; font-size: 16px; color: #555; }
    
    /* 버튼 스타일링 */
    div.stButton > button {
        width: 100%;
        height: 60px;
        font-size: 20px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# 3. 모델 로드 (속도 최적화: tiny.en)
@st.cache_resource
def load_models():
    whisper = WhisperModel("tiny.en", device="cpu", compute_type="int8", cpu_threads=8)
    return whisper

try:
    with st.spinner("AI 엔진 로딩 중..."):
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
    # [핵심] 사용자가 슬라이더로 설정한 민감도를 적용
    r.energy_threshold = energy_threshold 
    r.dynamic_energy_threshold = False # 수동 제어를 위해 자동 조절 끔
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

# ==========================================
# 5. UI 구성 (컨트롤 패널)
# ==========================================

# [A] 민감도 조절 슬라이더 (상단 배치)
# 300(조용한 방) ~ 4000(시끄러운 곳)
sensitivity = st.slider("🎚️ 마이크 민감도 (낮을수록 작은 소리도 잡음)", min_value=100, max_value=2000, value=300, step=50, help="주변이 시끄러우면 값을 높이세요. 조용한 곳에서는 300 정도가 적당합니다.")

# [B] 시작/중지 통합 버튼
# 상태에 따라 버튼 텍스트와 기능을 분기함
if st.session_state.is_listening:
    # 현재 작동 중 -> '중지' 버튼 표시
    if st.button("⏹️ 통역 중지 (Click to Stop)", type="primary"):
        st.session_state.is_listening = False
        st.session_state.stop_event.set()
        st.rerun()
else:
    # 현재 정지됨 -> '시작' 버튼 표시
    if st.button("▶️ 통역 시작 (Click to Start)"):
        st.session_state.is_listening = True
        st.session_state.history = []
        st.session_state.live_en = ""
        st.session_state.live_ko = ""
        st.session_state.stop_event.clear()
        with st.session_state.audio_queue.mutex: st.session_state.audio_queue.queue.clear()
        
        # 슬라이더 값을 스레드로 전달
        t = threading.Thread(
            target=record_thread, 
            args=(st.session_state.audio_queue, st.session_state.stop_event, sensitivity), 
            daemon=True
        )
        t.start()
        st.rerun()

st.divider()

# [C] 메인 화면 (좌우 분할)
col1, col2 = st.columns(2)

with col1:
    st.markdown("<div class='label'>🇺🇸 ENGLISH</div>", unsafe_allow_html=True)
    # 히스토리 + 라이브 텍스트 결합
    full_text_en = "".join([h[0] + " " for h in st.session_state.history]) + f"**{st.session_state.live_en}**"
    st.markdown(f"<div class='box en-box'>{full_text_en}</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='label'>🇰🇷 KOREAN</div>", unsafe_allow_html=True)
    full_text_ko = "".join([h[1] + " " for h in st.session_state.history]) + f"**{st.session_state.live_ko}**"
    st.markdown(f"<div class='box ko-box'>{full_text_ko}</div>", unsafe_allow_html=True)

# 6. 메인 로직 (파일 저장 방식 + 고속 설정)
if st.session_state.is_listening:
    if not st.session_state.audio_queue.empty():
        try:
            audio_data, is_final = st.session_state.audio_queue.get()
            
            # 안전한 파일 저장 방식
            temp_file = "temp_control.wav"
            with open(temp_file, "wb") as f: f.write(audio_data.get_wav_data())
            
            # Whisper 변환
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
