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
st.set_page_config(page_title="Dual-Block Translator", page_icon="🎤", layout="wide")
st.title("🎤 Dual-Block Real-time Translator")
st.caption("위: 번역 진행 중 / 아래: 실시간 듣기")

# 2. 스타일 정의 (위/아래 블록 구분)
st.markdown("""
<style>
    .status-box { 
        padding: 20px; 
        border-radius: 10px; 
        text-align: center; 
        margin-bottom: 15px;
    }
    /* 위쪽: 변환 중 (주황색/초록색 느낌) */
    .translating-box { 
        background-color: #FFF3E0; 
        color: #E65100; 
        border: 2px solid #FB8C00; 
        font-size: 22px;
        font-weight: bold;
    }
    /* 아래쪽: 듣는 중 (파란색 느낌) */
    .listening-box { 
        background-color: #E3F2FD; 
        color: #1565C0; 
        border: 2px solid #1565C0; 
        font-size: 20px;
    }
    .text-content {
        font-size: 18px;
        color: #333;
        margin-top: 5px;
        font-weight: normal;
    }
    .empty-state {
        color: #999;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

# 3. 모델 로드
@st.cache_resource
def load_models():
    # CPU 모드 유지, 영어 인식 강화
    whisper = WhisperModel("base", device="cpu", compute_type="int8")
    llm = ChatOllama(model="gemma2:9b", temperature=0)
    return whisper, llm

try:
    with st.spinner("AI 모델 로딩 중..."):
        model_whisper, llm = load_models()
    st.success("✅ 모델 로딩 완료!")
except Exception as e:
    st.error(f"모델 로딩 실패: {e}")
    st.stop()

# 번역 프롬프트 (퓨샷 적용)
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a professional interpreter. 
    Your task is to translate the English input into natural Korean. 
    Never answer the user's question or greet them back. 
    Just output the translated Korean text."""),
    ("user", "Hello"), ("assistant", "안녕하세요"),
    ("user", "How are you?"), ("assistant", "오늘 기분은 어떠신가요?"),
    ("user", "{text}")
])
chain = prompt | llm | StrOutputParser()

# 4. 상태 변수 초기화
if "history" not in st.session_state: st.session_state.history = []
if "is_listening" not in st.session_state: st.session_state.is_listening = False
if "audio_queue" not in st.session_state: st.session_state.audio_queue = queue.Queue()
if "log_queue" not in st.session_state: st.session_state.log_queue = queue.Queue()
if "stop_event" not in st.session_state: st.session_state.stop_event = threading.Event()

# [중요] 실시간 듣는 텍스트 저장소
if "listening_text" not in st.session_state: 
    st.session_state.listening_text = ""

# --- 백그라운드 스레드 (스트리밍 방식) ---
def record_thread(audio_queue, log_queue, energy_threshold, device_index, stop_event):
    r = sr.Recognizer()
    r.energy_threshold = energy_threshold
    r.dynamic_energy_threshold = False 
    r.pause_threshold = 1.5 # 문장 끊기 여유롭게
    
    import io
    accumulated_audio_data = io.BytesIO()
    silence_counter = 0
    has_speech = False
    
    try:
        with sr.Microphone(device_index=device_index) as source:
            log_queue.put(">>> [Thread] 마이크 열림!")
            sample_rate = source.SAMPLE_RATE
            sample_width = source.SAMPLE_WIDTH
            
            while not stop_event.is_set():
                try:
                    # 1초씩 끊어서 듣기
                    audio_chunk = r.listen(source, timeout=1, phrase_time_limit=1)
                    
                    accumulated_audio_data.write(audio_chunk.get_raw_data())
                    has_speech = True
                    silence_counter = 0
                    
                    full_audio = sr.AudioData(accumulated_audio_data.getvalue(), sample_rate, sample_width)
                    # (오디오, is_final=False) -> 중간 결과
                    audio_queue.put((full_audio, False))
                    
                except sr.WaitTimeoutError:
                    if has_speech:
                        silence_counter += 1
                        # 침묵 2회(약 2초) -> 문장 끝
                        if silence_counter >= 2:
                            full_audio = sr.AudioData(accumulated_audio_data.getvalue(), sample_rate, sample_width)
                            # (오디오, is_final=True) -> 최종 결과
                            audio_queue.put((full_audio, True))
                            
                            # 초기화
                            accumulated_audio_data = io.BytesIO()
                            has_speech = False
                            silence_counter = 0
                    continue
                except Exception as e:
                    log_queue.put(f">>> [Error] {e}")
                    break
    except Exception as e:
        log_queue.put(f">>> [Fatal Error] {e}")

# 5. 사이드바 설정
with st.sidebar:
    st.header("🎛️ 설정")
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
    except:
        selected_index = None

    energy_threshold = st.slider("민감도", 50, 1000, 300)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ 시작", use_container_width=True):
            if not st.session_state.is_listening:
                st.session_state.is_listening = True
                with st.session_state.audio_queue.mutex: st.session_state.audio_queue.queue.clear()
                with st.session_state.log_queue.mutex: st.session_state.log_queue.queue.clear()
                st.session_state.stop_event.clear()
                st.session_state.listening_text = "" # 텍스트 초기화
                
                t = threading.Thread(target=record_thread, args=(st.session_state.audio_queue, st.session_state.log_queue, energy_threshold, selected_index, st.session_state.stop_event), daemon=True)
                t.start()
                st.rerun()
    with col2:
        if st.button("⏹️ 중지", use_container_width=True):
            st.session_state.is_listening = False
            st.session_state.stop_event.set()
            st.rerun()

    st.divider()
    log_area = st.empty()

# 6. 메인 화면 레이아웃 (위/아래 분리)

# [Block 1] 위쪽: 변환 중 (Translating)
translating_placeholder = st.empty()

# [Block 2] 아래쪽: 듣는 중 (Listening)
listening_placeholder = st.empty()

# 기본 상태 렌더링
if st.session_state.is_listening:
    # 1. 위쪽 블록 (기본은 비어있거나 대기 상태)
    translating_placeholder.markdown("""
        <div class="status-box" style="background-color:#f0f0f0; color:#aaa; border:2px dashed #ccc;">
            ⏳ 변환 대기 중...
        </div>
    """, unsafe_allow_html=True)

    # 2. 아래쪽 블록 (실시간 텍스트 표시)
    current_text = st.session_state.listening_text
    display_text = current_text if current_text else "<span class='empty-state'>말씀을 하시면 여기에 표시됩니다...</span>"
    
    listening_placeholder.markdown(f"""
        <div class="status-box listening-box">
            🔵 <b>듣고 있습니다 (Listening)</b><br>
            <div class="text-content">"{display_text}"</div>
        </div>
    """, unsafe_allow_html=True)

else:
    st.info("왼쪽 사이드바에서 [시작] 버튼을 눌러주세요.")

# 7. 히스토리
st.write("---")
for item in reversed(st.session_state.history):
    with st.container(border=True):
        st.markdown(f"**🇺🇸 En:** {item['en']}")
        st.markdown(f"**🇰🇷 Ko:** :blue[{item['ko']}]")

# 8. 메인 루프 (로직 처리)
if st.session_state.is_listening:
    # 로그 처리
    logs = []
    while not st.session_state.log_queue.empty():
        logs.append(st.session_state.log_queue.get())
    if logs:
        with log_area.container():
            for log in reversed(logs[-5:]):
                st.text(log)

    # 오디오 데이터 처리
    if not st.session_state.audio_queue.empty():
        try:
            audio_data, is_final = st.session_state.audio_queue.get()
            
            temp_file = f"temp_{time.time()}.wav"
            with open(temp_file, "wb") as f: f.write(audio_data.get_wav_data())
            
            # Whisper 인식 (영어 전용)
            segments, _ = model_whisper.transcribe(temp_file, beam_size=5, language="en")
            text_en = "".join([s.text for s in segments]).strip()
            
            if os.path.exists(temp_file): os.remove(temp_file)

            if text_en:
                if is_final:
                    # [상태 전환] 문장 완성!
                    
                    # 1. 듣는 중 변수 초기화 (다음 문장 준비)
                    st.session_state.listening_text = ""
                    
                    # 2. 화면 즉시 갱신 (Imperative Update)
                    # 위쪽 블록: "이거 번역 중이야!" 하고 보여줌
                    translating_placeholder.markdown(f"""
                        <div class="status-box translating-box">
                            🚀 <b>한국어로 변환 중...</b><br>
                            <div class="text-content">"{text_en}"</div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # 아래쪽 블록: "새로 듣는 중(빈칸)"으로 바꿈
                    listening_placeholder.markdown("""
                        <div class="status-box listening-box">
                            🔵 <b>듣고 있습니다 (Listening)</b><br>
                            <div class="text-content"><span class='empty-state'>...</span></div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # 3. 번역 수행 (Blocking)
                    translation = chain.invoke({"text": text_en})
                    
                    # 4. 히스토리 저장
                    st.session_state.history.append({"en": text_en, "ko": translation})
                    
                    # 5. 화면 전체 갱신 (다시 Listening 모드로 깔끔하게 복귀)
                    st.rerun()
                    
                else:
                    # [중간 과정] 그냥 듣고 있는 중
                    st.session_state.listening_text = text_en
                    st.rerun() # 화면 갱신 (아래쪽 블록만 바뀜)
            
        except Exception as e:
            st.error(f"Error: {e}")
            
    else:
        time.sleep(0.05)
        if st.session_state.is_listening:
            st.rerun()
