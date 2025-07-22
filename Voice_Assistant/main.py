import time
import logging
import argparse
import threading
import queue
import sounddevice as sd
from src.command_handler import CommandHandler
from src.voice_engine import VoiceEngine
from src.config import PICOVOICE_TOKEN

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("assistant.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("JARVIS")

class AssistantState:
    """Класс для хранения состояния помощника"""
    def __init__(self):
        self.mic_enabled = True
        self.text_mode = False
        self.hybrid_mode = False
        self.command_queue = queue.Queue()
        self.shutdown_requested = False
        self.mic_device_index = None
        self.voice_engine = None

def control_thread(state, command_handler):
    """Поток для управления через консоль"""
    print("\nControl commands (prefix with '/'):")
    print("  /mic [on|off] - управление микрофоном")
    print("  /text [on|off] - текстовый режим")
    print("  /hybrid [on|off] - гибридный режим")
    print("  /devices - список аудиоустройств")
    print("  /set_mic [index] - выбрать микрофон")
    print("  /exit - завершение работы")
    print("\nUser commands (no prefix) will be processed normally")
    
    while not state.shutdown_requested:
        try:
            raw_cmd = input("\nControl> ").strip()
            
            if raw_cmd.startswith("/"):
                cmd = raw_cmd[1:].lower()
                
                if cmd == "exit":
                    logger.info("Shutdown command received")
                    state.command_queue.put("SHUTDOWN")
                    break
                    
                elif cmd.startswith("mic "):
                    action = cmd.split()[1]
                    if action == "on":
                        state.mic_enabled = True
                        if state.voice_engine:
                            state.voice_engine.set_mic_state(True)
                        logger.info("Microphone enabled")
                    elif action == "off":
                        state.mic_enabled = False
                        if state.voice_engine:
                            state.voice_engine.set_mic_state(False)
                        logger.info("Microphone disabled")
                    else:
                        print("Usage: /mic [on|off]")
                        
                elif cmd.startswith("text "):
                    action = cmd.split()[1]
                    if action == "on":
                        state.text_mode = True
                        logger.info("Text mode enabled")
                    elif action == "off":
                        state.text_mode = False
                        logger.info("Text mode disabled")
                    else:
                        print("Usage: /text [on|off]")
                        
                elif cmd.startswith("hybrid "):
                    action = cmd.split()[1]
                    if action == "on":
                        state.hybrid_mode = True
                        logger.info("Hybrid mode enabled")
                    elif action == "off":
                        state.hybrid_mode = False
                        logger.info("Hybrid mode disabled")
                    else:
                        print("Usage: /hybrid [on|off]")
                        
                elif cmd == "devices":
                    print("\nAvailable audio devices:")
                    devices = sd.query_devices()
                    for i, device in enumerate(devices):
                        if device['max_input_channels'] > 0:
                            print(f"[{i}] {device['name']} (in)")
                
                elif cmd.startswith("set_mic "):
                    try:
                        new_index = int(cmd.split()[1])
                        state.mic_device_index = new_index
                        
                        if state.voice_engine:
                            state.voice_engine.cleanup()
                        
                        state.voice_engine = VoiceEngine(
                            picovoice_token=PICOVOICE_TOKEN,
                            mic_index=new_index
                        )
                        state.voice_engine.set_mic_state(state.mic_enabled)
                        
                        logger.info(f"Microphone device set to index {new_index}")
                    except (ValueError, IndexError):
                        print("Usage: /set_mic [device_index]")
                
                else:
                    print(f"Unknown command: {cmd}. Type /help for available commands")
            
            elif raw_cmd:
                response = command_handler.handle(raw_cmd, input_type="text")
                print(f"Assistant: {response}")
                
                if state.hybrid_mode and state.voice_engine and state.voice_engine.is_active:
                    state.voice_engine.speak(response)
                
        except Exception as e:
            logger.error(f"Control thread error: {str(e)}")

def main():
    """Основная функция запуска помощника"""
    logger.info("Starting J.A.R.V.I.S. AI Assistant")
    
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Voice Assistant System')
    parser.add_argument('--text-only', action='store_true', help='Text-only mode (microphone disabled)')
    parser.add_argument('--hybrid', action='store_true', help='Hybrid voice/text mode')
    parser.add_argument('--mic-index', type=int, default=None, help='Microphone device index')
    args = parser.parse_args()
    
    # Инициализация состояния
    state = AssistantState()
    state.mic_device_index = args.mic_index
    
    # Обработка аргументов командной строки
    if args.hybrid:
        state.text_mode = True
        state.mic_enabled = True
        state.hybrid_mode = True
    elif args.text_only:
        state.text_mode = True
        state.mic_enabled = False
    else:
        # Default mode: voice with console control
        state.mic_enabled = True
        state.text_mode = False
    
    # Инициализация компонентов
    command_handler = CommandHandler()
    
    # Создаем голосовой движок (если нужен микрофон)
    if state.mic_enabled:
        state.voice_engine = VoiceEngine(
            picovoice_token=PICOVOICE_TOKEN,
            mic_index=state.mic_device_index
        )
        state.voice_engine.set_mic_state(True)
    
    logger.info(f"Initial mode: Mic={state.mic_enabled} (device={state.mic_device_index}), "
                f"Text={state.text_mode}, Hybrid={state.hybrid_mode}")
    
    # Запуск потока управления
    control_thr = threading.Thread(
        target=control_thread, 
        args=(state, command_handler),
        name="ControlThread",
        daemon=True
    )
    control_thr.start()
    
    try:
        # Основной рабочий цикл
        while not state.shutdown_requested:
            # Проверка команд управления
            if not state.command_queue.empty():
                cmd = state.command_queue.get()
                if cmd == "SHUTDOWN":
                    logger.info("Shutdown command processed")
                    break
            
            # Обработка голосовых команд
            if state.mic_enabled and state.voice_engine and state.voice_engine.is_active:
                if state.voice_engine.check_activation():
                    logger.info("Voice activation detected")
                    state.voice_engine.speak("Yes, sir?")
                    
                    command = state.voice_engine.record_command()
                    if command:
                        logger.info(f"Voice command: {command}")
                        response = command_handler.handle(command, input_type="voice")
                        if response:
                            state.voice_engine.speak(response)
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        logger.info("Assistant terminated by user")
    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
        raise
    finally:
        # Сначала освобождаем ресурсы
        logger.info("Cleaning up resources")
        if state.voice_engine:
            state.voice_engine.cleanup()
        
        # Затем устанавливаем флаг завершения
        state.shutdown_requested = True
        logger.info("Assistant shutdown complete")

if __name__ == "__main__":
    main()
