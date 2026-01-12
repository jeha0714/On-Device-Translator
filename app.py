import streamlit as st
import speech_recognition as sr
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from faster_whisper import WhisperModel
import os
import time
import queue
import threading

# 1. 페이지 설정
st.set_page_config(page_title="Stable Device Translator", page_icon="🎤", layout="wide")
st.title("🎤 Stable On-Device Translator")
st.caption("스레드 안전성(Thread-Safe)이 강화된 버전입니다.")

# 2. 스타일
st.markdown("""
<style>
    .status-box { padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; font-size: 20px; margin-bottom: 10px; }
    .listening { background-color: #E3F2FD; color: #1565C0; border: 2px solid #1565C0; }
    .translating { background-color: #E8F5E9; color: #2E7D32; border: 2px solid #2E7D32; }
</style>
""", unsafe_allow_html=True)

# 3. 모델 로드
@st.cache_resource
def load_models():
    whisper = WhisperModel("base", device="cpu", compute_type="int8")
    llm = ChatOllama(model="gemma2:2b", temperature=0)
    return whisper, llm

try:
    with st.spinner("AI 모델 로딩 중..."):
        model_whisper, llm = load_models()
    st.success("✅ 모델 로딩 완료!")
except Exception as e:
    st.error(f"모델 로딩 실패: {e}")
    st.stop()

# 번역 체인
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a professional interpreter. Translate the English input into natural Korean. Output ONLY the Korean translation."),
    ("user", "{text}")
])
chain = prompt | llm | StrOutputParser()

# 4. 상태 변수 초기화
if "history" not in st.session_state: st.session_state.history = []
if "is_listening" not in st.session_state: st.session_state.is_listening = False
if "audio_queue" not in st.session_state: st.session_state.audio_queue = queue.Queue()
if "log_queue" not in st.session_state: st.session_state.log_queue = queue.Queue()
if "ui_status" not in st.session_state: st.session_state.ui_status = "Stopped"

# [핵심 변경] 스레드 제어용 이벤트 객체 (session_state 대신 사용)
if "stop_event" not in st.session_state:
    st.session_state.stop_event = threading.Event()

# --- 백그라운드 스레드 (session_state 제거됨) ---
def record_thread(audio_queue, log_queue, energy_threshold, device_index, stop_event):
    r = sr.Recognizer()
    r.energy_threshold = energy_threshold
    r.dynamic_energy_threshold = False 
    r.pause_threshold = 1.5
    
    log_queue.put(f">>> [Thread] 마이크(ID: {device_index}) 연결 시도...")
    
    try:
        with sr.Microphone(device_index=device_index) as source:
            log_queue.put(">>> [Thread] 마이크 열림! 듣기 시작...")
            
            # [수정] st.session_state 대신 stop_event.is_set() 체크
            while not stop_event.is_set():
                try:
                    # 5초 타임아웃
                    audio = r.listen(source, timeout=1, phrase_time_limit=15)
                    log_queue.put(">>> [Detected] 🎤 오디오 감지됨!")
                    audio_queue.put(audio)
                    
                except sr.WaitTimeoutError:
                    continue 
                except Exception as e:
                    log_queue.put(f">>> [Error] {e}")
                    break
            
            log_queue.put(">>> [Thread] 종료 신호 확인. 스레드 멈춤.")
            
    except Exception as e:
        log_queue.put(f">>> [Fatal Error] 마이크 접근 실패: {e}")

# 5. 사이드바
with st.sidebar:
    st.header("🎛️ 장치 설정")
    
    try:
        mics = sr.Microphone.list_microphone_names()
        mic_options = [f"{i}: {name}" for i, name in enumerate(mics)]
        
        default_idx = 0
        for i, name in enumerate(mics):
            if "Microphone" in name or "MacBook" in name:
                default_idx = i
                break
                
        selected_mic = st.selectbox("마이크 선택", mic_options, index=default_idx)
        selected_index = int(selected_mic.split(":")[0])
        
    except Exception as e:
        st.error("마이크 목록 로딩 실패")
        selected_index = None

    energy_threshold = st.slider("민감도 (300 권장)", 50, 1000, 300)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ 시작", use_container_width=True):
            if not st.session_state.is_listening:
                st.session_state.is_listening = True
                st.session_state.ui_status = "Listening"
                
                # 큐 및 이벤트 초기화
                with st.session_state.audio_queue.mutex: st.session_state.audio_queue.queue.clear()
                with st.session_state.log_queue.mutex: st.session_state.log_queue.queue.clear()
                
                # 정지 신호 해제 (False로 설정)
                st.session_state.stop_event.clear()
                
                # [수정] 스레드에 stop_event 전달
                t = threading.Thread(
                    target=record_thread, 
                    args=(
                        st.session_state.audio_queue, 
                        st.session_state.log_queue, 
                        energy_threshold, 
                        selected_index, 
                        st.session_state.stop_event # 여기!
                    ), 
                    daemon=True
                )
                t.start()
                st.rerun()
                
    with col2:
        if st.button("⏹️ 중지", use_container_width=True):
            st.session_state.is_listening = False
            st.session_state.ui_status = "Stopped"
            
            # 정지 신호 발송 (True로 설정)
            st.session_state.stop_event.set()
            st.rerun()

    st.divider()
    st.caption("📝 실시간 로그")
    log_area = st.empty()

# 6. 메인 화면
status_placeholder = st.empty()

if st.session_state.ui_status == "Listening":
    status_placeholder.markdown('<div class="status-box listening">🔵 듣고 있습니다... (말씀하세요)</div>', unsafe_allow_html=True)
elif st.session_state.ui_status == "Translating":
    status_placeholder.markdown('<div class="status-box translating">🟢 감지됨! 번역 중...</div>', unsafe_allow_html=True)
else:
    status_placeholder.markdown('<div class="status-box" style="background-color:#eee;">⏹️ 대기 중</div>', unsafe_allow_html=True)

# 7. 히스토리
st.write("---")
for item in reversed(st.session_state.history):
    with st.container(border=True):
        st.markdown(f"**🇺🇸 En:** {item['en']}")
        st.markdown(f"**🇰🇷 Ko:** :blue[{item['ko']}]")

# 8. 메인 루프
if st.session_state.is_listening:
    # 로그 업데이트
    logs = []
    while not st.session_state.log_queue.empty():
        logs.append(st.session_state.log_queue.get())
    
    if logs:
        with log_area.container():
            for log in reversed(logs[-10:]):
                st.text(log)

    # 오디오 처리
    if not st.session_state.audio_queue.empty():
        st.session_state.ui_status = "Translating"
        status_placeholder.markdown('<div class="status-box translating">🟢 처리 중...</div>', unsafe_allow_html=True)
        
        try:
            audio_data = st.session_state.audio_queue.get()
            temp_file = f"temp_{time.time()}.wav"
            with open(temp_file, "wb") as f: f.write(audio_data.get_wav_data())
            
            segments, _ = model_whisper.transcribe(temp_file, beam_size=5)
            text_en = "".join([s.text for s in segments]).strip()
            
            if text_en:
                translation = chain.invoke({"text": text_en})
                st.session_state.history.append({"en": text_en, "ko": translation})
            
            if os.path.exists(temp_file): os.remove(temp_file)
            
        except Exception as e:
            st.error(f"Error: {e}")
        
        st.session_state.ui_status = "Listening"
        st.rerun()
    else:
        time.sleep(0.5)
        st.rerun()
