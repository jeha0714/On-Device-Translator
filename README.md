# 🎤 On-Device Real-time AI Translator

이 프로젝트는 인터넷 연결 없이 로컬 환경(On-Device)에서 구동되는 **실시간 영어-한국어 음성 번역기**입니다.  
OpenAI의 **Whisper** 모델로 음성을 인식하고, 구글의 경량 LLM인 **Gemma 2**를 사용하여 자연스러운 한국어로 번역합니다.

모든 데이터 처리가 사용자 컴퓨터 내부에서 이루어지므로 **개인정보가 보호**되며 **오프라인**에서도 작동합니다.

## ✨ 주요 기능

* **실시간 음성 인식 (STT):** `Faster-Whisper`를 사용하여 빠르고 정확하게 영어를 텍스트로 변환합니다.
* **자연스러운 번역 (LLM):** `Ollama`와 `LangChain`을 통해 단순 직역이 아닌 문맥을 고려한 번역을 제공합니다.
* **끊김 없는 번역:** 백그라운드 스레드와 큐(Queue) 아키텍처를 적용하여, 번역 중에도 사용자의 말을 놓치지 않고 계속 듣습니다.
* **마이크 선택 및 설정:** 사용 가능한 마이크를 직접 선택하고, 주변 소음 환경에 맞춰 민감도(Threshold)를 조절할 수 있습니다.
* **시각적 피드백:** 듣는 중(🔵), 처리 중(🟢), 대기 중(⏹️) 상태를 명확하게 시각화했습니다.

## 🛠️ 기술 스택

* **Frontend:** Streamlit
* **LLM Serving:** Ollama (Model: `gemma2:2b`)
* **Speech-to-Text:** Faster-Whisper
* **Audio Processing:** SpeechRecognition, PyAudio
* **Logic:** Python (Threading, Queue)

## 📋 사전 준비 사항 (Prerequisites)

이 프로젝트를 실행하기 위해 다음 프로그램들이 설치되어 있어야 합니다.

1.  **Python 3.9 이상**
2.  **Ollama 설치:** [ollama.com](https://ollama.com)에서 다운로드 및 설치
3.  **FFmpeg 설치:** (Whisper 구동용)
    * Mac: `brew install ffmpeg`
    * Windows: [FFmpeg 다운로드](https://ffmpeg.org/download.html) 후 환경변수 설정
4.  **PortAudio 설치:** (PyAudio 구동용)
    * Mac: `brew install portaudio`

## 🚀 설치 방법 (Installation)

1.  **레포지토리 클론 또는 다운로드**
    ```bash
    git clone [repository_url]
    cd [project_folder]
    ```

2.  **번역 모델(Gemma 2) 다운로드**
    터미널에서 다음 명령어를 실행하여 Ollama 모델을 받습니다.
    ```bash
    ollama pull gemma2:2b
    ```

3.  **Python 라이브러리 설치**
    ```bash
    pip install streamlit langchain-ollama faster-whisper speechrecognition pyaudio
    ```
    *(Mac에서 PyAudio 설치 에러 발생 시: `brew install portaudio` 후 다시 시도)*

## 💻 사용 방법 (Usage)

이 프로젝트는 두 가지 주요 파일로 구성되어 있습니다.

### 1. `mic_check.py` (마이크 감도 점검)
앱을 실행하기 전, 내 방의 소음 수준을 확인하여 적절한 **민감도(Threshold)** 값을 찾기 위한 도구입니다.

```bash
python3 mic_check.py
