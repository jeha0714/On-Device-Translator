네, 작성해주신 코드를 바탕으로 프로젝트의 목적, 설치 방법, 실행 방법, 그리고 각 파일의 역할을 명확하게 정리한 `README.md` 파일을 작성해 드립니다.

아래 내용을 복사해서 프로젝트 폴더의 `README.md` 파일에 저장하시면 됩니다.

---

```markdown
# 🎤 On-Device Real-time AI Translator (영-한 실시간 통역기)

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

```

* 실행 후 아무 말도 하지 않았을 때 출력되는 숫자가 내 방의 소음(Noise Floor)입니다.
* **본 앱 실행 시, 이 숫자보다 약 +100~200 높은 값을 민감도로 설정하세요.**

### 2. `app.py` (메인 번역기 실행)

실제 번역 웹 애플리케이션을 실행합니다.

```bash
python3 -m streamlit run app.py

```

#### **앱 사용 가이드**

1. **좌측 사이드바 설정:**
* **마이크 선택:** 사용할 입력 장치를 선택합니다.
* **민감도 조절:** `mic_check.py`에서 확인한 값을 참고하여 설정합니다. (기본값: 300~400 권장)


2. **시작 (▶️):** 버튼을 누르면 통역이 시작됩니다.
3. **말하기:**
* 파란색 박스(🔵)가 뜨면 영어를 말하세요.
* 말을 멈추고 약 1.5초가 지나면 자동으로 번역되어 녹색 박스(🟢)로 바뀝니다.


4. **중지 (⏹️):** 통역을 종료합니다.

## ⚙️ 상세 설정 (Tuning)

`app.py` 내부의 `record_thread` 함수에서 다음 변수를 수정하여 인식 반응 속도를 조절할 수 있습니다.

* `r.pause_threshold`: 문장이 끝났다고 판단하는 침묵 시간 (현재: **1.5초**)
* 짧게 줄이면(0.8초) 반응이 빠르지만 말을 더듬으면 끊길 수 있습니다.


* `phrase_time_limit`: 한 번에 녹음하는 최대 시간 (현재: **15초**)
* 길게 늘리면 긴 문장을 한 번에 번역할 수 있습니다.



## ⚠️ 트러블슈팅 (Troubleshooting)

**Q. 실행했는데 '듣는 중'에서 반응이 없어요.**

* 사이드바에서 **올바른 마이크**가 선택되었는지 확인하세요.
* **민감도(Threshold)** 수치를 낮춰보세요. (예: 100~200)

**Q. 마이크 접근 에러가 발생해요.**

* **Mac 사용자:** 터미널(Terminal) 앱에 **마이크 접근 권한**이 허용되어 있는지 확인하세요.
* `시스템 설정` > `개인정보 보호 및 보안` > `마이크`



**Q. 번역이 너무 느려요.**

* `gemma2:2b` 모델은 CPU에서도 잘 동작하지만, GPU가 없는 환경에서는 약간의 지연이 발생할 수 있습니다.
* `Whisper` 모델 사이즈를 `base`에서 `tiny`로 변경하면 속도가 빨라지지만 인식률은 다소 떨어질 수 있습니다.

---
