import speech_recognition as sr
import time
import sys

def check_microphone_level():
    r = sr.Recognizer()
    
    # 마이크 설정
    try:
        with sr.Microphone() as source:
            print("------------------------------------------------")
            print("🎤 마이크 소음 측정 모드 (CTRL+C로 종료)")
            print("------------------------------------------------")
            print("1. 잠시 침묵하세요 (배경 소음 측정 중...)")
            
            # 1초간 배경 소음 듣고 기준값 자동 계산
            r.adjust_for_ambient_noise(source, duration=1)
            
            print(f"✅ 측정된 배경 소음(Energy): {r.energy_threshold:.0f}")
            print("------------------------------------------------")
            print("이제 실시간으로 소리 크기를 출력합니다.")
            print("말을 하지 않을 때 수치가 계속 높다면, 그게 소음입니다.")
            print("------------------------------------------------")

            while True:
                # 0.1초만큼 소리를 듣고 에너지를 측정하는 꼼수 (listen 대신 raw stream 사용이 정석이지만 간편함을 위해)
                # 다만 speech_recognition은 실시간 레벨 미터 기능을 직접 제공하지 않으므로,
                # 여기서는 '자동 감지된 Threshold'를 기준으로 설명드리겠습니다.
                
                # 대신 가장 확실한 방법: 다시 ambient noise를 짧게 측정해서 출력
                r.adjust_for_ambient_noise(source, duration=0.5)
                current_noise = r.energy_threshold
                
                # 시각화 바 (Bar) 만들기
                bar_length = int(current_noise / 50) # 50단위로 바 1개
                bar = "█" * bar_length
                
                sys.stdout.write(f"\r🔊 현재 소음 레벨: {current_noise:.0f} \t{bar}")
                sys.stdout.flush()
                
    except KeyboardInterrupt:
        print("\n\n측정 종료.")
    except Exception as e:
        print(f"\n에러 발생: {e}")
        print("마이크 권한을 확인해주세요.")

if __name__ == "__main__":
    check_microphone_level()
