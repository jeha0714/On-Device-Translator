import streamlit as st
import speech_recognition as sr
from faster_whisper import WhisperModel
import argostranslate.translate # [변경] 기계번역 라이브러리
import os
import time
import queue
import threading

# 1. 페이지 설정
st.set_page_config(page_title="Offline Fast Translator", page_icon="⚡", layout="wide")
st.title("⚡ Offline Fast Real-time Translator")
st.caption("위: 기계번역 (Argos Translate) / 아래: 실시간 듣기")

# 2. 스타일 정의
st.markdown("""
<style>
    .status-box { 
        padding: 20px; 
        border-radius: 10px; 
        text-align: center; 
        margin-bottom: 15px;
    }
    .translating-box { 
        background-color: #FFF3E0; 
        color: #E65100; 
        border: 2px solid #FB8C00; 
        font-size: 22px; font-weight: bold;
    }
    .listening-box { 
        background-color: #E3F2FD; 
        color: #1565C0; 
        border: 2px solid #1565C0; 
        font-size: 20px;
    }
    .text-content { font-size: 18px; color: #333; margin-top: 5px; font-weight: normal; }
    .empty-state { color: #999; font-style: italic; }
</style>
""", unsafe_allow_html=True)

# 3. 모델 로드 (Gemma 제거됨)
@st.cache_resource
def load_models():
    # Whisper: 음성 인식 (CPU 모드)
    whisper = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=4)
    return whisper

try:
    with st.spinner("Whisper 모델 로딩 중..."):
        model_whisper = load_models()
    st.success("✅ 모델 로딩 완료!")
except Exception as e:
    st.error(f"모델 로딩 실패: {e}")
    st.stop()

# 4. 상태 변수 초기화
if "history" not in st.session_state: st.session_state.history = []
if "is_listening" not in st.session_state: st.session_state.is_listening = False
if "audio_queue" not in st.session_state: st.session_state.audio_queue = queue.Queue()
if "log_queue" not in st.session_state: st.session_state.log_queue = queue.Queue()
if "stop_event" not in st.session_state: st.session_state.stop_event = threading.Event()

if "listening_text" not in st.session_state: st.session_state.listening_text = ""
if "current_translating_text" not in st.session_state: st.session_state.current_translating_text = ""
if "translation_queue" not in st.session_state: st.session_state.translation_queue = queue.Queue()

# --- [변경] 번역 작업자 (Argos Translate 사용) ---
def run_translation_job(text, result_queue):
    try:
        # [핵심] LLM 대신 기계번역 사용 (속도 매우 빠름)
        # from_code="en", to_code="ko"
        translation = argostranslate.translate.translate(text, "en", "ko")
        result_queue.put({"en": text, "ko": translation})
    except Exception as e:
        print(f"Translation Error: {e}")
        # 에러 발생 시 원문이라도 반환
        result_queue.put({"en": text, "ko": "(번역 실패)"})

# --- 녹음 스레드 (기존 동일) ---
def record_thread(audio_queue, log_queue, energy_threshold, device_index, stop_event):
    r = sr.Recognizer()
    r.energy_threshold = energy_threshold
    r.dynamic_energy_threshold = False 
    r.pause_threshold = 1.2
    
    import io
    import time
    
    accumulated_audio_data = io.BytesIO()
    silence_counter = 0
    has_speech = False
    speech_start_time = None
    MAX_PHRASE_TIME = 15 

    try:
        with sr.Microphone(device_index=device_index) as source:
            log_queue.put(">>> [Thread] 마이크 열림!")
            sample_rate = source.SAMPLE_RATE
            sample_width = source.SAMPLE_WIDTH
            
            while not stop_event.is_set():
                try:
                    audio_chunk = r.listen(source, timeout=1, phrase_time_limit=1)
                    accumulated_audio_data.write(audio_chunk.get_raw_data())
                    
                    if not has_speech:
                        has_speech = True
                        speech_start_time = time.time()
                    
                    silence_counter = 0 
                    
                    current_duration = time.time() - speech_start_time if speech_start_time else 0
                    if current_duration > MAX_PHRASE_TIME:
                        log_queue.put(f">>> [Force] 15초 초과!")
                        full_audio = sr.AudioData(accumulated_audio_data.getvalue(), sample_rate, sample_width)
                        audio_queue.put((full_audio, True))
                        accumulated_audio_data = io.BytesIO()
                        has_speech = False
                        silence_counter = 0
                        speech_start_time = None
                        continue
                    
                    full_audio = sr.AudioData(accumulated_audio_data.getvalue(), sample_rate, sample_width)
                    audio_queue.put((full_audio, False))
                    
                except sr.WaitTimeoutError:
                    if has_speech:
                        silence_counter += 1
                        if silence_counter >= 2:
                            log_queue.put(">>> [End] 문장 종료")
                            full_audio = sr.AudioData(accumulated_audio_data.getvalue(), sample_rate, sample_width)
                            audio_queue.put((full_audio, True))
                            accumulated_audio_data = io.BytesIO()
                            has_speech = False
                            silence_counter = 0
                            speech_start_time = None
                    continue
                except Exception as e:
                    log_queue.put(f">>> [Error] {e}")
                    break
    except Exception as e:
        log_queue.put(f">>> [Fatal Error] {e}")

# 5. 사이드바
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
                st.session_state.stop_event.clear()
                st.session_state.listening_text = "" 
                st.session_state.current_translating_text = ""
                
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

# 6. 메인 화면 레이아웃
translating_placeholder = st.empty()
listening_placeholder = st.empty()

if st.session_state.is_listening:
    t_text = st.session_state.current_translating_text
    if t_text:
        translating_placeholder.markdown(f"""
            <div class="status-box translating-box">
                ⚡ <b>빠른 번역 중...</b><br>
                <div class="text-content">"{t_text}"</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        translating_placeholder.markdown("""
            <div class="status-box" style="background-color:#f0f0f0; color:#aaa; border:2px dashed #ccc;">
                ⏳ 변환 대기 중...
            </div>
        """, unsafe_allow_html=True)

    l_text = st.session_state.listening_text
    d_text = l_text if l_text else "<span class='empty-state'>...</span>"
    listening_placeholder.markdown(f"""
        <div class="status-box listening-box">
            🔵 <b>듣고 있습니다 (Listening)</b><br>
            <div class="text-content">"{d_text}"</div>
        </div>
    """, unsafe_allow_html=True)
else:
    st.info("왼쪽 사이드바에서 [시작] 버튼을 눌러주세요.")

st.write("---")
for item in reversed(st.session_state.history):
    with st.container(border=True):
        st.markdown(f"**🇺🇸 En:** {item['en']}")
        st.markdown(f"**🇰🇷 Ko:** :blue[{item['ko']}]")

# 8. 메인 루프 (Non-Blocking Logic)
if st.session_state.is_listening:
    
    try:
        while not st.session_state.translation_queue.empty():
            result = st.session_state.translation_queue.get_nowait()
            st.session_state.history.append(result)
            if st.session_state.current_translating_text == result['en']:
                 st.session_state.current_translating_text = ""
            st.rerun()
    except:
        pass

    logs = []
    while not st.session_state.log_queue.empty(): logs.append(st.session_state.log_queue.get())
    if logs:
        with log_area.container():
            for log in reversed(logs[-5:]): st.text(log)

    if not st.session_state.audio_queue.empty():
        try:
            audio_data, is_final = st.session_state.audio_queue.get()
            
            temp_file = f"temp_{time.time()}.wav"
            with open(temp_file, "wb") as f: f.write(audio_data.get_wav_data())
            
            segments, _ = model_whisper.transcribe(temp_file, beam_size=5, language="en")
            text_en = "".join([s.text for s in segments]).strip()
            
            if os.path.exists(temp_file): os.remove(temp_file)

            if text_en:
                if is_final:
                    st.session_state.listening_text = ""
                    st.session_state.current_translating_text = text_en
                    
                    # [변경] 스레드에서 Argos 번역 함수 실행
                    t = threading.Thread(
                        target=run_translation_job, 
                        args=(text_en, st.session_state.translation_queue),
                        daemon=True
                    )
                    t.start()
                    
                else:
                    st.session_state.listening_text = text_en
            
            st.rerun()
            
        except Exception as e:
            st.error(f"Error: {e}")
            time.sleep(0.1)
            st.rerun()
    else:
        time.sleep(0.05)
        if st.session_state.is_listening:
            st.rerun()
